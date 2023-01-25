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
from paie.override.journal_entry import CustomJournalEntry

class CustomPayrollEntry(PayrollEntry):

    def calcul_absence(self,emp):
        holiday = get_holiday_dates_for_employee(emp, self.start_date, self.end_date)
        attendance = frappe.db.count('Attendance', filters=[
                        ['employee', '=', emp],
                        ['attendance_date', 'between', [self.start_date, self.end_date]],
                        ['status', 'IN', ['Absent', 'On Leave']]
                    ])
        return attendance - len(holiday)

    def calcul_conge_annuel(self,emp, from_date, to_date):
        conge = frappe.db.sql_list(
            """
            SELECT a.total_leave_days
            FROM `tabLeave Application` a INNER JOIN `tabLeave Type` t ON a.leave_type = t.name
            WHERE a.employee = %s AND a.from_date BETWEEN %s AND %s AND a.status = 'Approved' AND is_circumstance = 0
            LIMIT 1
            """ , (emp, from_date, to_date),
        )
        #frappe.msgprint(str(conge or 0))
        if len(conge) == 0 :
            return 0
        return conge[0]

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
                leaves = self.calcul_conge_annuel(emp, self.start_date, self.end_date)
                employee = frappe.get_doc('Employee', emp)
                #employee.absence = self.calcul_absence(emp)
                employee.jour_conge = leaves
                #employee.conge_period = leaves
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
                    #frappe.msgprint(str( not frappe.db.exists("Salary Slip", {"employee": emp, "salary_type": t.salary_type, "payroll_period": self.payroll_period})))
                    #cat_details = frappe.get_doc("Employee Category Details", employee.employee_category_details)
                    attendances = frappe.db.sql(
                        """
                            SELECT l.*
                            FROM `tabAttendance list` a INNER JOIN `tabAttendance Line` l ON a.name = l.parent
                            WHERE a.pay_period = '%s' AND employee = '%s' AND a.docstatus = 1  
                        """ % (payroll_entry.payroll_period,emp), as_dict = 1
                    )
                    if not frappe.db.exists("Salary Slip", {"employee": emp, "salary_type": t.salary_type, "payroll_period": self.payroll_period}):
                        args.update({
                            "doctype": "Salary Slip", 
                            "employee": emp, 
                            "salary_type": t.salary_type, 
                            "salary_structure": t.salary_structure, 
                            "is_main_salary": t.is_main_salary,

                            "employee_category_details": employee.employee_category_details, 
                            "anciennete": employee.anciennete,
                            
                            #"present_days": employee.present_days, 
                            #"hours_30": employee.hours_30, 
                            #"night_hours": employee.night_hours, 
                            #"sunday_hours": employee.sunday_hours, 
                            #"hours_60": employee.hours_60,
                            #"absence": employee.absence, 

                            "present_days": (26 - attendances[0].absence) if len(attendances) > 0 else 26, 
                            "hours_30": attendances[0].hours_30 if len(attendances) > 0 else 0, 
                            "night_hours": attendances[0].night_hours if len(attendances) > 0 else 0, 
                            "sunday_hours": attendances[0].sunday_hours if len(attendances) > 0 else 0, 
                            "hours_60": attendances[0].hours_60 if len(attendances) > 0 else 0,
                            "absence": attendances[0].absence if len(attendances) > 0 else 0, 

                            "child": employee.child, 
                            "dependent": employee.dependent
                        })
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
                    "payroll_period": self.payroll_period
                }
            )
            if len(employees) > 30 or frappe.flags.enqueue_payroll_entry:
                self.db_set("status", "Queued")
                frappe.enqueue(
                    self.create_salary_slips_for_employees,
                    timeout=1200,
                    employees=employees,
                    args=args,
                    publish_progress=True,
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

    def make_accrual_jv_entry(self):
        self.check_permission("write")
        earnings = self.get_salary_component_total(component_type="earnings") or {}
        deductions = self.get_salary_component_total(component_type="deductions") or {}
        payroll_payable_account = self.payroll_payable_account
        jv_name = ""
        precision = frappe.get_precision("Journal Entry Account", "debit_in_account_currency")

        if earnings or deductions:
            journal_entry = frappe.new_doc("Journal Entry")
            journal_entry.voucher_type = "Journal Entry"
            journal_entry.user_remark = _("Accrual Journal Entry for salaries from {0} to {1}").format(
                self.start_date, self.end_date
            )
            journal_entry.company = self.company
            journal_entry.posting_date = self.posting_date
            accounting_dimensions = get_accounting_dimensions() or []

            accounts = []
            currencies = []
            payable_amount = 0
            payable_amt2 = 0
            multi_currency = 0
            company_currency = erpnext.get_company_currency(self.company)

            # Earnings
            for acc_cc, amount in earnings.items():
                exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
                    acc_cc[0], amount, company_currency, currencies
                )
                payable_amount += flt(amount, precision)
                payable_amt2 += flt(amt, precision)
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": acc_cc[0],
                            "debit_in_account_currency": flt(amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": acc_cc[1] or self.cost_center,
                            "project": self.project,
                        },
                        accounting_dimensions,
                    )
                )

            # Deductions
            for acc_cc, amount in deductions.items():
                exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
                    acc_cc[0], amount, company_currency, currencies
                )
                payable_amount -= flt(amount, precision)
                payable_amt2 -= flt(amt, precision)
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": acc_cc[0],
                            "credit_in_account_currency": flt(amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": acc_cc[1] or self.cost_center,
                            "project": self.project,
                        },
                        accounting_dimensions,
                    )
                )

            # Payable amount
            exchange_rate, payable_amt = self.get_amount_and_exchange_rate_for_journal_entry(
                payroll_payable_account, payable_amount, company_currency, currencies
            )
            accounts.append(
                self.update_accounting_dimensions(
                    {
                        "account": payroll_payable_account,
                        "credit_in_account_currency": flt(payable_amt, precision),
                        "exchange_rate": flt(exchange_rate),
                        "cost_center": self.cost_center,
                    },
                    accounting_dimensions,
                )
            )
            if flt(payable_amt2 - payable_amt, precision) != 0 :
                #frappe.msgprint(str(payable_amt - payable_amt2))
                accounts.append(
                    self.update_accounting_dimensions(
                        {
                            "account": "67600200 - Round Off - MCO",
                            "credit_in_account_currency": flt(payable_amt2 - payable_amt, precision),
                            "exchange_rate": flt(exchange_rate),
                            "cost_center": self.cost_center,
                        },
                        accounting_dimensions,
                    )
                )
            frappe.msgprint(str(payroll_payable_account))


            journal_entry.set("accounts", accounts)
            if len(currencies) > 1:
                multi_currency = 1
            journal_entry.multi_currency = multi_currency
            journal_entry.title = payroll_payable_account
            journal_entry.save()

            try:
                journal_entry.submit()
                jv_name = journal_entry.name
                self.update_salary_slip_status(jv_name=jv_name)
            except Exception as e:
                if type(e) in (str, list, tuple):
                    frappe.msgprint(e)
                raise
                
        return jv_name

