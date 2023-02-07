// Copyright (c) 2022, Richard and contributors
// For license information, please see license.txt

frappe.ui.form.on('Element de Voyage Allocation', {
	setup: function(frm) {
		frm.get_field('element_de_voyage_details').grid.cannot_add_rows = true;
	},
	refresh: function(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			//frm.page.clear_primary_action();
			frm.add_custom_button(__("Get All Dependants"),
				function () {
					frm.events.get_employee_all_dependants(frm);
				}
			).toggleClass("btn-primary", !(frm.doc.employee_details || []).length);
		}
	},
	get_employee_all_dependants: function (frm) {
		return frappe.call({
			method: 'paie.override.employee.get_employee_all_dependants',
			args: { "emp_name": frm.doc.employee, },
		    callback: function(r, rt){
    			if (r.message) {
					/*Object.entries(r.message).forEach(([k,v]) => {
						console.log("The key: ", k)
						console.log("The value: ", v)
					})*/
					r.message.forEach(e => {
						var row = frm.add_child('element_de_voyage_details');
						row.code = e.name,
						row.nom = e.nom_complet,
						row.element_de_voyage = e.element_name
						row.disponible = e.disponible;
						row.en_cours = 1;
						row.utilise = 0;
						row.reste = e.disponible + 1;
					});
    			    
    				frm.refresh_field('element_de_voyage_details');
    				frm.dirty();
    				//frm.save();
    				frm.refresh();
    			}
		    }
		});
	},
});

/*frappe.ui.form.on('Element de Voyage Details', { 
    refresh(frm, cdt, cdn) { 
		var row = locals[cdt][cdn];
        row.set_df_property("disponible", "read_only", 1);
		row.set_df_property("en_cours", "read_only", 1);
		row.set_df_property("utilise", "read_only", 1);
		row.set_df_property("reste", "read_only", 1);
    }
});*/

frappe.ui.form.on('Element de Voyage Details', {
	
    en_cours(frm, cdt, cdn) {
		var row = locals[cdt][cdn]; 
        if(row.en_cours != null){
			row.reste = row.disponible + row.en_cours - row.utilise;
			frm.refresh_field('element_de_voyage_details');
		}
    },
});

frappe.ui.form.on("Element de Voyage Allocation","onload", function(frm, cdt, cdn) { 
	var df = frappe.meta.get_docfield("Element de Voyage Details","code", cur_frm.doc.name);
    df.read_only = 1;
	df = frappe.meta.get_docfield("Element de Voyage Details","nom", cur_frm.doc.name);
    df.read_only = 1;
	df = frappe.meta.get_docfield("Element de Voyage Details","element_de_voyage", cur_frm.doc.name);
    df.read_only = 1;

    var df = frappe.meta.get_docfield("Element de Voyage Details","disponible", cur_frm.doc.name);
    df.read_only = 1;
	//df = frappe.meta.get_docfield("Element de Voyage Details","en_cours", cur_frm.doc.name);
    //df.read_only = 1;
	df = frappe.meta.get_docfield("Element de Voyage Details","utilise", cur_frm.doc.name);
    df.read_only = 1;
	//df.hidden = 1;
	df = frappe.meta.get_docfield("Element de Voyage Details","reste", cur_frm.doc.name);
    df.read_only = 1;
	//df.hidden = 1; 

});
