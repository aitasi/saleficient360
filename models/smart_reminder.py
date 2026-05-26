from odoo import api, fields, models, _


class SalesRouteSmartReminder(models.Model):
    _name = 'sales.route.smart.reminder'
    _description = 'Field Sales Smart Reminder'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date asc, priority desc, id desc'

    name = fields.Char(required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user, index=True)
    partner_id = fields.Many2one('res.partner', string='Client', index=True)
    route_id = fields.Many2one('sales.route', string='Route', index=True)
    visit_id = fields.Many2one('sales.route.visit', string='Visit')
    reminder_type = fields.Selection([
        ('revisit', 'Revisit'),
        ('no_purchase', 'No Purchase Follow-up'),
        ('delivery', 'Delivery Follow-up'),
        ('custom', 'Custom'),
    ], default='custom', required=True)
    priority = fields.Selection([('low', 'Low'), ('normal', 'Normal'), ('high', 'High')], default='normal')
    due_date = fields.Date(default=fields.Date.context_today, index=True)
    due_date_stop = fields.Date(string='End Date', default=fields.Date.context_today, index=True)
    state = fields.Selection([('open', 'Open'), ('done', 'Done'), ('cancelled', 'Cancelled')], default='open', index=True, tracking=True)
    note = fields.Text()

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    @api.model
    def create_from_visit(self, visit, reminder_type='revisit', days=7, note=False):
        return self.create({
            'name': _('Follow up %s') % (visit.partner_id.display_name or ''),
            'user_id': visit.user_id.id,
            'partner_id': visit.partner_id.id,
            'route_id': visit.route_id.id,
            'visit_id': visit.id,
            'reminder_type': reminder_type,
            'due_date': fields.Date.add(fields.Date.context_today(self), days=days),
            'note': note or '',
        })
