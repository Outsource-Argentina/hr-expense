# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    def action_register_payment(self):
        """Permite registrar el pago del reembolso al empleado cuando hay facturas
        de proveedor asociadas y asientos de traspaso (move_type = 'entry').
        Evita el error 'No queda nada por pagar en los apuntes contables seleccionados'.
        """
        self.ensure_one()
        expenses_with_invoice = self.expense_line_ids.filtered("invoice_id")

        if expenses_with_invoice:
            employee_partner = self.employee_id.sudo().work_contact_id
            transfer_moves = self.account_move_ids.filtered(
                lambda m: m.move_type == "entry"
                and (
                    m.source_invoice_expense_id in expenses_with_invoice
                    or m.expense_sheet_id == self
                )
            )

            # Buscar líneas abiertas por pagar al empleado
            payable_employee_lines = transfer_moves.line_ids.filtered(
                lambda line: line.account_type
                in ("liability_payable", "asset_receivable")
                and not line.reconciled
                and line.partner_id == employee_partner
            )

            if payable_employee_lines:
                # Abrir asistente de pago directamente sobre la deuda con el empleado
                return payable_employee_lines.action_register_payment()

            # Si no quedan líneas por pagar al empleado, verificar si las facturas vinculadas están pagadas
            all_invoices_paid = all(
                exp.invoice_id.payment_state in ("paid", "in_payment")
                for exp in expenses_with_invoice
            )
            if all_invoices_paid:
                self.payment_state = "paid"
                self.state = "done"
                return True

        return super().action_register_payment()

    def set_to_paid(self):
        """Compatibilidad con Odoo 17/18 donde set_to_paid no existe en el core."""
        if hasattr(super(), "set_to_paid"):
            return super().set_to_paid()
        self.write({"state": "done", "payment_state": "paid"})
        return True

    def action_sync_invoice_payments(self):
        """Acción para sincronizar el estado de pago del reporte con sus facturas vinculadas."""
        for sheet in self:
            expenses = sheet.expense_line_ids.filtered("invoice_id")
            if not expenses:
                continue
            all_paid = all(
                exp.invoice_id.payment_state in ("paid", "in_payment")
                for exp in expenses
            )
            if all_paid:
                sheet.payment_state = "paid"
                if sheet.state == "post":
                    sheet.state = "done"
