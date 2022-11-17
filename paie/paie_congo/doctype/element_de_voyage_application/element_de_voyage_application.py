# Copyright (c) 2022, Richard and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.docstatus import DocStatus

class ElementdeVoyageApplication(Document):

	def on_cancel(self):
		frappe.db.sql(
        """
			UPDATE  `tabElement de Voyage Details` d INNER JOIN `tabElement de Voyage Allocation` a ON d.parent = a.name
				INNER JOIN `tabElement de Voyage Application Details` v ON v.code = d.code
			SET d.utilise = d.utilise - 1, d.reste = d.reste + 1
			WHERE a.employee = %(employee)s AND a.docstatus = 1 AND %(date_application)s BETWEEN a.from_date AND a.to_date AND v.parent = %(name)s 
			AND d.name = v.id_allocation;
		""",{"employee":self.employee, "date_application":self.date_application, "name":self.name,},
		as_dict =True,
		)
		frappe.db.commit()

	def on_submit(self):
		frappe.db.sql(
        """
			UPDATE  `tabElement de Voyage Details` d INNER JOIN `tabElement de Voyage Allocation` a ON d.parent = a.name
				INNER JOIN `tabElement de Voyage Application Details` v ON v.code = d.code
			SET d.utilise = d.utilise + 1, d.reste = d.reste - 1
			WHERE a.employee = %(employee)s AND a.docstatus = 1 AND %(date_application)s BETWEEN a.from_date AND a.to_date AND v.parent = %(name)s 
			AND d.name = v.id_allocation;
		""",{"employee":self.employee, "date_application":self.date_application, "name":self.name,},
		as_dict =True,
		)
		frappe.db.commit()
	
	def before_save(self):
		exists = frappe.db.exists(
			"Element de Voyage Allocation",
			{
				"employee": self.employee,
				"docstatus": DocStatus.submitted(),
				"from_date": ("<=", self.date_application),
				"to_date": (">=", self.date_application),
			},
		)
		if not exists:
			frappe.throw("Vérifier la validité du document ainsi que de la période!!!")

@frappe.whitelist()
def get_allocation_dependant(emp_name):
    return frappe.db.sql(
        """
			SELECT d.*
            FROM `tabElement de Voyage Details` d INNER JOIN `tabElement de Voyage Allocation` e 
				ON d.parent = e.name
            WHERE e.employee = %(employee)s AND e.docstatus = 1
		""",{"employee":emp_name},
		as_dict =True,
	)
