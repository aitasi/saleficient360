from odoo import api, fields, models, _


class SalesRouteMerchandisingAudit(models.Model):
    _name = 'sales.route.merchandising.audit'
    _description = 'Field Sales Merchandising Audit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'audit_date desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    visit_id = fields.Many2one('sales.route.visit', string='Visit', ondelete='cascade', index=True)
    route_id = fields.Many2one(related='visit_id.route_id', store=True, index=True)
    user_id = fields.Many2one(related='visit_id.user_id', store=True, index=True)
    partner_id = fields.Many2one(related='visit_id.partner_id', store=True, index=True)
    audit_date = fields.Datetime(default=fields.Datetime.now, required=True, index=True)
    shelf_available = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Our Products Visible?', default='yes')
    display_quality = fields.Selection([('excellent', 'Excellent'), ('good', 'Good'), ('fair', 'Fair'), ('poor', 'Poor')], default='good')
    competitor_visible = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Competitor Visible?', default='no')
    competitor_brand = fields.Char()
    before_photo = fields.Binary(string='Before Photo')
    before_photo_filename = fields.Char()
    after_photo = fields.Binary(string='After Photo')
    after_photo_filename = fields.Char()
    competitor_photo = fields.Binary(string='Competitor Photo')
    competitor_photo_filename = fields.Char()
    score = fields.Integer(string='Merchandising Score', default=0)
    notes = fields.Text()

    @api.depends('partner_id', 'audit_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s Merchandising Audit - %s' % (rec.partner_id.display_name or 'Client', rec.audit_date or '')
