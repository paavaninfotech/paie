from hrms.payroll.doctype.salary_slip.salary_slip import SalarySlip
import frappe
from frappe import _, msgprint

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