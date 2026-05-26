from odoo import api, fields, models, _


class SalesRouteGameScore(models.Model):
    _name = 'sales.route.game.score'
    _description = 'Field Sales Gamification Score'
    _order = 'score_date desc, total_points desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    user_id = fields.Many2one('res.users', string='Salesperson', required=True, index=True)
    route_id = fields.Many2one('sales.route', string='Route', index=True)
    score_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    visits_done = fields.Integer()
    productive_calls = fields.Integer()
    sales_amount = fields.Monetary(currency_field='currency_id')
    total_points = fields.Integer(compute='_compute_points', store=True)
    badge = fields.Selection([
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('champion', 'Champion'),
    ], compute='_compute_points', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('user_id', 'score_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (rec.user_id.name or 'Salesperson', rec.score_date or '')

    @api.depends('visits_done', 'productive_calls', 'sales_amount')
    def _compute_points(self):
        for rec in self:
            points = (rec.visits_done or 0) * 10 + (rec.productive_calls or 0) * 20 + int((rec.sales_amount or 0.0) / 10000.0)
            rec.total_points = points
            if points >= 300:
                rec.badge = 'champion'
            elif points >= 200:
                rec.badge = 'gold'
            elif points >= 100:
                rec.badge = 'silver'
            else:
                rec.badge = 'bronze'

    @api.model
    def refresh_scores_for_today(self):
        today = fields.Date.context_today(self)
        users = self.env['res.users'].search([('share', '=', False)])
        Visit = self.env['sales.route.visit'].sudo()
        for user in users:
            visits = Visit.search([('user_id', '=', user.id), ('check_in', '>=', fields.Datetime.to_string(today))])
            vals = {
                'visits_done': len(visits.filtered(lambda v: v.state == 'checked_out')),
                'productive_calls': len(visits.filtered(lambda v: v.sale_order_total_amount > 0)),
                'sales_amount': sum(visits.mapped('sale_order_total_amount')),
            }
            score = self.search([('user_id', '=', user.id), ('score_date', '=', today)], limit=1)
            if score:
                score.write(vals)
            elif any(vals.values()):
                vals.update({'user_id': user.id, 'score_date': today})
                self.create(vals)
