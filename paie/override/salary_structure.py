from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import SalaryStructureAssignment
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

class DuplicateAssignment(frappe.ValidationError):
	pass

class CustomSalaryStructureAssignment(SalaryStructureAssignment):

    def validate_dates(self):
        joining_date, relieving_date = frappe.db.get_value(
            "Employee", self.employee, ["date_of_joining", "relieving_date"]
        )

        if self.from_date:
            if frappe.db.exists(
                "Salary Structure Assignment",
                {"employee": self.employee, "from_date": self.from_date, "docstatus": 1, "salary_type": self.salary_type},
            ):
                frappe.throw(_("Salary Structure Assignment for Employee already exists"), DuplicateAssignment)

            if joining_date and getdate(self.from_date) < joining_date:
                frappe.throw(
                    _("From Date {0} cannot be before employee's joining Date {1}").format(
                        self.from_date, joining_date
                    )
                )

            # flag - old_employee is for migrating the old employees data via patch
            if relieving_date and getdate(self.from_date) > relieving_date and not self.flags.old_employee:
                frappe.throw(
                    _("From Date {0} cannot be after employee's relieving Date {1}").format(
                        self.from_date, relieving_date
                    )
                )