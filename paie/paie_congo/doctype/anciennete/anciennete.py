# Copyright (c) 2022, Richard and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class Anciennete(Document):
	
	def before_save(self):
		self.get_employee()

	def on_submit(self):
		for d in self.anciennete_details:
			doc = frappe.get_doc("Employee", d.employee)
			doc.anciennete = d.new_anciennete
			doc.save()


	def get_employee(self):
		company = self.company if not self.company == None  else '%'
		branch = self.branch if not self.branch == None else '%'

		for d in self.anciennete_details:
			frappe.delete_doc(d.get("doctype"), d.get("name"))

		employees = frappe.db.sql(
		"""
			SELECT distinct e.employee, e.date_of_joining, c.basic_salary_per_day, e.anciennete
			FROM `tabEmployee` e CROSS JOIN `tabPayroll Period` p LEFT JOIN (
				SELECT a.payroll_period, d.employee
				FROM `tabAnciennete` a INNER JOIN `tabAnciennete Details` d ON a.name =  d.parent
				WHERE a.payroll_period = %(payroll_period)s
			) t ON e.employee = t.employee  AND t.payroll_period = p.name
			INNER JOIN 	`tabEmployee Category Details` c on e.employee_category_details = c.name
			WHERE e.status = 'Active' AND e.company LIKE %(company)s AND (e.branch LIKE %(branch)s or e.branch IS NULL ) AND p.name = %(payroll_period)s
			AND DATE_ADD(e.date_of_joining, INTERVAL (YEAR(CURRENT_DATE()) - YEAR(e.date_of_joining)) YEAR) between p.start_date and p.end_date
			AND t.employee IS NULL
		""",{"company":company, "branch":branch, 'payroll_period': self.payroll_period},
		as_dict =True,
		)

		rate = frappe.db.get_single_value('Custom Paie Settings', 'anciennete_rate')


		for e in employees :
			anciennete = e.anciennete if e.anciennete else 0.0
			rate = rate if rate else 0.0
			self.append('anciennete_details',{
						'employee': e.employee,
						'date_of_join': e.date_of_joining,
						'basic': e.basic_salary_per_day,
						'current_anciennete': anciennete,
						'rate': rate,
						'new_anciennete': anciennete + (e.basic_salary_per_day + anciennete) * rate /100,
					}
				)

