from odoo import fields, models


class SalesRouteCallReason(models.Model):
    _name = 'sales.route.call.reason'
    _description = 'Field Sales Unproductive Call Reason'
    _order = 'sequence, name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    category = fields.Selection([
        ('closed', 'Client Closed'),
        ('no_cash', 'No Cash / Credit Issue'),
        ('stock', 'No Requirement / Still Stocked'),
        ('owner_absent', 'Owner/Buyer Absent'),
        ('competitor', 'Competitor Supplied'),
        ('bad_debt', 'Bad Debt / Blocked Client'),
        ('other', 'Other'),
    ], default='other', required=True)
