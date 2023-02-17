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
			SELECT a.name, a.type, a.nom_complet, a.date_naissance, a.element_name, a.parent, IFNULL(t.disponible,0) AS disponible
            FROM
            (
                SELECT DISTINCT d.name, d.type, d.nom_complet, d.date_naissance, e.element_name, d.parent
                FROM `tabDependant` d CROSS JOIN `tabElement de Voyage` e
            ) a
            LEFT JOIN
            (
                SELECT DISTINCT w.employee,w.nom,w.element_de_voyage,w.disponible
                FROM(
                    SELECT a.employee,v.nom,v.element_de_voyage,SUM(v.en_cours) - SUM(v.utilise) AS disponible
                    FROM `tabElement de Voyage Allocation` a INNER JOIN `tabElement de Voyage Details` v
                        ON v.parent = a.name
                    WHERE a.to_date <= CURDATE() AND a.docstatus = 1
                    GROUP BY v.nom,v.element_de_voyage
                ) w
            ) t ON a.parent = t.employee AND t.element_de_voyage = a.element_name AND t.nom = a.nom_complet
            WHERE a.parent = %(parent)s
		""",{"parent":emp_name},
		as_dict =True,
	)
