# Copyright (c) 2022, Richard and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

class Attendancelist(Document):

	def submit_attendance(self, lines, publish_progress=True) :
		count = 0
		#frappe.msgprint("OK")
		for e in lines:
			#frappe.msgprint(e.employee)
			emp = frappe.get_doc('Employee', e.employee)
			jour_ouvrable = frappe.db.get_single_value('Custom Paie Settings', 'jour_ouvrable')
			emp.present_days = jour_ouvrable - e.absence
			emp.absence = e.absence
			emp.sunday_hours = e.sunday_hours
			emp.hours_30 = e.hours_30
			emp.hours_60 = e.hours_60
			emp.night_hours = e.night_hours
			emp.save()

			count += 1
			if publish_progress:
				frappe.publish_progress(
					count * 100 / len(set(lines)),
					title=_("Creating Attendance..."),
				)

	"""
	def submit(self):
		if len(self.attendance_line) > 100:
			self.queue_action('submit')
		else:
			self._submit()
	"""

	#def on_submit(self):
		#frappe.msgprint("on submit")
	#	lines = self.attendance_line
	#	try:
	#		self.check_permission("write")
	#		if lines:
	#			if len(lines) > 30 or frappe.flags.enqueue_attendance_list:
	#				self.db_set("status", "Queued")
	#				frappe.enqueue(
	#					self.submit_attendance,
	#					lines = lines,
	#					timeout=600,
	#					publish_progress=False,
	#				)
	#				frappe.msgprint(
	#					_("Attendance creation is queued. It may take a few minutes"),
	#					alert=True,
	#					indicator="blue",
	#				)
	#			else:
	#				self.submit_attendance(lines, publish_progress=False)
	#				# since this method is called via frm.call this doc needs to be updated manually
	#				self.reload()
	#	except Exception as e:
	#		frappe.db.rollback()
	#		self.log_attendance_failure("submission", attendance_list, e)

	#	finally:
	#		frappe.db.commit()  # nosemgrep
	#		frappe.publish_realtime("completed_salary_slip_creation")
    

	@frappe.whitelist()
	def fill_attendance_line(self):
		self.set("attendance_line", [])
		line = get_attendance_list(self.start_date, self.end_date, self.branch, self.employment_type)

		for d in line:
			self.append("attendance_line", d)


def get_attendance_list(debut, fin, branch="", employment_type=""):
	branch = branch + "%" if not branch is None else "%"
	employment_type = employment_type + "%" if not employment_type is None else "%"
	return frappe.db.sql("""
			SELECT v.employee AS employee, v.real_working_hours/9 AS jour_preste, 26 -  v.real_working_hours/9 AS absence, v.holidays_working AS sunday_hours,
			CASE WHEN v.avant + v.apres >= 6 THEN 6 ELSE v.avant + v.apres END AS hours_30,
			CASE WHEN v.avant + v.apres >= 6 THEN v.avant + v.apres - 6 ELSE 0 END AS hours_60,
			v.night_hours AS night_hours
			FROM (
				SELECT u.employee, u.employee_name, SUM(u.real_working_hours) AS real_working_hours, SUM(u.avant) AS avant, SUM(u.apres) AS apres, SUM(u.late_hours) AS late_hours,
					SUM(u.holidays) AS holidays_working, SUM(u.working_hours) AS working_hours, SUM(u.night_hours) AS night_hours
				FROM
				(
					SELECT t.employee, t.employee_name, t.attendance_date,t.in_date_time, t.out_date_time,
					TIME_TO_SEC(timediff(t.out_date_time, t.in_date_time))/3600 AS real_working_hours,t.avant, t.apres, t.status, t.late_hours, t.night_hours, t.holidays,
					t.working_hours
					FROM(
						SELECT a.employee, a.employee_name, a.attendance_date,
						CAST(CONCAT(CAST(CAST(a.in_time AS DATE) AS NCHAR), ' ',
						CAST(CASE WHEN  time(a.in_time) < s.start_time THEN s.start_time ELSE time(a.in_time) END AS NCHAR),19) AS DATETIME) AS in_date_time,
						CAST(CONCAT(CAST(CAST(a.out_time AS DATE) AS NCHAR), ' ',
						CAST(CASE WHEN  time(a.out_time) < s.end_time THEN time(a.out_time) ELSE s.end_time END AS NCHAR),19) AS DATETIME) AS out_date_time,
						TIME_TO_SEC(CASE WHEN timediff(time(a.in_time), time(s.start_time))  < 0 THEN timediff(time(s.start_time), time(a.in_time)) ELSE 0 END) / 3600 avant,
						TIME_TO_SEC(CASE WHEN timediff(time(a.out_time), time(s.end_time))  > 0 THEN timediff(time(a.out_time), time(s.end_time)) ELSE 0 END) / 3600 apres,
						CASE WHEN IFNULL(a.attendance_date = (SELECT holiday_date FROM tabHoliday h WHERE a.attendance_date = h.holiday_date),0) THEN 'Holidays'
						ELSE CASE WHEN a.working_hours < 4 THEN 'Absent' ELSE a.status END END AS status, 
						TIME_TO_SEC(CASE WHEN timediff(time(DATE_SUB(a.in_time, INTERVAL s.late_entry_grace_period MINUTE)), time(s.start_time))  < 0 THEN 
							timediff(time(s.start_time), time(DATE_SUB(a.in_time, INTERVAL s.late_entry_grace_period MINUTE))) ELSE 0 END) / 3600 +
						TIME_TO_SEC(CASE WHEN timediff(time(a.out_time), time(s.end_time))  < 0 THEN timediff(time(s.end_time), time(a.out_time)) ELSE 0 END) / 3600
							AS late_hours,
						CASE WHEN s.name = 'Night'THEN working_hours ELSE 0 END AS night_hours, 
						CASE WHEN IFNULL(a.attendance_date = (SELECT holiday_date FROM tabHoliday h WHERE a.attendance_date = h.holiday_date),0) THEN a.working_hours ELSE 0 END AS holidays, 
						a.working_hours
						FROM `tabAttendance` a INNER JOIN `tabShift Type` s ON a.shift = s.name INNER JOIN tabEmployee e ON e.name = a.employee
						WHERE a.attendance_date BETWEEN %(debut)s AND %(fin)s AND e.branch LIKE %(branch)s AND e.employment_type LIKE %(employment_type)s
					) AS t
				) AS u
				GROUP BY  u.employee, u.employee_name
			) AS v
		""", {"debut":debut, "fin":fin, "branch":branch, "employment_type":employment_type},
		as_dict =True,
		
	)

def log_attendance_failure(process, attendance_list, error):
	error_log = frappe.log_error(
		title=_("Attendance {0} failed for List {1}").format(process, attendance_list.name)
	)
	message_log = frappe.message_log.pop() if frappe.message_log else str(error)

	try:
		error_message = json.loads(message_log).get("message")
	except Exception:
		error_message = message_log

	error_message += "\n" + _("Check Error Log {0} for more details.").format(
		get_link_to_form("Error Log", error_log.name)
	)

	attendance_list.db_set({"error_message": error_message, "status": "Failed"})


