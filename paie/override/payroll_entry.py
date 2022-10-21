from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry
import frappe
from frappe import _

import json

from dateutil.relativedelta import relativedelta


from frappe.desk.reportview import get_filters_cond, get_match_cond
from frappe.model.document import Document
from frappe.query_builder.functions import Coalesce
from frappe.utils import (
	DATE_FORMAT,
	add_days,
	add_to_date,
	cint,
	comma_and,
	date_diff,
	flt,
	get_link_to_form,
	getdate,
)

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
)
from erpnext.accounts.utils import get_fiscal_year
from erpnext.setup.doctype.employee.employee import get_holiday_list_for_employee
from hrms.hr.utils import get_holiday_dates_for_employee

class CustomPayrollEntry(PayrollEntry):

    def calcul_absence(self,emp):
        holiday = get_holiday_dates_for_employee(emp, self.start_date, self.end_date)
        attendance = frappe.db.count('Attendance', filters=[
                        ['employee', '=', emp],
                        ['attendance_date', 'between', [self.start_date, self.end_date]],
                        ['status', 'IN', ['Absent', 'On Leave']]
                    ])
        return attendance - len(holiday)

    def get_existing_salary_slips(self,employees, args):
        return frappe.db.sql_list(
            """
            select distinct employee, salary_type 
            from `tabSalary Slip`
            where docstatus!= 2 and company = %s and payroll_entry = %s
                and start_date >= %s and end_date <= %s
                and employee in (%s)
        """
            % ("%s", "%s", "%s", "%s", ", ".join(["%s"] * len(employees))),
            [args.company, args.payroll_entry, args.start_date, args.end_date] + employees,
        )


    def create_salary_slips_for_employees(self,employees, args, publish_progress=True):
        try:
            payroll_entry = frappe.get_doc("Payroll Entry", args.payroll_entry)
            salary_slips_exist_for = self.get_existing_salary_slips(employees, args)
            count = 0

            #frappe.msgprint(str(salary_slips_exist_for))
            
            
            for emp in employees:
                leaves = frappe.db.count('Attendance', filters=[
                        ['employee', '=', emp],
                        ['attendance_date', 'between', [self.start_date, self.end_date]],
                        ['status', 'IN', ['On Leave']]
                    ])
                employee = frappe.get_doc('Employee', emp)
                employee.absence = self.calcul_absence(emp)
                employee.conge_period = leaves
                employee.save()

                salary_types = frappe.db.get_list(doctype="Salary Structure Assignment", fields=["salary_type", "salary_structure"], 
                    filters={"eventual": 0, "employee": emp, "docstatus": 1})
                
                if leaves > 0 :
                    leaves_struc = frappe.db.get_list(doctype="Salary Structure Assignment", fields=["salary_type", "salary_structure"], 
                    filters={"eventual": 1, "employee": emp, "docstatus": 1, 'event_name': 'Congé Annuel'})
                    if len(leaves_struc) > 0: 
                        salary_types = salary_types + leaves_struc

                if employee.retirement == 1 : 
                    ret_struc = frappe.db.get_list(doctype="Salary Structure Assignment", fields=["salary_type", "salary_structure"], 
                    filters={"eventual": 1, "employee": emp, "docstatus": 1, 'event_name': 'Retraite'})
                    if len(ret_struc) > 0: 
                        salary_types = salary_types + ret_struc
                
                for t in salary_types:
                    #frappe.msgprint(str( not frappe.db.exists("Salary Slip", {"employee": emp, "salary_type": t.salary_type})))
                    if not frappe.db.exists("Salary Slip", {"employee": emp, "salary_type": t.salary_type}):
                        args.update({"doctype": "Salary Slip", "employee": emp, "salary_type": t.salary_type, "salary_structure": t.salary_structure})
                        frappe.get_doc(args).insert()
                        
                        #frappe.msgprint(str(args))

                        count += 1
                        if publish_progress:
                            frappe.publish_progress(
                                count * 100 / len(set(employees) - set(salary_slips_exist_for)),
                                title=_("Creating Salary Slips..."),
                            )

            payroll_entry.db_set({"status": "Submitted", "salary_slips_created": 1, "error_message": ""})

            if salary_slips_exist_for:
                frappe.msgprint(
                    _(
                        "Salary Slips already exist for employees {}, and will not be processed by this payroll."
                    ).format(frappe.bold(", ".join(emp for emp in salary_slips_exist_for))),
                    title=_("Message"),
                    indicator="orange",
                )
            
        except Exception as e:
            frappe.db.rollback()
            self.log_payroll_failure("creation", payroll_entry, e)

        finally:
            frappe.db.commit()  # nosemgrep
            frappe.publish_realtime("completed_salary_slip_creation")


    @frappe.whitelist()
    def create_salary_slips(self):
        """
        Creates salary slip for selected employees if already not created
        """
        self.check_permission("write")
        employees = [emp.employee for emp in self.employees]
        if employees:
            args = frappe._dict(
                {
                    "salary_slip_based_on_timesheet": self.salary_slip_based_on_timesheet,
                    "payroll_frequency": self.payroll_frequency,
                    "start_date": self.start_date,
                    "end_date": self.end_date,
                    "company": self.company,
                    "posting_date": self.posting_date,
                    "deduct_tax_for_unclaimed_employee_benefits": self.deduct_tax_for_unclaimed_employee_benefits,
                    "deduct_tax_for_unsubmitted_tax_exemption_proof": self.deduct_tax_for_unsubmitted_tax_exemption_proof,
                    "payroll_entry": self.name,
                    "exchange_rate": self.exchange_rate,
                    "currency": self.currency,
                    "eventual": self.eventual,
                }
            )
            if len(employees) > 30 or frappe.flags.enqueue_payroll_entry:
                self.db_set("status", "Queued")
                frappe.enqueue(
                    self.create_salary_slips_for_employees,
                    timeout=600,
                    employees=employees,
                    args=args,
                    publish_progress=False,
                )
                frappe.msgprint(
                    _("Salary Slip creation is queued. It may take a few minutes"),
                    alert=True,
                    indicator="blue",
                )
            else:
                self.create_salary_slips_for_employees(employees, args, publish_progress=False)
                # since this method is called via frm.call this doc needs to be updated manually
                self.reload()

    def log_payroll_failure(self,process, payroll_entry, error):
        error_log = frappe.log_error(
            title=_("Salary Slip {0} failed for Payroll Entry {1}").format(process, payroll_entry.name)
        )
        message_log = frappe.message_log.pop() if frappe.message_log else str(error)

        try:
            error_message = json.loads(message_log).get("message")
        except Exception:
            error_message = message_log

        error_message += "\n" + _("Check Error Log {0} for more details.").format(
            get_link_to_form("Error Log", error_log.name)
        )

        payroll_entry.db_set({"error_message": error_message, "status": "Failed"})

