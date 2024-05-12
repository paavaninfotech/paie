from lending.loan_management.doctype.loan_repayment.loan_repayment import LoanRepayment
import frappe
from frappe import _

class CustomLoanRepayment(LoanRepayment):
	pass

def create_repayment_entry2(
	loan,
	applicant,
	company,
	posting_date,
	loan_type,
	payment_type,
	interest_payable,
	payable_principal_amount,
	amount_paid,
	cost_center,
	branch,
	penalty_amount=None,
	payroll_payable_account=None,

):

	lr = frappe.get_doc(
		{
			"doctype": "Loan Repayment",
			"against_loan": loan,
			"payment_type": payment_type,
			"company": company,
			"posting_date": posting_date,
			"applicant": applicant,
			"penalty_amount": penalty_amount,
			"interest_payable": interest_payable,
			"payable_principal_amount": payable_principal_amount,
			"amount_paid": amount_paid,
			"loan_type": loan_type,
			"payroll_payable_account": payroll_payable_account,
			"cost_center": cost_center,
			"branch": branch,
		}
	).insert()

	return lr

