// Copyright (c) 2022, Richard and contributors
// For license information, please see license.txt

frappe.ui.form.on('Attendance list', {
	refresh: function(frm) {
		frm.add_custom_button(__("Calcul Attendance"),
			function () {
				frm.events.get_attendance_line(frm);
			}
		).toggleClass("btn-primary", !(frm.doc.attendance_line || []).length);
	},

	get_attendance_line: function (frm) {
		return frappe.call({
			doc: frm.doc,
			method: 'fill_attendance_line',
		}).then(r => {
			if (r.docs && r.docs[0].attendance_line) {
				frm.attendance_line = r.docs[0].attendance_line;
				frm.dirty();
				frm.save();
				frm.refresh();
			}
		});
	},
});
