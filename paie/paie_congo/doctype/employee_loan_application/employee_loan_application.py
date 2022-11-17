# Copyright (c) 2022, Richard and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import nowdate

class EmployeeloanApplication(Document):
	
	def on_submit(self):
		self.create_loan()

	def check_mandatory(self):
		for fieldname in ["posting_date", "period_start", "period_end", "loan_start_date", "loan_type"]:
			if not self.get(fieldname):
				frappe.throw(_("Please set {0}").format(self.meta.get_label(fieldname)))

	def get_emp_list(self):
		"""
		Returns list of active employees based on selected criteria
		and for which salary structure exists
		"""
		self.check_mandatory()
		filters = self.make_filters()
		cond = get_filter_condition(filters)
		#cond += get_joining_relieving_condition(self.start_date, self.end_date)
		
		emp_list = get_emp_list(cond, self.basic, self.installment_amount,self.is_quinzaine)
		#emp_list = remove_payrolled_employees(emp_list, self.start_date, self.end_date)
		return emp_list

	def make_filters(self):
		filters = frappe._dict()
		filters["company"] = self.company
		filters["branch"] = self.branch
		filters["department"] = self.department
		filters["designation"] = self.designation

		return filters
	


	@frappe.whitelist()
	def fill_loan_employee_details(self):
		self.set("employee_details", [])
		employees = self.get_emp_list()
		if not employees:
			error_msg = _(
				"No employees found for the mentioned criteria:<br>Company: {0}<br> Currency: {1}<br>Payroll Payable Account: {2}"
			).format(
				frappe.bold(self.company),
				frappe.bold(self.currency),
				frappe.bold(self.payroll_payable_account),
			)
			if self.branch:
				error_msg += "<br>" + _("Branch: {0}").format(frappe.bold(self.branch))
			if self.department:
				error_msg += "<br>" + _("Department: {0}").format(frappe.bold(self.department))
			if self.designation:
				error_msg += "<br>" + _("Designation: {0}").format(frappe.bold(self.designation))
			if self.start_date:
				error_msg += "<br>" + _("Start date: {0}").format(frappe.bold(self.start_date))
			if self.end_date:
				error_msg += "<br>" + _("End date: {0}").format(frappe.bold(self.end_date))
			frappe.throw(error_msg, title=_("No employees found"))

		for d in employees:
			self.append("employee_details", d)

		#self.number_of_employees = len(self.employee_details)

	def create_loan(self):
		"""
		Creates loan for selected employees if already not created
		"""
		self.check_permission("write")
		employees =  self.employee_details
		#employees =  frappe.as_json(self.employee_details)    #[emp.employee for emp in self.employee_details]
		#frappe.msgprint("<pre>{}</pre>".format(frappe.as_json(self.employee_details)))
		#doc1 = frappe.get_doc("Employee loan Application","f961285fed")
		frappe.msgprint(len(employees))
		if employees:
			args = frappe._dict(
				{
					"applicant_type": "Employee",
					"company": self.company,
					"posting_date": self.posting_date,
					"loan_type": self.loan_type,
					"loan_amount_in_loan_currency": self.loan_amount,
					"rate_of_interest": 0,
					"exchange_rate": self.exchange_rate, 
					"currency": self.currency, 
					"repay_from_salary_slip": 1,
					"repayment_method": self.repayment_method,
					"repayment_periods": self.number_of_installments,
					"repayment_start_date": self.loan_start_date,
					"is_term_loan": 1,
					"employee_loan_application": self.name,
				}
			)
			if len(employees) > 30 or frappe.flags.enqueue_employee_loan:
				self.db_set("status", "Queued")
				frappe.enqueue(
					create_loan_for_employees,
					timeout=600,
					employees=employees,
					args=args,
					is_quinzaine=self.is_quinzaine,
					publish_progress=False,
				)
				frappe.msgprint(
					_("Loan creation is queued. It may take a few minutes"),
					alert=True,
					indicator="blue",
				)
			else:
				create_loan_for_employees(employees, args, self.is_quinzaine, publish_progress=False)
				# since this method is called via frm.call this doc needs to be updated manually
				self.reload()

#///////////////////////////////// Static Methods////////////////////////////////

def get_filter_condition(filters):
		cond = ""
		for f in ["company", "branch", "department", "designation"]:
			if filters.get(f):
				cond += " and t1." + f + " = " + frappe.db.escape(filters.get(f))

		return cond

def get_joining_relieving_condition(start_date, end_date):
	cond = """
		and ifnull(t1.date_of_joining, '1900-01-01') <= '%(end_date)s'
		and ifnull(t1.relieving_date, '2199-12-31') >= '%(start_date)s'
	""" % {
		"start_date": start_date,
		"end_date": end_date,
	}
	return cond

def get_emp_list(cond, basic, loan_amount, is_quinzaine):
	return frappe.db.sql("""
			select
				distinct t1.name as employee, t1.employee_name, t1.basic_salary_per_day * %(basic)s as basic_salary, 
				CASE WHEN %(is_quinzaine)s = 0 THEN %(loan_amount)s ELSE t1.basic_salary_per_day * %(basic)s END as loan_amount
			from
				`tabEmployee` t1 inner join `tabSalary Structure Assignment` t2 on t1.name = t2.employee
			where
				 t1.status != 'Inactive' and t2.is_main_salary = 1
			{condition}
		""".format(condition=cond),{"basic":basic, "loan_amount":loan_amount, "is_quinzaine":is_quinzaine},
		as_dict =True,
		
	)


def create_loan_for_employees(employees, args, is_quinzaine, publish_progress=True):
	try:
		count = 0

		for emp in employees:
			if is_quinzaine == 0 :
				args.update({"doctype": "Loan", "applicant": emp.employee, "monthly_repayment_amount_in_loan_currency": emp.loan_amount,})
			else :
				args.update({"doctype": "Loan", "applicant": emp.employee, "monthly_repayment_amount_in_loan_currency": emp.loan_amount,"loan_amount_in_loan_currency": emp.loan_amount,})
			loan_doc = frappe.get_doc(args)
			loan_doc.insert()
			loan_doc.submit()
			make_loan_disbursement(loan_doc.name, loan_doc.company, loan_doc.applicant_type,loan_doc.applicant,loan_doc.loan_amount)

			count += 1
			if publish_progress:
				frappe.publish_progress(
					count * 100 / len(set(employees)),
					title=_("Creating Loans..."),
				)

	except Exception as e:
		frappe.db.rollback()

	finally:
		frappe.db.commit()  # nosemgrep
		frappe.publish_realtime("completed_loan_creation")


def make_loan_disbursement(loan, company, applicant_type, applicant, pending_amount):
	disbursement_entry = frappe.new_doc("Loan Disbursement")
	disbursement_entry.against_loan = loan
	disbursement_entry.applicant_type = applicant_type
	disbursement_entry.applicant = applicant
	disbursement_entry.company = company
	disbursement_entry.disbursement_date = nowdate()
	disbursement_entry.posting_date = nowdate()

	disbursement_entry.disbursed_amount = pending_amount
	disbursement_entry.insert()
	disbursement_entry.submit()

