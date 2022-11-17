from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry
import frappe
from frappe.utils import cint, cstr, flt, fmt_money, formatdate, get_link_to_form, nowdate
from frappe import _, msgprint, scrub

class CustomJournalEntry(JournalEntry):

    @frappe.whitelist()
    def get_balance2(self):
        if not self.get("accounts"):
            msgprint(_("'Entries' cannot be empty"), raise_exception=True)
        else:
            self.total_debit, self.total_credit = 0, 0
            diff = flt(self.difference, self.precision("difference"))

            # If any row without amount, set the diff on that row
            if diff:
                blank_row = None
                for d in self.get("accounts"):
                    if not d.credit_in_account_currency and not d.debit_in_account_currency and diff != 0:
                        blank_row = d
                        frappe.msgprint(str(blank_row))

                if not blank_row:
                    blank_row = self.append("accounts", {})

                blank_row.exchange_rate = 1
                if diff > 0:
                    blank_row.credit_in_account_currency = diff
                    blank_row.credit = diff
                elif diff < 0:
                    blank_row.debit_in_account_currency = abs(diff)
                    blank_row.debit = abs(diff)

            self.validate_total_debit_and_credit()
