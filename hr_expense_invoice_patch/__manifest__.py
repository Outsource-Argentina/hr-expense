# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "HR Expense Invoice - Patch / Fix",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "author": "Outsource Argentina",
    "license": "AGPL-3",
    "summary": "Fix payment registration and payment status synchronization for HR expenses linked to vendor bills",
    "depends": ["hr_expense_invoice"],
    "data": [
        "views/hr_expense_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
