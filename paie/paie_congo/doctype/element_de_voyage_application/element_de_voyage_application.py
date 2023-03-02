# Copyright (c) 2022, Richard and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.docstatus import DocStatus
from frappe.utils import getdate

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
		#exists = frappe.db.exists(
		#	"Element de Voyage Allocation",
		#	{
		#		"employee": self.employee,
		#		"docstatus": DocStatus.submitted(),
		#		"from_date": ("<=", self.date_depart),
		#		"to_date": (">=", self.date_depart),
		#	},
		#)
		if self.date_depart > self.date_arrivee : 
			frappe.throw("La date de départ en congé ne peut pas être plus grand que la date de retour!")

		element = frappe.db.sql(
			"""
				SELECT MAX(name) AS max_code
				FROM `tabElement de Voyage Allocation`
				WHERE employee =  %(employee)s 
			""",{"employee":self.employee},
		as_dict =True,
		)
		if element[0].max_code > self.voyoage_allocation:
			#frappe.msgprint(str(element[0].max_code) + " || " + self.voyoage_allocation)
			frappe.throw("Vous ne pouvez plus prendre des congés pour cette période. Utilisez une période plus récente!")

	@frappe.whitelist()
	def get_allocation_info(self):
		date = frappe.utils.formatdate(self.date_depart,"MM-dd-yyyy")
		elements = frappe.db.get_list("Element de Voyage Allocation", 
			filters={
				"employee": self.employee,
				"docstatus": DocStatus.submitted(),
				"from_date": ["<=", date],
				"to_date": [">=", date],
			},
			fields= ["*"]
		)
		#frappe.msgprint(str(self.date_depart))
		if(len(elements) > 0): 
			self.voyoage_allocation = elements[0].name
			self.from_date = elements[0].from_date
			self.to_date = elements[0].to_date
		else: 
			self.voyoage_allocation = ""
			self.from_date = ""
			self.to_date = ""
			frappe.msgprint("Il n'existe aucune allocation pour la période concernée!")
			

@frappe.whitelist()
def get_allocation_dependant(allocation):
	return frappe.db.sql(
		"""
			SELECT *
			FROM `tabElement de Voyage Details`  
			WHERE parent = %(parent)s 
		""",{"parent":allocation},
		as_dict =True,
	)
