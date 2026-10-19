# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class AccountMove(models.Model):
    _inherit = "account.move"

    def action_register_payment(self):
        """Permitir registrar pago desde el asiento de transferencia si es llamado directamente."""
        moves_with_expense = self.filtered("source_invoice_expense_id")
        if moves_with_expense:
            payable_lines = moves_with_expense.line_ids.filtered(
                lambda l: l.account_type in ("liability_payable", "asset_receivable")
                and not l.reconciled
            )
            if payable_lines:
                return payable_lines.action_register_payment()
        return super().action_register_payment()
