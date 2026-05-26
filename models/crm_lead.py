from odoo import fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    route_visit_id = fields.Many2one('sales.route.visit', string='Route Visit')
    route_plan_id = fields.Many2one('sales.route.plan', string='Daily Route Plan')
    route_id = fields.Many2one('sales.route', string='Market Route')
