from hrms.hr.doctype.leave_allocation.leave_allocation import LeaveAllocation
import frappe
from frappe import _
from hrms.hr.utils import  set_employee_name

class CustomLeaveAllocation(LeaveAllocation):
    def validate(self):
        self.validate_period()
        #self.validate_allocation_overlap()
        self.validate_lwp()
        set_employee_name(self)
        self.set_total_leaves_allocated()
        self.validate_leave_days_and_dates()