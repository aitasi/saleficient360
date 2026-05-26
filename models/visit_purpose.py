from odoo import fields, models


class SalesRouteVisitPurpose(models.Model):
    _name = 'sales.route.visit.purpose'
    _description = 'Field Visit Purpose'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(help='Optional short code, e.g. marketing, sales, delivery.')
    category = fields.Selection([
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('delivery', 'Delivery'),
        ('merchandising', 'Merchandising'),
        ('retail_sales', 'Retail Sales Visit'),
        ('van_sales', 'Van Sales'),
        ('other', 'Other'),
    ], string='Purpose Type', required=True, default='other',
       help='Controls which visit screen is shown. Custom purposes can use Other unless they should behave like Marketing, Sales, Delivery, Merchandising, Retail Sales, or Van Sales.')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
