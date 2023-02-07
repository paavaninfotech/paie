from erpnext.setup.doctype.employee.employee import Employee
import frappe

class CustomEmployee(Employee):
    pass

@frappe.whitelist()
def get_employee_dependant(emp_name):
    return frappe.get_doc('Employee',emp_name)

@frappe.whitelist()
def get_employee_all_dependants(emp_name):
    return frappe.db.sql(
        """
			SELECT DISTINCT d.name, d.type, d.nom_complet, d.date_naissance, e.element_name, t.disponible
            FROM `tabDependant` d CROSS JOIN `tabElement de Voyage` e INNER JOIN
                (   SELECT w.nom,w.element_de_voyage,IFNULL(w.disponible,0) AS disponible
                    FROM(
                        SELECT v.nom,v.element_de_voyage,SUM(v.en_cours) - SUM(v.utilise) AS disponible
                        FROM `tabElement de Voyage Allocation` a INNER JOIN `tabElement de Voyage Details` v
                            ON v.parent = a.name AND employee = %(parent)s
                        WHERE a.to_date <= CURDATE() AND a.docstatus = 1
                        GROUP BY v.nom,v.element_de_voyage
                    ) w
                ) t ON t.nom = d.nom_complet
            WHERE d.parent = %(parent)s AND t.element_de_voyage = e.name
		""",{"parent":emp_name},
		as_dict =True,
	)
