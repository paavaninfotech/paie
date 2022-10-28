import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import (
	add_days,
	cstr,
	flt,
	format_datetime,
	formatdate,
	get_datetime,
	get_link_to_form,
	getdate,
	nowdate,
	today,
)

import erpnext
from erpnext import get_company_currency
from erpnext.setup.doctype.employee.employee import (
	InactiveEmployeeStatusError,
	get_holiday_list_for_employee,
)

class DuplicateDeclarationError(frappe.ValidationError):
	pass

def validate_loan_repay_from_salary(doc, method=None):
	frappe.msgprint("ok")


