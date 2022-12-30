import frappe
from frappe.model.document import Document
import pymssql  
class test(Document):
    pass

def connexion():
    conn = pymssql.connect("server", "user", "password", "tempdb")
    cursor = conn.cursor(as_dict=True)

    cursor.execute('SELECT * FROM persons WHERE salesrep=%s', 'John Doe')
    for row in cursor:
        print("ID=%d, Name=%s" % (row['id'], row['name']))

    conn.close()
