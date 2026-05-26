from odoo import fields, models


class SalesRouteMarketingHistory(models.Model):
    _name = 'sales.route.marketing.history'
    _description = 'Client Marketing History'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'visit_date desc, id desc'

    name = fields.Char(required=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, index=True, ondelete='cascade')
    visit_id = fields.Many2one('sales.route.visit', string='Visit', ondelete='set null')
    plan_id = fields.Many2one('sales.route.plan', string='Daily Plan')
    route_id = fields.Many2one('sales.route', string='Market Route')
    user_id = fields.Many2one('res.users', string='Salesperson')
    visit_date = fields.Datetime(default=fields.Datetime.now)
    program_issued = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Program Issued?')
    program_custom_count = fields.Integer(string='Other Program Count')
    program_count = fields.Integer(string='Program Count')
    program_id = fields.Many2one('sales.route.marketing.program', string='Program / Catalogue Issued')
    program_ids = fields.Many2many('sales.route.marketing.program', 'sales_route_marketing_history_program_rel', 'history_id', 'program_id', string='Programs / Catalogues Issued')
    contact_person_name = fields.Char()
    contact_person_phone = fields.Char()
    contact_person_email = fields.Char()
    opportunity_id = fields.Many2one('crm.lead', string='Opportunity')
    activity_summary = fields.Char(string='Follow-up / Activity Summary')
    activity_date_deadline = fields.Date(string='Follow-up Due Date')
    notes = fields.Text(string='Client Communication / Notes')

    # Manager intelligence helpers. These are lightweight related/computed fields so
    # the Marketing History workspace can show route/client context without heavy
    # dashboard calculations.
    visit_purpose = fields.Selection(related='visit_id.visit_purpose', string='Visit Purpose Type', readonly=True)
    visit_purpose_id = fields.Many2one(related='visit_id.visit_purpose_id', string='Visit Purpose', readonly=True)
    last_purchase_date = fields.Date(related='partner_id.last_purchase_date', string='Last Purchase', readonly=True)
    days_since_last_purchase = fields.Integer(related='partner_id.days_since_last_purchase', string='Days Since Last Purchase', readonly=True)
    route_age_bucket = fields.Selection(related='partner_id.route_age_bucket', string='Client Sales Aging', readonly=True)
    customer_classification = fields.Selection(related='partner_id.customer_classification', string='Client Class', readonly=True)
    route_sales_potential = fields.Float(related='partner_id.route_sales_potential', string='Sales Potential', readonly=True)
    client_phone = fields.Char(related='partner_id.phone', string='Client Phone', readonly=True)
    client_mobile = fields.Char(related='partner_id.mobile', string='Client Mobile', readonly=True)
