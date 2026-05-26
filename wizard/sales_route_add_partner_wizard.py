from odoo import fields, models, _
from odoo.exceptions import UserError


class SalesRouteAddPartnerWizard(models.TransientModel):
    _name = 'sales.route.add.partner.wizard'
    _description = 'Add Existing Customers to Market Route'

    route_id = fields.Many2one('sales.route', string='Market Route', required=True)
    partner_ids = fields.Many2many(
        'res.partner',
        'sales_route_add_partner_wizard_rel',
        'wizard_id',
        'partner_id',
        string='Existing Customers',
        domain="[('id', 'not in', current_route_partner_ids), ('is_company', 'in', [True, False])]",
        help='Select one or many existing contacts/customers to add to this route.'
    )
    current_route_partner_ids = fields.Many2many(
        'res.partner',
        compute='_compute_current_route_partner_ids',
        string='Already on Route'
    )
    set_salesperson = fields.Boolean(
        string='Set Customer Salesperson from Route',
        default=True,
        help='If enabled, selected customers will inherit the assigned salesperson on the market route.'
    )
    overwrite_existing_route = fields.Boolean(
        string='Move Customers from Other Routes',
        default=False,
        help='If enabled, customers already assigned to another route will be moved to this route.'
    )

    def _compute_current_route_partner_ids(self):
        for wizard in self:
            wizard.current_route_partner_ids = wizard.route_id.partner_ids

    def action_add_partners(self):
        self.ensure_one()
        if not self.partner_ids:
            raise UserError(_('Please select at least one existing customer/contact.'))

        partners = self.partner_ids
        if not self.overwrite_existing_route:
            partners = partners.filtered(lambda p: not p.route_id or p.route_id == self.route_id)

        if not partners:
            raise UserError(_('All selected customers are already assigned to another route. Enable "Move Customers from Other Routes" to move them.'))

        vals = {'route_id': self.route_id.id}
        if self.set_salesperson:
            salesperson = self.route_id.user_id or self.route_id.user_ids[:1]
            if salesperson:
                vals['user_id'] = salesperson.id
        partners.write(vals)

        return {'type': 'ir.actions.act_window_close'}
