from frappe.desk.doctype.todo.todo import ToDo
import frappe

class CustomToDo(ToDo):
    def on_update(self):
        self.my_custom_code()
        super().on_update()

    def my_custom_code(self):
        frappe.msgprint("ok")


from hrms.payroll.doctype.salary_structure_assignment.salary_structure_assignment import SalaryStructureAssignment
import frappe

class CustomSalaryStructureAssignment(SalaryStructureAssignment):
    def validate_dates(self):
        self.my_custom_code()
        pass

    def my_custom_code(self):
        frappe.msgprint("ok")