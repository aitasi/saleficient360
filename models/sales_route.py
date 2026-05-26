from odoo import api, fields, models, _, SUPERUSER_ID
from odoo.exceptions import AccessError


class SalesRoute(models.Model):
    _name = 'sales.route'
    _description = 'Market Sales Route'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    area = fields.Char(tracking=True)
    user_id = fields.Many2one('res.users', string='Primary Salesperson', tracking=True, help='Primary/default salesperson for this route. Kept for compatibility.')
    user_ids = fields.Many2many('res.users', 'sales_route_user_rel', 'route_id', 'user_id', string='Assigned Salespersons', tracking=True, help='All salespeople allowed to work on this market route.')
    supervisor_ids = fields.Many2many('res.users', 'sales_route_supervisor_rel', 'route_id', 'user_id', string='Assigned Supervisors', tracking=True, help='Supervisors responsible for managing this route. A supervisor can manage several routes.')
    team_id = fields.Many2one('crm.team', string='Sales Team')
    active = fields.Boolean(default=True)
    partner_ids = fields.One2many('res.partner', 'route_id', string='Customers')
    partner_count = fields.Integer(compute='_compute_counts')
    plan_count = fields.Integer(compute='_compute_counts')
    visit_count = fields.Integer(compute='_compute_counts')
    note = fields.Text()
    # Legacy compatibility placeholder: older experimental VAN builds may have left
    # stale views referencing van_ids. This field is intentionally empty and is
    # not shown in the clean core views. It prevents upgrade validation crashes
    # while keeping VAN Sales removed from the module.
    van_ids = fields.Many2many('res.partner', string='Legacy VAN Placeholder', compute='_compute_empty_legacy_van_ids', readonly=True)

    def _compute_empty_legacy_van_ids(self):
        for route in self:
            route.van_ids = [(5, 0, 0)]

    @api.depends('partner_ids')
    def _compute_counts(self):
        Plan = self.env['sales.route.plan']
        Visit = self.env['sales.route.visit']
        for route in self:
            route.partner_count = len(route.partner_ids)
            route.plan_count = Plan.search_count([('route_id', '=', route.id)])
            route.visit_count = Visit.search_count([('route_id', '=', route.id)])

    def action_view_customers(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Route Customers'),
            'res_model': 'res.partner',
            'view_mode': 'tree,form',
            'domain': [('route_id', '=', self.id)],
            'context': {'default_route_id': self.id, 'default_user_id': self.user_id.id or self.env.user.id},
        }


    def action_add_existing_partners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Existing Customers'),
            'res_model': 'sales.route.add.partner.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_route_id': self.id},
        }


    @api.model_create_multi
    def create(self, vals_list):
        # Market routes are master data. Salespeople may select existing routes
        # when creating clients/plans, but only supervisors/managers/admins may
        # create new market routes from any screen, including many2one quick-create.
        if self.env.uid != SUPERUSER_ID and not (
            self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor')
            or self.env.user.has_group('field_sales_route_plan.group_field_sales_manager')
            or self.env.user.has_group('base.group_system')
        ):
            raise AccessError(_('Only Field Sales Supervisors or Managers can create new Market Routes. Please select an existing route.'))
        routes = super().create(vals_list)
        for route, vals in zip(routes, vals_list):
            route._sync_primary_salesperson_to_team()
        return routes

    def write(self, vals):
        res = super().write(vals)
        if {'user_id', 'user_ids'} & set(vals):
            self._sync_primary_salesperson_to_team()
        return res

    def _sync_primary_salesperson_to_team(self):
        """Keep the legacy primary salesperson included in the new multi-salesperson list."""
        for route in self:
            if route.user_id and route.user_id not in route.user_ids:
                route.user_ids = [(4, route.user_id.id)]
            if not route.user_id and route.user_ids:
                route.user_id = route.user_ids[0].id


class SalesRouteCustomerHistory(models.Model):
    _name = 'sales.route.customer.history'
    _description = 'Route Customer Assignment History'
    _order = 'date_from desc'

    partner_id = fields.Many2one('res.partner', required=True, ondelete='cascade')
    route_id = fields.Many2one('sales.route', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Salesperson')
    date_from = fields.Date(default=fields.Date.context_today, required=True)
    date_to = fields.Date()
    active = fields.Boolean(default=True)
