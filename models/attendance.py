from math import radians, sin, cos, sqrt, atan2
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalesRouteAttendance(models.Model):
    _name = 'sales.route.attendance'
    _description = 'Field Staff Attendance and Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_time desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    user_id = fields.Many2one('res.users', string='Salesperson', default=lambda self: self.env.user, required=True, index=True)
    route_id = fields.Many2one('sales.route', string='Route', index=True)
    attendance_date = fields.Date(default=fields.Date.context_today, required=True, index=True)
    start_time = fields.Datetime(readonly=True, tracking=True)
    end_time = fields.Datetime(readonly=True, tracking=True)
    start_latitude = fields.Float(digits=(16, 7), readonly=True)
    start_longitude = fields.Float(digits=(16, 7), readonly=True)
    end_latitude = fields.Float(digits=(16, 7), readonly=True)
    end_longitude = fields.Float(digits=(16, 7), readonly=True)
    start_place = fields.Char(readonly=True)
    end_place = fields.Char(readonly=True)
    duration_hours = fields.Float(compute='_compute_duration', store=True)
    state = fields.Selection([('open', 'Started'), ('closed', 'Ended')], default='open', tracking=True)

    @api.depends('user_id', 'attendance_date')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s - %s' % (rec.user_id.name or 'Salesperson', rec.attendance_date or '')

    @api.depends('start_time', 'end_time')
    def _compute_duration(self):
        for rec in self:
            rec.duration_hours = ((rec.end_time - rec.start_time).total_seconds() / 3600.0) if rec.start_time and rec.end_time else 0.0

    @api.model
    def start_day(self, latitude=False, longitude=False, place=False, route_id=False):
        existing = self.search([('user_id', '=', self.env.user.id), ('attendance_date', '=', fields.Date.context_today(self)), ('state', '=', 'open')], limit=1)
        if existing:
            return existing
        return self.create({
            'user_id': self.env.user.id,
            'route_id': route_id or False,
            'start_time': fields.Datetime.now(),
            'start_latitude': latitude or 0.0,
            'start_longitude': longitude or 0.0,
            'start_place': place or '',
            'state': 'open',
        })

    def action_end_day(self):
        for rec in self:
            rec.write({'end_time': fields.Datetime.now(), 'state': 'closed'})
        return True
