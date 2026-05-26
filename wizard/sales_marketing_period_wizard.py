from odoo import api, fields, models, _


class SalesMarketingPeriodWizard(models.TransientModel):
    _name = 'sales.marketing.period.wizard'
    _description = 'Sales / Marketing Period Selector'

    period_selection = fields.Selection([
        ('today', 'Today'),
        ('current', 'Current Sales / Marketing Period'),
        ('jan_apr', 'January to April'),
        ('may_aug', 'May to August'),
        ('sep_dec', 'September to December'),
        ('custom', 'Custom Date Range'),
    ], string='Period', default='today', required=True)
    period_year = fields.Integer(string='Year', default=lambda self: fields.Date.context_today(self).year, required=True)
    custom_date_from = fields.Date(string='Custom From')
    custom_date_to = fields.Date(string='Custom To')

    @api.onchange('period_selection')
    def _onchange_period_selection(self):
        today = fields.Date.context_today(self)
        if self.period_selection == 'today':
            self.custom_date_from = False
            self.custom_date_to = False
        if self.period_selection == 'custom' and not self.custom_date_from:
            self.custom_date_from = today.replace(day=1)
            self.custom_date_to = today

    def action_apply_to_profiles(self):
        self.ensure_one()
        ctx = dict(self.env.context or {})
        ctx.update({
            'fsrp_period_key': self.period_selection,
            'fsrp_period_year': self.period_year,
        })
        if self.period_selection == 'custom':
            ctx.update({
                'fsrp_date_from': self.custom_date_from,
                'fsrp_date_to': self.custom_date_to,
            })
        action = self.env.ref('field_sales_route_plan.action_sales_person_profile').sudo().read()[0]
        action['context'] = ctx
        return action
