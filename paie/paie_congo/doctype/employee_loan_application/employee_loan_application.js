// Copyright (c) 2022, Richard and contributors
// For license information, please see license.txt

frappe.ui.form.on('Employee loan Application', {
	refresh(frm) {
		if (frm.doc.docstatus === 0 && !frm.is_new()) {
			//frm.page.clear_primary_action();
			frm.add_custom_button(__("Get Employees"),
				function () {
					frm.events.get_employee_details(frm);
				}
			).toggleClass("btn-primary", !(frm.doc.employee_details || []).length);
		}

		/*if (
			(frm.doc.employee_details || []).length
			&& !frappe.model.has_workflow(frm.doctype)
			//&& !cint(frm.doc.salary_slips_created)
			&& (frm.doc.docstatus != 2)
		) {
			if (frm.doc.docstatus == 0) {
				frm.page.clear_primary_action();
				frm.save("Submit").then(() => {
					frm.page.clear_primary_action();
					frm.refresh();
					frm.events.refresh(frm);
				});
			} else if (frm.doc.docstatus == 1 && frm.doc.status == "Failed") {
				frm.reload_doc();
			}
		}

		if (frm.doc.docstatus == 1 && frm.doc.status == "Submitted") {
			if (frm.custom_buttons) frm.clear_custom_buttons();
			frm.events.add_context_buttons(frm);
		}

		if (frm.doc.status == "Failed" && frm.doc.error_message) {
			const issue = `<a id="jump_to_error" style="text-decoration: underline;">issue</a>`;
			let process = (cint(frm.doc.salary_slips_created)) ? "submission" : "creation";

			frm.dashboard.set_headline(
				__("Salary Slip {0} failed. You can resolve the {1} and retry {0}.", [process, issue])
			);

			$("#jump_to_error").on("click", (e) => {
				e.preventDefault();
				frappe.utils.scroll_to(
					frm.get_field("error_message").$wrapper,
					true,
					30
				);
			});
		}

		/*frappe.realtime.on("completed_salary_slip_creation", function() {
			frm.reload_doc();
		});

		frappe.realtime.on("completed_salary_slip_submission", function() {
			frm.reload_doc();
		});*/
	},
	
	number_of_installments(frm) {
	    frm.set_value('installment_amount', 0);
	    if(frm.doc.number_of_installments){
    		if(frm.doc.loan_amount){
    		    var installment_amount = 0;
    		    if (frm.doc.number_of_installments > 0) installment_amount = frm.doc.loan_amount / frm.doc.number_of_installments;
    		    frm.set_value('installment_amount', installment_amount);
    		}
	    }
	},
	
	loan_amount(frm) {
	    frm.set_value('installment_amount', 0);
	    if(frm.doc.loan_amount){
    		if(frm.doc.number_of_installments){
    		    var installment_amount = 0;
    		    if (frm.doc.number_of_installments > 0) installment_amount = frm.doc.loan_amount / frm.doc.number_of_installments;
    		    frm.set_value('installment_amount', installment_amount);
    		}
	    }
	},
	
	currency: function (frm) {
		var company_currency;
		if (!frm.doc.company) {
			company_currency = erpnext.get_currency(frappe.defaults.get_default("Company"));
		} else {
			company_currency = erpnext.get_currency(frm.doc.company);
		}
		if (frm.doc.currency) {
			if (company_currency != frm.doc.currency) {
				frappe.call({
					method: "erpnext.setup.utils.get_exchange_rate",
					args: {
						from_currency: frm.doc.currency,
						to_currency: company_currency,
					},
					callback: function (r) {
						frm.set_value("exchange_rate", flt(r.message));
					}
				});
			} else {
				frm.set_value("exchange_rate", 1.0);
			}
		}
	},

	get_employee_details: function (frm) {
		return frappe.call({
			doc: frm.doc,
			method: 'fill_loan_employee_details',
		}).then(r => {
			if (r.docs && r.docs[0].employee_details) {
				frm.employee_details = r.docs[0].employee_details;
				frm.dirty();
				frm.save();
				frm.refresh();
			}
		});
	},
});

/*frappe.ui.form.on('Employee details', { // The child table is defined in a DoctType called "Dynamic Link"
    links_add(frm, cdt, cdn) { // "links" is the name of the table field in ToDo, "_add" is the event
        // frm: current ToDo form
        // cdt: child DocType 'Dynamic Link'
        // cdn: child docname (something like 'a6dfk76')
        // cdt and cdn are useful for identifying which row triggered this event

        frappe.msgprint('A row has been added to the links table 🎉 ');
    }
});*/

frappe.ui.form.on("Loan Employee details", "loan_amount", function(frm, cdt, cdn) { 
		var row = locals[cdt][cdn]; 
		try {
			if(row.basic_salary < row.loan_amount) {
				//$("[data-fieldname=loan_amount]").focus();
				throw("Loan amount cannot be greater than the basic");
				//row.loan_amount.focus();
				
			}
		} catch (error) {
			alert(error)
		}
		
		
	});
