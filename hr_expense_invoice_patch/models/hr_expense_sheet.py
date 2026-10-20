# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

PAID_STATES = ("paid", "in_payment")


class HrExpenseSheet(models.Model):
    _inherit = "hr.expense.sheet"

    # -------------------------------------------------------------------------
    # Computes
    # -------------------------------------------------------------------------
    # NOTA: 'payment_state' y 'state' son campos computados almacenados en
    # Odoo 18. NO deben escribirse a mano, porque luego no se recalculan al
    # cambiar de estado (p.ej. al volver a borrador seguía figurando "Pagado").
    # Se extienden los computes para que tengan en cuenta las facturas
    # vinculadas y el estado de aprobación del reporte.

    @api.depends(
        "approval_state",
        "expense_line_ids.invoice_id",
        "expense_line_ids.invoice_id.payment_state",
    )
    def _compute_from_account_move_ids(self):
        res = super()._compute_from_account_move_ids()
        for sheet in self:
            # Reporte en borrador: nunca puede figurar como pagado
            if not sheet.approval_state:
                sheet.payment_state = "not_paid"
                continue
            if sheet.approval_state == "cancel":
                continue
            if sheet._is_paid_by_linked_invoices():
                sheet.payment_state = "paid"
        return res

    @api.depends(
        "approval_state",
        "expense_line_ids.invoice_id",
        "expense_line_ids.invoice_id.payment_state",
    )
    def _compute_state(self):
        res = super()._compute_state()
        for sheet in self:
            # Reportes aprobados cuyos gastos están cubiertos por facturas de
            # proveedor ya pagadas (y sin deuda pendiente con el empleado).
            if (
                sheet.approval_state == "approve"
                and sheet.state in ("approve", "post")
                and sheet.payment_state in PAID_STATES
                and sheet._is_paid_by_linked_invoices()
            ):
                sheet.state = "done"
        return res

    def _is_paid_by_linked_invoices(self):
        """True si todos los gastos del reporte tienen factura vinculada pagada
        y no queda saldo pendiente con el empleado."""
        self.ensure_one()
        expenses = self.expense_line_ids
        if not expenses or not all(expenses.mapped("invoice_id")):
            return False
        if any(inv.payment_state not in PAID_STATES for inv in expenses.invoice_id):
            return False
        return self._get_open_employee_lines() == self.env["account.move.line"]

    def _get_open_employee_lines(self):
        self.ensure_one()
        expenses_with_invoice = self.expense_line_ids.filtered("invoice_id")
        employee_partner = self.employee_id.sudo().work_contact_id
        transfer_moves = self.account_move_ids.filtered(
            lambda m: m.move_type == "entry"
            and m.state == "posted"
            and (
                m.source_invoice_expense_id in expenses_with_invoice
                or m.expense_sheet_id == self
            )
        )
        return transfer_moves.line_ids.filtered(
            lambda line: line.account_type in ("liability_payable", "asset_receivable")
            and not line.reconciled
            and line.partner_id == employee_partner
        )

    def _recompute_payment_and_state(self):
        """Fuerza el recálculo de los campos computados en lugar de escribirlos."""
        for fname in ("payment_state", "amount_residual", "state"):
            self.env.add_to_compute(self._fields[fname], self)
        self._recompute_recordset(["payment_state", "amount_residual", "state"])

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------

    def action_register_payment(self):
        """Permite registrar el pago del reembolso al empleado cuando hay facturas
        de proveedor asociadas y asientos de traspaso (move_type = 'entry').
        Evita el error 'No queda nada por pagar en los apuntes contables seleccionados'.
        """
        self.ensure_one()
        if self.expense_line_ids.filtered("invoice_id"):
            payable_employee_lines = self._get_open_employee_lines()
            if payable_employee_lines:
                # Abrir asistente de pago directamente sobre la deuda con el empleado
                return payable_employee_lines.action_register_payment()

            # Si no quedan líneas por pagar al empleado, recalcular estado
            # en base a las facturas vinculadas (sin escribir a mano).
            self._recompute_payment_and_state()
            if self.payment_state in PAID_STATES:
                return True

        return super().action_register_payment()

    def set_to_paid(self):
        """Compatibilidad con Odoo 17/18 donde set_to_paid no existe en el core."""
        if hasattr(super(), "set_to_paid"):
            return super().set_to_paid()
        self._recompute_payment_and_state()
        return True

    def action_sync_invoice_payments(self):
        """Acción para sincronizar el estado de pago del reporte con sus facturas vinculadas."""
        self._recompute_payment_and_state()
        return True
