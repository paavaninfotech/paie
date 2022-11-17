// Copyright (c) 2022, Richard and contributors
// For license information, please see license.txt

frappe.ui.form.on('Element de Voyage Application', {
	setup: function(frm) {
		frm.get_field('element_de_voyage_application_details').grid.cannot_add_rows = true;
	},
	before_save: function(frm) {
		if (frm.doc.docstatus === 0 && frm.is_new()) {
			frm.events.get_allocation_dependant(frm);
		}
	},
	get_allocation_dependant: function (frm) {
		return frappe.call({
			method: 'paie.paie_congo.doctype.element_de_voyage_application.element_de_voyage_application.get_allocation_dependant',
			args: { "emp_name": frm.doc.employee, },
		    callback: function(r, rt){
    			if (r.message) {
					frm.clear_table("element_de_voyage_application_details")
					frm.refresh_field('element_de_voyage_application_details');
					r.message.forEach(e => {
						if(e.reste <= 0) return;
						var row = frm.add_child('element_de_voyage_application_details');
						row.code = e.code;
						row.nom = e.nom;
						row.element_de_voyage = e.element_de_voyage
						row.quantite = 1;
						row.id_allocation = e.name
					});
    			    
    				frm.refresh_field('element_de_voyage_application_details');
    				frm.dirty();
    				//frm.save();
    				frm.refresh();
    			}
		    }
		});
	},
});

frappe.ui.form.on("Element de Voyage Application","onload", function(frm, cdt, cdn) { 
	var df = frappe.meta.get_docfield("Element de Voyage Application Details","code", cur_frm.doc.name);
    df.read_only = 1;
	df = frappe.meta.get_docfield("Element de Voyage Application Details","nom", cur_frm.doc.name);
    df.read_only = 1;
	df = frappe.meta.get_docfield("Element de Voyage Application Details","element_de_voyage", cur_frm.doc.name);
    df.read_only = 1;

    var df = frappe.meta.get_docfield("Element de Voyage Application Details","quantite", cur_frm.doc.name);
    df.read_only = 1;

});
