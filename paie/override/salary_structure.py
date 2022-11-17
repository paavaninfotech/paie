from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import SalaryStructureAssignment
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate
from hrms.payroll.doctype.salary_structure.salary_structure import assign_salary_structure_for_employees

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

    @frappe.whitelist()
    def assign_salary_structure(
        self,
        branch=None,
		employment_type=None,
        grade=None,
        department=None,
        designation=None,
        employee=None,
        payroll_payable_account=None,
        from_date=None,
        base=None,
        variable=None,
        income_tax_slab=None,
    ):
        employees = self.get_employees(
            company=self.company, grade=grade, department=department, designation=designation, name=employee, branch=branch, employment_type=employment_type
        )

        if employees:
            if len(employees) > 20:
                frappe.enqueue(
                    assign_salary_structure_for_employees,
                    timeout=600,
                    employees=employees,
                    salary_structure=self,
                    payroll_payable_account=payroll_payable_account,
                    from_date=from_date,
                    base=base,
                    variable=variable,
                    income_tax_slab=income_tax_slab,
                )
            else:
                assign_salary_structure_for_employees(
                    employees,
                    self,
                    payroll_payable_account=payroll_payable_account,
                    from_date=from_date,
                    base=base,
                    variable=variable,
                    income_tax_slab=income_tax_slab,
                )
        else:
            frappe.msgprint(_("No Employee Found"))
