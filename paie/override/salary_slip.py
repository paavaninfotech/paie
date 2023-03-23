from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip, get_lwp_or_ppl_for_date
import frappe
from frappe import _, msgprint
from frappe.utils import (
	add_days,
	cint,
	cstr,
	date_diff,
	flt,
	formatdate,
	get_first_day,
	getdate,
	money_in_words,
	rounded,
)
from erpnext.loan_management.doctype.process_loan_interest_accrual.process_loan_interest_accrual import (
	process_loan_interest_accrual_for_term_loans,
)
from erpnext.loan_management.doctype.loan_repayment.loan_repayment import (
	calculate_amounts,
	create_repayment_entry,
)
from paie.override.loan_repayment import (
	create_repayment_entry2,
)

class CustomSalarySlip(SalarySlip):

	def check_existing(self):
			if not self.salary_slip_based_on_timesheet:
				cond = ""
				if self.payroll_entry:
					cond += "and payroll_entry = '{0}'".format(self.payroll_entry)
				ret_exist = frappe.db.sql(
					"""select name from `tabSalary Slip`
							where start_date = %s and end_date = %s and docstatus != 2
							and employee = %s and name != %s and salary_type = %s {0}""".format(
						cond
					),
					(self.start_date, self.end_date, self.employee, self.name, self.salary_type),
				)
				if ret_exist:
					frappe.throw(
						_("Salary Slip of employee {0} already created for this period").format(self.employee)
					)
			else:
				for data in self.timesheets:
					if frappe.db.get_value("Timesheet", data.time_sheet, "status") == "Payrolled":
						frappe.throw(
							_("Salary Slip of employee {0} already created for time sheet {1}").format(
								self.employee, data.time_sheet
							)
						)

	@frappe.whitelist()
	def get_emp_and_working_day_details(self):
		"""First time, load all the components from salary structure"""
		if self.employee:
			self.set("earnings", [])
			self.set("deductions", [])

			if not self.salary_slip_based_on_timesheet:
				self.get_date_details()

			joining_date, relieving_date = frappe.get_cached_value(
				"Employee", self.employee, ("date_of_joining", "relieving_date")
			)

			self.validate_dates(joining_date, relieving_date)

			# getin leave details
			self.get_working_days_details(joining_date, relieving_date)
			struct = ''
			if not self.salary_structure : 
				struct = self.check_sal_struct(joining_date, relieving_date)
			else: 
				struct = self.salary_structure

			if struct:
				self._salary_structure_doc = frappe.get_doc("Salary Structure", struct)
				self.salary_slip_based_on_timesheet = (
					self._salary_structure_doc.salary_slip_based_on_timesheet or 0
				)
				self.set_time_sheet()
				self.pull_sal_struct()
				ps = frappe.db.get_value(
					"Payroll Settings", None, ["payroll_based_on", "consider_unmarked_attendance_as"], as_dict=1
				)
				return [ps.payroll_based_on, ps.consider_unmarked_attendance_as]

	def calculate_net_pay(self):
		if self.salary_structure:
			self.calculate_component_amounts("earnings")
		self.gross_pay = self.get_component_totals("earnings", depends_on_payment_days=1)
		self.base_gross_pay = flt(
			flt(self.gross_pay) * flt(self.exchange_rate), self.precision("base_gross_pay")
		)

		if self.salary_structure:
			self.calculate_component_amounts("deductions")

		if self.is_main_salary == 1: 
			self.set_loan_repayment()
		self.set_precision_for_component_amounts()
		self.set_net_pay()

	def get_loan_details(self):
		
		loan_details = frappe.get_all(
			"Loan",
			fields=["name", "interest_income_account", "loan_account", "loan_type", "is_term_loan", "exchange_rate"],
			filters={
				"applicant": self.employee,
				"docstatus": 1,
				"company": self.company,
				"repay_from_salary_slip": 1
			},
		)
		#frappe.msgprint("Loan details ",str(loan_details))
		if loan_details:
			for loan in loan_details:
				if loan.is_term_loan:
					process_loan_interest_accrual_for_term_loans(
						posting_date=self.posting_date, loan_type=loan.loan_type, loan=loan.name
					)

		return loan_details

	def set_loan_repayment(self):
		self.total_loan_repayment = 0
		self.total_interest_amount = 0
		self.total_principal_amount = 0
		self.total_loan_repayment_foreign_currency = 0
		self.total_interest_amount_foreign_currency = 0
		self.total_principal_amount_foreign_currency = 0

		if not self.get("loans"):
			for loan in self.get_loan_details():

				amounts = calculate_amounts(loan.name, self.posting_date, "Regular Payment")
				#frappe.msgprint(str(amounts))
				if amounts["interest_amount"] or amounts["payable_principal_amount"]:
					self.append(
						"loans",
						{
							"loan": loan.name,
							"total_payment": amounts["interest_amount"] + amounts["payable_principal_amount"],
							"interest_amount": amounts["interest_amount"],
							"principal_amount": amounts["payable_principal_amount"],
							"loan_account": loan.loan_account,
							"interest_income_account": loan.interest_income_account,
							"total_payment_foreign_currency": amounts["interest_amount"] + amounts["payable_principal_amount"] / loan.exchange_rate,
							"interest_amount_foreign_currency": amounts["interest_amount"] / loan.exchange_rate,
							"principal_amount_foreign_currency": amounts["payable_principal_amount"] / loan.exchange_rate,
							"loan_exchange_rate":loan.exchange_rate,
							"loan_type": loan.loan_type,
						},
					)

		for payment in self.get("loans"):
			
			amounts = calculate_amounts(payment.loan, self.posting_date, "Regular Payment")
			total_amount = amounts["interest_amount"] + amounts["payable_principal_amount"]
			if payment.total_payment > total_amount:
				frappe.throw(
					_(
						"""Row {0}: Paid amount {1} is greater than pending accrued amount {2} against loan {3}"""
					).format(
						payment.idx,
						frappe.bold(payment.total_payment),
						frappe.bold(total_amount),
						frappe.bold(payment.loan),
					)
				)

			self.total_interest_amount += payment.interest_amount
			self.total_principal_amount += payment.principal_amount

			self.total_loan_repayment += payment.total_payment
			
			self.total_interest_amount_foreign_currency += payment.interest_amount_foreign_currency
			self.total_principal_amount_foreign_currency += payment.principal_amount_foreign_currency

			self.total_loan_repayment_foreign_currency += payment.total_payment_foreign_currency
			
	@frappe.whitelist()
	def set_totals(self):
		self.gross_pay = 0.0
		if self.salary_slip_based_on_timesheet == 1:
			self.calculate_total_for_salary_slip_based_on_timesheet()
		else:
			self.total_deduction = 0.0
			if hasattr(self, "earnings"):
				for earning in self.earnings:
					self.gross_pay += flt(earning.amount, earning.precision("amount"))
			if hasattr(self, "deductions"):
				for deduction in self.deductions:
					self.total_deduction += flt(deduction.amount, deduction.precision("amount"))
			#frappe.msgprint(str(self.total_loan_repayment_foreign_currency))
			self.net_pay = flt(self.gross_pay) - flt(self.total_deduction) - flt(self.total_loan_repayment_foreign_currency)
		self.set_base_totals()

	def set_net_pay(self):
		self.total_deduction = self.get_component_totals("deductions")
		self.base_total_deduction = flt(
			flt(self.total_deduction) * flt(self.exchange_rate), self.precision("base_total_deduction")
		)
		self.net_pay = flt(self.gross_pay) - (flt(self.total_deduction) + flt(self.total_loan_repayment_foreign_currency))
		self.rounded_total = rounded(self.net_pay)
		self.base_net_pay = flt(
			flt(self.net_pay) * flt(self.exchange_rate), self.precision("base_net_pay")
		)
		self.base_rounded_total = flt(rounded(self.base_net_pay), self.precision("base_net_pay"))
		if self.hour_rate:
			self.base_hour_rate = flt(
				flt(self.hour_rate) * flt(self.exchange_rate), self.precision("base_hour_rate")
			)
		self.set_net_total_in_words()

	def calculate_lwp_or_ppl_based_on_leave_application(self, holidays, working_days):
		lwp = 0
		holidays = "','".join(holidays)
		feries = holidays.split(',')
		nb = len(feries)
		daily_wages_fraction_for_half_day = (
			flt(frappe.db.get_value("Payroll Settings", None, "daily_wages_fraction_for_half_day")) or 0.5
		)

		#frappe.msgprint(str(working_days))
		for d in range(len(working_days) + nb):
			date = add_days(cstr(getdate(self.start_date)), d)
			leave = get_lwp_or_ppl_for_date(date, self.employee, holidays)
			#frappe.msgprint(str(d) + " | " + str(date))
			if leave:
				equivalent_lwp_count = 0
				is_half_day_leave = cint(leave[0].is_half_day)
				is_partially_paid_leave = cint(leave[0].is_ppl)
				fraction_of_daily_salary_per_leave = flt(leave[0].fraction_of_daily_salary_per_leave)

				equivalent_lwp_count = (1 - daily_wages_fraction_for_half_day) if is_half_day_leave else 1

				if is_partially_paid_leave:
					equivalent_lwp_count *= (
						fraction_of_daily_salary_per_leave if fraction_of_daily_salary_per_leave else 1
					)

				lwp += equivalent_lwp_count
				#frappe.msgprint(str(lwp))
		return lwp

	def make_loan_repayment_entry(self):
		payroll_payable_account = get_payroll_payable_account(self.company, self.payroll_entry)
		for loan in self.loans:
			if loan.total_payment:
				emp = frappe.get_doc("Employee",self.employee)
				repayment_entry = create_repayment_entry2(
					loan.loan,
					self.employee,
					self.company,
					self.posting_date,
					loan.loan_type,
					"Regular Payment",
					loan.interest_amount,
					loan.principal_amount,
					loan.total_payment,
					emp.payroll_cost_center,
					emp.branch,
					payroll_payable_account=payroll_payable_account,
				)

				repayment_entry.save()
				repayment_entry.submit()

				frappe.db.set_value(
					"Salary Slip Loan", loan.name, "loan_repayment_entry", repayment_entry.name
				)


def get_payroll_payable_account(company, payroll_entry):
	if payroll_entry:
		payroll_payable_account = frappe.db.get_value(
			"Payroll Entry", payroll_entry, "payroll_payable_account"
		)
	else:
		payroll_payable_account = frappe.db.get_value(
			"Company", company, "default_payroll_payable_account"
		)

	return payroll_payable_account


