from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalesRouteQuickPlanWizard(models.TransientModel):
    _name = 'sales.route.quick.plan.wizard'
    _description = 'Quick Mobile Route Plan Wizard'

    plan_date = fields.Date(required=True, default=fields.Date.context_today)
    user_id = fields.Many2one('res.users', string='Salesperson', required=True, default=lambda self: self.env.user)
    route_id = fields.Many2one('sales.route', string='Market Route', required=True, domain="[('active','=',True)]")
    supervisor_id = fields.Many2one('res.users', string='Supervisor', readonly=True, help='Automatically selected from the supervisors configured on the selected market route.')
    planned_productive_calls = fields.Integer(string='Productive Target', default=10, required=True)
    selection_mode = fields.Selection([
        ('manual', 'Choose clients'),
        ('all_route', 'All clients on route'),
    ], string='Clients to Add', default='manual', required=True)
    partner_ids = fields.Many2many(
        'res.partner',
        'sales_route_quick_plan_partner_rel',
        'wizard_id', 'partner_id',
        string='Selected Route Clients',
        domain="[('route_id','=',route_id), ('customer_rank','>',0)]",
    )
    global_partner_ids = fields.Many2many(
        'res.partner',
        'sales_route_quick_plan_global_partner_rel',
        'wizard_id', 'partner_id',
        string='Extra Clients From Any Route',
        domain="[('customer_rank','>',0), ('active','=',True)]",
        help='Adds these clients to this route plan only. Their original market route is not changed.',
    )
    add_to_existing = fields.Boolean(string='Use existing plan for today if available', default=True)
    auto_sequence = fields.Boolean(string='Auto sequence clients', default=True)
    default_visit_purpose_id = fields.Many2one(
        'sales.route.visit.purpose',
        string='Default Visit Purpose',
        default=lambda self: self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False),
    )
    default_call_type = fields.Selection([
        ('productive', 'Possible Productive'),
        ('unproductive', 'Possible Unproductive'),
    ], string='Default Call Type', default='productive', required=True)
    available_client_count = fields.Integer(compute='_compute_counts')
    selected_client_count = fields.Integer(compute='_compute_counts')

    @api.depends('route_id', 'partner_ids', 'global_partner_ids', 'selection_mode')
    def _compute_counts(self):
        for wizard in self:
            wizard.available_client_count = len(wizard.route_id.partner_ids.filtered(lambda p: p.customer_rank > 0)) if wizard.route_id else 0
            if wizard.selection_mode == 'all_route':
                wizard.selected_client_count = wizard.available_client_count + len(wizard.global_partner_ids)
            else:
                wizard.selected_client_count = len(wizard.partner_ids | wizard.global_partner_ids)

    @api.onchange('route_id')
    def _onchange_route_id(self):
        for wizard in self:
            if wizard.route_id:
                if wizard.route_id.user_ids and self.env.user in wizard.route_id.user_ids:
                    wizard.user_id = self.env.user
                elif wizard.route_id.user_id:
                    wizard.user_id = wizard.route_id.user_id
                elif wizard.route_id.user_ids:
                    wizard.user_id = wizard.route_id.user_ids[0]
                supervisor = wizard._get_route_supervisor(wizard.route_id)
                wizard.supervisor_id = supervisor
                if wizard.selection_mode == 'manual':
                    wizard.partner_ids = [(5, 0, 0)]

    def _get_route_supervisor(self, route):
        self.ensure_one()
        if not route:
            return False
        supervisors = route.supervisor_ids
        if self.env.user in supervisors:
            return self.env.user
        if supervisors:
            return supervisors[0]
        hierarchy = self.env['sales.route.team.hierarchy'].sudo().search([('salesperson_id', '=', self.user_id.id), ('active', '=', True)], limit=1)
        return hierarchy.supervisor_id if hierarchy else False

    def _get_clients(self):
        self.ensure_one()
        if self.selection_mode == 'all_route':
            clients = self.route_id.partner_ids.filtered(lambda p: p.customer_rank > 0 and p.active)
        else:
            clients = self.partner_ids
        # Extra/global clients are deliberately added to the plan only.
        # Do not write route_id/user_id on these partners, so they keep their original market route.
        clients = (clients | self.global_partner_ids).filtered(lambda p: p.customer_rank > 0 and p.active)
        clients = clients.sorted(lambda p: (p.name or '').lower())
        if not clients:
            raise UserError(_('No clients found for this route plan. Add clients to the route or select clients manually.'))
        return clients

    def _prepare_line_vals(self, plan, partner, sequence, is_global_client=False):
        self.ensure_one()
        # Out-of-route/global clients must be marked as ad-hoc so the
        # route membership constraint allows them on this plan without
        # changing their original market route assignment.
        vals = {
            'plan_id': plan.id,
            'sequence': sequence,
            'partner_id': partner.id,
            'expected_call_type': self.default_call_type,
            'is_ad_hoc': bool(is_global_client or (partner.route_id and partner.route_id != plan.route_id)),
        }
        if self.default_visit_purpose_id:
            vals['expected_visit_purpose_id'] = self.default_visit_purpose_id.id
            vals['expected_visit_purpose'] = self.default_visit_purpose_id.category or 'sales'
        return vals

    def _create_or_update_plan(self):
        self.ensure_one()
        clients = self._get_clients()
        Plan = self.env['sales.route.plan']
        Line = self.env['sales.route.plan.line']
        plan = False
        if self.add_to_existing:
            plan = Plan.search([
                ('plan_date', '=', self.plan_date),
                ('user_id', '=', self.user_id.id),
                ('route_id', '=', self.route_id.id),
                ('state', '!=', 'cancelled'),
            ], limit=1)
        if plan and plan.state != 'draft':
            raise UserError(_('This route plan has already been submitted or approved. Create a new draft plan or ask a supervisor to update it.'))
        if not plan:
            supervisor = self.supervisor_id or self._get_route_supervisor(self.route_id)
            plan = Plan.create({
                'plan_date': self.plan_date,
                'user_id': self.user_id.id,
                'route_id': self.route_id.id,
                'supervisor_id': supervisor.id if supervisor else False,
                'planned_productive_calls': self.planned_productive_calls,
            })
        else:
            supervisor = self.supervisor_id or self._get_route_supervisor(self.route_id)
            vals = {'planned_productive_calls': self.planned_productive_calls}
            if supervisor and not plan.supervisor_id:
                vals['supervisor_id'] = supervisor.id
            plan.write(vals)

        existing_partner_ids = set(plan.line_ids.mapped('partner_id').ids)
        sequence = (max(plan.line_ids.mapped('sequence') or [0]) + 10)
        global_partner_ids = set(self.global_partner_ids.ids)
        for partner in clients:
            if partner.id in existing_partner_ids:
                continue
            is_global_client = partner.id in global_partner_ids or (partner.route_id and partner.route_id != self.route_id)
            Line.create(self._prepare_line_vals(plan, partner, sequence, is_global_client=is_global_client))
            sequence += 10
        if plan.state == 'draft':
            plan.action_submit()
        return plan

    def action_create_plan(self):
        plan = self._create_or_update_plan()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Daily Route Plan'),
            'res_model': 'sales.route.plan',
            'view_mode': 'form',
            'res_id': plan.id,
            'target': 'current',
        }

    def action_create_and_start(self):
        # Kept for backward compatibility with any cached/stale button metadata.
        # New route plans must always be approved before visits can start.
        plan = self._create_or_update_plan()
        raise UserError(_('Route plan created and submitted for approval. It must be approved before Start My Day or any visit can be used.'))
