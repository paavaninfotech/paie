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
			SELECT d.name, d.type, d.nom_complet, d.date_naissance, e.element_name, t.disponible
            FROM `tabDependant` d CROSS JOIN `tabElement de Voyage` e CROSS JOIN
                (   SELECT IFNULL(w.disponible,0) AS disponible
                    FROM(
                        SELECT SUM(v.en_cours) - SUM(v.utilise) AS disponible
                        FROM `tabElement de Voyage Allocation` a INNER JOIN `tabElement de Voyage Details` v
                            ON v.parent = a.name
                        WHERE a.to_date <= CURDATE() AND a.docstatus = 1
                    ) w
                ) t 
            WHERE d.parent = %(parent)s
		""",{"parent":emp_name},
		as_dict =True,
	)
