from hrms.hr.doctype.leave_application.leave_application import LeaveApplication
import frappe
from frappe import _
from hrms.hr.utils import (
	get_holiday_dates_for_employee,
	get_leave_period,
	set_employee_name,
	share_doc_with_approver,
	validate_active_employee,
)
from pypika import CustomFunction
from frappe.query_builder.custom import ConstantColumn

class CustomLeaveApplication(LeaveApplication):
    def on_submit(self):
        if self.status in ["Open", "Cancelled"]:
            frappe.throw(
                _("Only Leave Applications with status 'Approved' and 'Rejected' can be submitted")
            )

        self.validate_back_dated_application()
        #self.update_attendance()

        # notify leave applier about approval
        if frappe.db.get_single_value("HR Settings", "send_leave_notification"):
            self.notify_employee()

        self.create_leave_ledger_entry()
        self.reload()

    def validate(self):
        validate_active_employee(self.employee)
        set_employee_name(self)
        self.validate_dates()
        self.validate_balance_leaves()
        self.validate_leave_overlap()
        self.validate_max_days()
        self.show_block_day_warning()
        self.validate_block_days()
        self.validate_salary_processed_days()
        #self.validate_attendance()
        self.set_half_day_date()
        if frappe.db.get_value("Leave Type", self.leave_type, "is_optional_leave"):
            self.validate_optional_leave()
        self.validate_applicable_after()


@frappe.whitelist()
def get_all_leave_details():
    all_leaves = frappe.db.get_list("Leave Type", fields = ["name"])

    return {
        "all_leaves": all_leaves,
    }

def get_leave_allocation_records_2(employee, date, leave_type=None):
	"""Returns the total allocated leaves and carry forwarded leaves based on ledger entries"""
	Ledger = frappe.qb.DocType("Leave Ledger Entry")
	LeaveAllocation = frappe.qb.DocType("Leave Allocation")

	cf_leave_case = (
		frappe.qb.terms.Case().when(Ledger.is_carry_forward == "1", Ledger.leaves).else_(0)
	)
	sum_cf_leaves = Sum(cf_leave_case).as_("cf_leaves")

	new_leaves_case = (
		frappe.qb.terms.Case().when(Ledger.is_carry_forward == "0", Ledger.leaves).else_(0)
	)
	sum_new_leaves = Sum(new_leaves_case).as_("new_leaves")

	query = (
		frappe.qb.from_(Ledger)
		.inner_join(LeaveAllocation)
		.on(Ledger.transaction_name == LeaveAllocation.name)
		.select(
			sum_cf_leaves,
			sum_new_leaves,
			Min(Ledger.from_date).as_("from_date"),
			Max(Ledger.to_date).as_("to_date"),
			Ledger.leave_type,
			Ledger.employee,
		)
		.where(
			(Ledger.from_date <= date)
			& (Ledger.docstatus == 1)
			& (Ledger.transaction_type == "Leave Allocation")
			& (Ledger.employee == employee)
			& (Ledger.is_expired == 0)
			& (Ledger.is_lwp == 0)
            & (Ledger.based_on_application == 0)
			& (
				# newly allocated leave's end date is same as the leave allocation's to date
				((Ledger.is_carry_forward == 0) & (Ledger.to_date >= date))
				# carry forwarded leave's end date won't be same as the leave allocation's to date
				# it's between the leave allocation's from and to date
				| (
					(Ledger.is_carry_forward == 1)
					& (Ledger.to_date.between(LeaveAllocation.from_date, LeaveAllocation.to_date))
					# only consider cf leaves from current allocation
					& (LeaveAllocation.from_date <= date)
					& (date <= LeaveAllocation.to_date)
				)
			)
		)
	)

	if leave_type:
		query = query.where((Ledger.leave_type == leave_type))
	query = query.groupby(Ledger.employee, Ledger.leave_type)

	allocation_details = query.run(as_dict=True)

	allocated_leaves = frappe._dict()
	for d in allocation_details:
		allocated_leaves.setdefault(
			d.leave_type,
			frappe._dict(
				{
					"from_date": d.from_date,
					"to_date": d.to_date,
					"total_leaves_allocated": flt(d.cf_leaves) + flt(d.new_leaves),
					"unused_leaves": d.cf_leaves,
					"new_leaves_allocated": d.new_leaves,
					"leave_type": d.leave_type,
					"employee": d.employee,
				}
			),
		)
	return allocated_leaves



def get_leave_application_records(employee, start_date, end_date, leave_type=None):
	"""Returns the total allocated leaves and carry forwarded leaves based on ledger entries"""
	Ledger = frappe.qb.DocType("Leave Ledger Entry")
	#LeaveAllocation = frappe.qb.DocType("Leave Allocation")

	DateDiff = CustomFunction('DATE_DIFF', ['interval', 'start_date', 'end_date'])
	debut_case = (
		frappe.qb.terms.Case().when(Ledger.from_date >= start_date, Ledger.from_date).else_(start_date)
	)
	fin_case = (
		frappe.qb.terms.Case().when(Ledger.to_date <= end_date, Ledger.to_date).else_(end_date)
	)

	previous_date_case = (
		frappe.qb.terms.Case().when(Ledger.from_date <= start_date & Ledger.to_date >= start_date, start_date).else_(Ledger.from_date)
	)

	query = (
		frappe.qb.from_(Ledger)
		#.inner_join(LeaveAllocation)
		#.on(Ledger.transaction_name == LeaveAllocation.name)
		.select(
			DateDiff('day', Ledger.from_date, previous_date_case).as_("sum_cf_leaves"),
			DateDiff('day', debut_case, fin_case).as_("sum_new_leaves"),
			ConstantColumn(start_date).as_("start_date"),
			ConstantColumn(end_date).as_("end_date"),
			Ledger.leave_type,
			Ledger.employee,
		)
		.where(
			(Ledger.from_date <= end_date)
			& (Ledger.docstatus == 1)
			& (Ledger.transaction_type == "Leave Application")
			& (Ledger.employee == employee)
			& (Ledger.is_expired == 0)
			& (Ledger.is_lwp == 0)
            & (Ledger.based_on_application == 1)
			& (
				# newly allocated leave's end date is same as the leave allocation's to date
				((Ledger.is_carry_forward == 0) & (Ledger.to_date >= end_date))
				# carry forwarded leave's end date won't be same as the leave allocation's to date
				# it's between the leave allocation's from and to date
				| (
					(Ledger.is_carry_forward == 1)
					#& (Ledger.to_date.between(LeaveAllocation.from_date, LeaveAllocation.to_date))
					# only consider cf leaves from current allocation
					& (Ledger.from_date <= end_date)
					& (end_date <= Ledger.to_date)
				)
			)
		)
	)

	if leave_type:
		query = query.where((Ledger.leave_type == leave_type))
	query = query.groupby(Ledger.employee, Ledger.leave_type)

	allocation_details = query.run(as_dict=True)

	allocated_leaves = frappe._dict()
	for d in allocation_details:
		allocated_leaves.setdefault(
			d.leave_type,
			frappe._dict(
				{
					"from_date": d.from_date,
					"to_date": d.to_date,
					"total_leaves_allocated": flt(d.cf_leaves) + flt(d.new_leaves),
					"unused_leaves": d.cf_leaves,
					"new_leaves_allocated": d.new_leaves,
					"leave_type": d.leave_type,
					"employee": d.employee,
				}
			),
		)
	return allocated_leaves