from odoo import api, fields, models, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    route_id = fields.Many2one('sales.route', string='Market Route', tracking=True)
    route_user_id = fields.Many2one(related='route_id.user_id', string='Primary Route Salesperson', store=True, readonly=True)
    visit_frequency = fields.Selection([
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('adhoc', 'Ad-hoc'),
    ], default='weekly', string='Visit Frequency')
    route_date_added = fields.Date(default=fields.Date.context_today, string='Date Added to Route')
    customer_latitude = fields.Float(string='Customer Latitude', digits=(16, 7))
    customer_longitude = fields.Float(string='Customer Longitude', digits=(16, 7))
    last_route_visit_id = fields.Many2one('sales.route.visit', compute='_compute_route_stats', string='Last Route Visit')
    last_route_visit_date = fields.Datetime(compute='_compute_route_stats', string='Last Visit Date')
    last_purchase_date = fields.Date(compute='_compute_route_stats', string='Last Purchase Date')
    days_since_last_purchase = fields.Integer(compute='_compute_route_stats', string='Days Since Last Purchase')
    route_customer_age_days = fields.Integer(compute='_compute_route_stats', string='Days on Route')
    customer_classification = fields.Selection([
        ('key_account', 'Key Account'),
        ('wholesale', 'Wholesale'),
        ('retail', 'Retail'),
        ('dormant', 'Dormant'),
        ('new', 'New Customer'),
        ('high_potential', 'High Potential'),
    ], string='Customer Classification', default='retail', tracking=True)
    route_age_bucket = fields.Selection([
        ('never_bought', 'Never Bought'),
        ('today', 'Bought Today'),
        ('7_days', '7 Days Inactive'),
        ('14_days', '14 Days Inactive'),
        ('30_days', '30+ Days Inactive'),
    ], compute='_compute_route_stats', string='Ageing Bucket')
    route_sales_potential = fields.Float(string='Estimated Monthly Potential')

    @api.depends('route_date_added')
    def _compute_route_stats(self):
        today = fields.Date.context_today(self)
        SaleOrder = self.env['sale.order']
        Visit = self.env['sales.route.visit']
        for partner in self:
            last_visit = Visit.search([('partner_id', '=', partner.id), ('check_in', '!=', False)], order='check_in desc', limit=1)
            partner.last_route_visit_id = last_visit.id
            partner.last_route_visit_date = last_visit.check_in
            last_order = SaleOrder.search([
                ('partner_id', 'child_of', partner.id),
                ('state', 'in', ['sale', 'done']),
            ], order='date_order desc', limit=1)
            last_purchase = fields.Date.to_date(last_order.date_order) if last_order else False
            partner.last_purchase_date = last_purchase
            partner.days_since_last_purchase = (today - last_purchase).days if last_purchase else 0
            partner.route_customer_age_days = (today - partner.route_date_added).days if partner.route_date_added else 0
            if not last_purchase:
                partner.route_age_bucket = 'never_bought'
            else:
                days = (today - last_purchase).days
                if days == 0:
                    partner.route_age_bucket = 'today'
                elif days <= 7:
                    partner.route_age_bucket = '7_days'
                elif days <= 14:
                    partner.route_age_bucket = '14_days'
                else:
                    partner.route_age_bucket = '30_days'


    marketing_history_ids = fields.One2many('sales.route.marketing.history', 'partner_id', string='Marketing History')
    marketing_history_count = fields.Integer(compute='_compute_marketing_history_count', string='Marketing Notes')

    def _compute_marketing_history_count(self):
        for partner in self:
            partner.marketing_history_count = len(partner.marketing_history_ids)

    def action_view_marketing_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marketing History'),
            'res_model': 'sales.route.marketing.history',
            'view_mode': 'tree,form',
            'domain': [('partner_id', '=', self.id)],
            'context': {'default_partner_id': self.id},
        }

    def get_route_map_coordinates(self):
        """Return the best client coordinates for route maps/compliance.

        Priority:
        1) This module's assigned client coordinates (customer_latitude/customer_longitude).
        2) Odoo/geolocalize partner coordinates (partner_latitude/partner_longitude) when available.
        3) Last route visit check-in GPS as fallback.
        """
        self.ensure_one()
        lat = self.customer_latitude or 0.0
        lon = self.customer_longitude or 0.0
        source = 'client_assigned' if lat and lon else False

        if not (lat and lon) and 'partner_latitude' in self._fields and 'partner_longitude' in self._fields:
            lat = self.partner_latitude or 0.0
            lon = self.partner_longitude or 0.0
            source = 'partner_geolocation' if lat and lon else False

        if not (lat and lon):
            last_visit = self.env['sales.route.visit'].sudo().search([
                ('partner_id', '=', self.id),
                ('checkin_latitude', '!=', 0),
                ('checkin_longitude', '!=', 0),
            ], order='check_in desc, id desc', limit=1)
            if last_visit:
                lat = last_visit.checkin_latitude or 0.0
                lon = last_visit.checkin_longitude or 0.0
                source = 'last_visit_gps' if lat and lon else False

        return {
            'latitude': lat or 0.0,
            'longitude': lon or 0.0,
            'source': source or 'none',
            'has_location': bool(lat and lon),
        }

    def write(self, vals):
        route_changed = 'route_id' in vals or 'user_id' in vals
        res = super().write(vals)
        if route_changed:
            for partner in self.filtered(lambda p: p.route_id):
                self.env['sales.route.customer.history'].create({
                    'partner_id': partner.id,
                    'route_id': partner.route_id.id,
                    'user_id': partner.route_id.user_id.id or partner.user_id.id,
                    'date_from': fields.Date.context_today(self),
                })
        return res

    def _field_sales_find_auto_route(self, vals=None):
        """Find the best sales route for a customer from assigned salesperson/team.

        Priority:
        1) Explicit salesperson route.
        2) Explicit sales team route.
        3) Existing partner salesperson route.
        4) Existing partner team route.
        """
        self.ensure_one()
        vals = vals or {}
        Route = self.env['sales.route'].sudo()
        user_id = vals.get('user_id') or self.user_id.id
        team_id = vals.get('team_id') or self.team_id.id if 'team_id' in self._fields else False
        domain_base = [('active', '=', True)]
        route = False
        if user_id:
            route = Route.search(domain_base + ['|', ('user_id', '=', user_id), ('user_ids', 'in', [user_id])], limit=1)
        if not route and team_id:
            route = Route.search(domain_base + [('team_id', '=', team_id)], limit=1)
        return route

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner, vals in zip(partners, vals_list):
            if not vals.get('route_id') and (vals.get('team_id') or vals.get('user_id')):
                route = partner._field_sales_find_auto_route(vals)
                if route:
                    write_vals = {'route_id': route.id}
                    if route.user_id and not partner.user_id:
                        write_vals['user_id'] = route.user_id.id
                    if 'team_id' in partner._fields and route.team_id and not partner.team_id:
                        write_vals['team_id'] = route.team_id.id
                    partner.sudo().write(write_vals)
        return partners

    def write(self, vals):
        route_changed = 'route_id' in vals or 'user_id' in vals
        res = super(ResPartner, self).write(vals)
        # Automatically place new or updated customers into the matching market route when a sales team/salesperson is assigned.
        if 'route_id' not in vals and ('team_id' in vals or 'user_id' in vals):
            for partner in self.filtered(lambda p: not p.route_id and (p.customer_rank or p.parent_id)):
                route = partner._field_sales_find_auto_route(vals)
                if route:
                    write_vals = {'route_id': route.id}
                    if route.user_id and not partner.user_id:
                        write_vals['user_id'] = route.user_id.id
                    if 'team_id' in partner._fields and route.team_id and not partner.team_id:
                        write_vals['team_id'] = route.team_id.id
                    partner.sudo().write(write_vals)
        if route_changed:
            for partner in self.filtered(lambda p: p.route_id):
                self.env['sales.route.customer.history'].sudo().create({
                    'partner_id': partner.id,
                    'route_id': partner.route_id.id,
                    'user_id': partner.route_id.user_id.id or partner.user_id.id,
                    'date_from': fields.Date.context_today(self),
                })
        return res
