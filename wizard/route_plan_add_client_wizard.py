from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalesRoutePlanAddClientWizard(models.TransientModel):
    _name = 'sales.route.plan.add.client.wizard'
    _description = 'Add Client to Daily Route Plan'

    plan_id = fields.Many2one('sales.route.plan', string='Route Plan', required=True, readonly=True)
    route_id = fields.Many2one('sales.route', string='Market Route', required=True, readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', required=True, readonly=True)
    add_mode = fields.Selection([
        ('existing', 'Existing Customer From Any Route'),
        ('new', 'Create New Customer'),
    ], default='new', required=True)
    partner_id = fields.Many2one('res.partner', string='Existing Customer', domain="[('customer_rank', '>', 0)]")
    name = fields.Char(string='Customer Name')
    phone = fields.Char()
    mobile = fields.Char()
    street = fields.Char()
    city = fields.Char()
    expected_visit_purpose_id = fields.Many2one('sales.route.visit.purpose', string='Purpose', default=lambda self: self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False))
    expected_call_type = fields.Selection([
        ('productive', 'Possible Productive'),
        ('unproductive', 'Possible Unproductive'),
    ], default='productive', required=True)
    assign_to_route = fields.Boolean(string='Also assign customer to this market route', default=False, help='Leave unticked when borrowing a customer from another route for today only. The customer keeps their original route assignment.')
    start_visit_after_add = fields.Boolean(string='Start visit immediately', default=True, help='Untick when adding a global client while preparing a route plan. The client is added to the plan only and keeps their original route.')

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        if self.partner_id and not self.name:
            self.name = self.partner_id.name

    def action_add_client(self):
        self.ensure_one()
        if self.start_visit_after_add and self.plan_id.state not in ('approved', 'in_progress'):
            raise UserError(_('You can only start a visit immediately from approved or in-progress route plans.'))
        if not self.start_visit_after_add and self.plan_id.state not in ('draft', 'approved', 'in_progress'):
            raise UserError(_('You can only add clients to draft, approved, or in-progress route plans.'))
        if self.add_mode == 'existing':
            if not self.partner_id:
                raise UserError(_('Please select an existing customer.'))
            partner = self.partner_id
            if self.assign_to_route and (not partner.route_id or partner.route_id == self.route_id):
                partner.sudo().write({'route_id': self.route_id.id, 'user_id': self.user_id.id})
        else:
            if not self.name:
                raise UserError(_('Please enter the new customer name.'))
            partner_vals = {
                'name': self.name,
                'phone': self.phone,
                'mobile': self.mobile,
                'street': self.street,
                'city': self.city,
                'customer_rank': 1,
                'user_id': self.user_id.id,
            }
            if self.assign_to_route:
                partner_vals['route_id'] = self.route_id.id
            partner = self.env['res.partner'].sudo().create(partner_vals)

        max_sequence = max(self.plan_id.line_ids.mapped('sequence') or [0])
        purpose = self.expected_visit_purpose_id
        line = self.env['sales.route.plan.line'].create({
            'plan_id': self.plan_id.id,
            'sequence': max_sequence + 10,
            'partner_id': partner.id,
            'expected_call_type': self.expected_call_type,
            'expected_visit_purpose_id': purpose.id if purpose else False,
            'expected_visit_purpose': purpose.category if purpose else 'sales',
            'is_ad_hoc': True,
        })
        self.plan_id.message_post(body=_('Client added to the route plan without changing the customer original market route: %s') % partner.display_name)
        if self.start_visit_after_add:
            if self.plan_id.state == 'approved':
                self.plan_id.state = 'in_progress'
            return line.action_start_visit()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Daily Route Plan'),
            'res_model': 'sales.route.plan',
            'view_mode': 'form',
            'res_id': self.plan_id.id,
            'target': 'current',
        }
