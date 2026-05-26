from datetime import timedelta

from odoo import api, fields, models, _


class FieldSalesDeviceStatus(models.Model):
    _name = 'sales.route.device.status'
    _description = 'Field Sales Device Status'
    _order = 'alert_level desc, last_seen desc, id desc'
    _rec_name = 'display_name'

    user_id = fields.Many2one('res.users', string='Salesperson', required=True, index=True, ondelete='cascade')
    route_id = fields.Many2one('sales.route', string='Current Route', index=True)
    plan_id = fields.Many2one('sales.route.plan', string='Current Route Plan', index=True)
    last_visit_id = fields.Many2one('sales.route.visit', string='Last Visit', index=True)
    last_seen = fields.Datetime(string='Last Seen', default=fields.Datetime.now, index=True)

    battery_supported = fields.Boolean(string='Battery Supported')
    battery_level = fields.Float(string='Battery Level %', digits=(5, 2), index=True)
    battery_charging = fields.Boolean(string='Charging')
    battery_status = fields.Selection([
        ('unknown', 'Unknown'),
        ('critical', 'Critical'),
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('charging', 'Charging'),
    ], string='Battery Status', compute='_compute_statuses', store=True, index=True)

    network_online = fields.Boolean(string='Online', default=True, index=True)
    network_type = fields.Char(string='Network Type')
    effective_type = fields.Char(string='Effective Connection')
    downlink_mbps = fields.Float(string='Downlink Mbps')
    rtt_ms = fields.Integer(string='RTT ms')
    save_data = fields.Boolean(string='Data Saver')
    network_status = fields.Selection([
        ('offline', 'Offline'),
        ('poor', 'Poor'),
        ('fair', 'Fair'),
        ('good', 'Good'),
        ('unknown', 'Unknown'),
    ], string='Network Status', compute='_compute_statuses', store=True, index=True)

    # v8.3 smart monitoring fields
    is_stale = fields.Boolean(string='Inactive / Not Reporting', index=True, default=False)
    minutes_since_seen = fields.Float(string='Minutes Since Last Seen', digits=(10, 1), default=0.0)
    alert_level = fields.Selection([
        ('0_ok', 'OK'),
        ('1_warning', 'Warning'),
        ('2_critical', 'Critical'),
    ], string='Alert Level', default='0_ok', index=True)
    alert_message = fields.Char(string='Smart Alert')
    alert_acknowledged = fields.Boolean(string='Acknowledged', default=False, index=True)
    last_alert_at = fields.Datetime(string='Last Alert At')

    page_url = fields.Char(string='Last Page')
    user_agent = fields.Char(string='Device / Browser')
    platform = fields.Char(string='Platform')
    device_note = fields.Char(string='Device Note')
    display_name = fields.Char(string='Name', compute='_compute_display_name', store=True)

    @api.depends('user_id', 'last_seen')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s - %s' % (rec.user_id.name or 'User', rec.last_seen or '')

    @api.depends('battery_level', 'battery_charging', 'battery_supported', 'network_online', 'effective_type', 'downlink_mbps')
    def _compute_statuses(self):
        for rec in self:
            if rec.battery_charging:
                rec.battery_status = 'charging'
            elif not rec.battery_supported and not rec.battery_level:
                rec.battery_status = 'unknown'
            elif rec.battery_level <= 15:
                rec.battery_status = 'critical'
            elif rec.battery_level <= 30:
                rec.battery_status = 'low'
            else:
                rec.battery_status = 'normal'

            if not rec.network_online:
                rec.network_status = 'offline'
            elif rec.effective_type in ('slow-2g', '2g') or (rec.downlink_mbps and rec.downlink_mbps < 0.5):
                rec.network_status = 'poor'
            elif rec.effective_type == '3g' or (rec.downlink_mbps and rec.downlink_mbps < 2):
                rec.network_status = 'fair'
            elif rec.effective_type or rec.downlink_mbps:
                rec.network_status = 'good'
            else:
                rec.network_status = 'unknown'

    def _smart_alert_values(self):
        """Return smart monitoring alert values for a single status row.

        Browser APIs do not expose exact data usage, so alerting is based on
        network availability/quality and battery health.
        """
        self.ensure_one()
        now = fields.Datetime.now()
        minutes = 0.0
        if self.last_seen:
            delta = now - self.last_seen
            minutes = round(max(delta.total_seconds(), 0) / 60.0, 1)

        messages = []
        level = '0_ok'
        stale = minutes >= 30

        if stale:
            level = '2_critical'
            messages.append(_('No device update for %.0f minutes') % minutes)
        if not self.network_online or self.network_status == 'offline':
            level = '2_critical'
            messages.append(_('Offline'))
        elif self.network_status == 'poor':
            level = max(level, '1_warning')
            messages.append(_('Poor network'))
        elif self.network_status == 'fair':
            level = max(level, '1_warning')
            messages.append(_('Fair network'))

        if self.battery_status == 'critical':
            level = '2_critical'
            messages.append(_('Critical battery %.0f%%') % (self.battery_level or 0.0))
        elif self.battery_status == 'low':
            level = max(level, '1_warning')
            messages.append(_('Low battery %.0f%%') % (self.battery_level or 0.0))

        if self.save_data:
            messages.append(_('Data saver enabled'))
            level = max(level, '1_warning')

        if not messages:
            messages.append(_('Device OK'))

        return {
            'minutes_since_seen': minutes,
            'is_stale': stale,
            'alert_level': level,
            'alert_message': ' • '.join(messages),
            'last_alert_at': now if level != '0_ok' else self.last_alert_at,
            'alert_acknowledged': self.alert_acknowledged if level != '0_ok' else False,
        }

    def action_refresh_smart_alerts(self):
        for rec in self:
            rec.write(rec._smart_alert_values())
        return True

    def action_acknowledge_alert(self):
        self.write({'alert_acknowledged': True})
        return True

    def action_clear_acknowledgement(self):
        self.write({'alert_acknowledged': False})
        return True

    @api.model
    def cron_refresh_device_alerts(self):
        records = self.sudo().search([])
        records.action_refresh_smart_alerts()
        return True

    @api.model
    def create_or_update_from_payload(self, payload):
        user = self.env.user
        today = fields.Date.context_today(user)
        plan = self.env['sales.route.plan'].sudo().search([('plan_date', '=', today), ('user_id', '=', user.id)], order='id desc', limit=1)
        last_visit = self.env['sales.route.visit'].sudo().search([('user_id', '=', user.id)], order='check_in desc, id desc', limit=1)
        values = {
            'user_id': user.id,
            'route_id': plan.route_id.id if plan and plan.route_id else False,
            'plan_id': plan.id if plan else False,
            'last_visit_id': last_visit.id if last_visit else False,
            'last_seen': fields.Datetime.now(),
            'battery_supported': bool(payload.get('battery_supported')),
            'battery_level': float(payload.get('battery_level') or 0.0),
            'battery_charging': bool(payload.get('battery_charging')),
            'network_online': bool(payload.get('network_online', True)),
            'network_type': payload.get('network_type') or '',
            'effective_type': payload.get('effective_type') or '',
            'downlink_mbps': float(payload.get('downlink_mbps') or 0.0),
            'rtt_ms': int(payload.get('rtt_ms') or 0),
            'save_data': bool(payload.get('save_data')),
            'page_url': payload.get('page_url') or '',
            'user_agent': payload.get('user_agent') or '',
            'platform': payload.get('platform') or '',
            'device_note': payload.get('device_note') or '',
            'alert_acknowledged': False,
        }
        rec = self.sudo().search([('user_id', '=', user.id)], order='id desc', limit=1)
        if rec:
            rec.write(values)
        else:
            rec = self.sudo().create(values)
        rec.action_refresh_smart_alerts()
        return rec

    def action_open_user_visits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Route Visits',
            'res_model': 'sales.route.visit',
            'view_mode': 'tree,form',
            'domain': [('user_id', '=', self.user_id.id)],
            'target': 'current',
        }
