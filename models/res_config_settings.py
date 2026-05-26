# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Compatibility field for POS settings views in some Odoo 16 builds/customizations.
    # Some databases have a POS settings view referencing this field even when the
    # enterprise/employee POS extension that defines it is not installed.
    pos_employee_ids = fields.Many2many(
        'hr.employee',
        string='Allowed POS Employees',
        help='Compatibility field used by POS settings views. Install HR/employee POS features for full employee restrictions.',
    )
