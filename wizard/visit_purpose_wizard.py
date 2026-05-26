from odoo import api, fields, models, _


class SalesRouteVisitPurposeWizard(models.TransientModel):
    _name = 'sales.route.visit.purpose.wizard'
    _description = 'Choose Route Visit Purpose'

    plan_line_id = fields.Many2one('sales.route.plan.line', required=True, readonly=True)
    partner_id = fields.Many2one(related='plan_line_id.partner_id', readonly=True)
    route_id = fields.Many2one(related='plan_line_id.route_id', readonly=True)
    visit_purpose_id = fields.Many2one('sales.route.visit.purpose', string='Visit Purpose', required=True)
    visit_purpose = fields.Selection([
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('delivery', 'Delivery'),
        ('merchandising', 'Merchandising'),
        ('retail_sales', 'Retail Sales Visit'),
        ('other', 'Other'),
    ], string='Purpose Type', default='sales')

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        purpose_id = vals.get('visit_purpose_id') or self.env.context.get('default_visit_purpose_id')
        legacy = vals.get('visit_purpose') or self.env.context.get('default_visit_purpose') or 'sales'
        if not purpose_id:
            purpose = self.env['sales.route.visit.purpose'].search([('category', '=', legacy)], limit=1)
            if purpose:
                purpose_id = purpose.id
        if purpose_id:
            purpose = self.env['sales.route.visit.purpose'].browse(purpose_id)
            vals['visit_purpose_id'] = purpose.id
            vals['visit_purpose'] = purpose.category or 'other'
        return vals

    @api.onchange('visit_purpose_id')
    def _onchange_visit_purpose_id(self):
        if self.visit_purpose_id:
            self.visit_purpose = self.visit_purpose_id.category or 'other'

    def action_proceed(self):
        self.ensure_one()
        line = self.plan_line_id
        purpose = self.visit_purpose_id
        category = purpose.category or 'other'
        vals = {
            'visit_purpose_id': purpose.id,
            'visit_purpose': category,
        }
        if line.visit_id:
            line.visit_id.write(vals)
            if category == 'marketing':
                return line.visit_id.action_open_marketing_quick_popup()
            return line.visit_id.action_open_visit_form()
        visit = self.env['sales.route.visit'].create({
            'plan_line_id': line.id,
            'plan_id': line.plan_id.id,
            'route_id': line.route_id.id,
            'partner_id': line.partner_id.id,
            'user_id': line.user_id.id,
            'visit_purpose_id': purpose.id,
            'visit_purpose': category,
        })
        line.write({
            'visit_id': visit.id,
            'expected_visit_purpose': category if category in ['marketing', 'sales', 'delivery', 'merchandising', 'retail_sales', 'other'] else 'other',
            'expected_visit_purpose_id': purpose.id,
        })
        if category == 'marketing':
            return visit.action_open_marketing_quick_popup()
        return visit.action_open_visit_form()
