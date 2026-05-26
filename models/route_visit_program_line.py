from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SalesRouteVisitProgramLine(models.Model):
    _name = 'sales.route.visit.program.line'
    _description = 'Visit Program / Catalogue Count Line'
    _order = 'program_id, id'

    visit_id = fields.Many2one('sales.route.visit', string='Visit', required=True, ondelete='cascade', index=True)
    program_id = fields.Many2one('sales.route.marketing.program', string='Program / Catalogue', required=True, ondelete='restrict')
    response = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Issued?', default='no', required=True)
    count = fields.Integer(string='Count', default=0)
    note = fields.Char(string='Note')

    @api.onchange('response')
    def _onchange_response(self):
        for rec in self:
            if rec.response == 'yes':
                rec.count = 1
            elif rec.response == 'no':
                rec.count = 0

    @api.constrains('count')
    def _check_count(self):
        for rec in self:
            if rec.count < 0:
                raise ValidationError(_('Program / catalogue count cannot be negative.'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            response = vals.get('response', 'no')
            if response == 'yes':
                vals['count'] = 1
            elif response == 'no':
                vals['count'] = 0
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if vals.get('response') == 'yes':
            vals['count'] = 1
        elif vals.get('response') == 'no':
            vals['count'] = 0
        return super().write(vals)
