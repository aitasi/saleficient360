from odoo import fields, models


class SalesRouteMarketingProgram(models.Model):
    _name = 'sales.route.marketing.program'
    _description = 'Field Sales Marketing Program / Product Catalogue'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char()
    active = fields.Boolean(default=True)
    product_ids = fields.Many2many('product.product', string='Products / SKUs')
    attachment_ids = fields.Many2many('ir.attachment', string='Catalogue Files')
    description = fields.Text()
