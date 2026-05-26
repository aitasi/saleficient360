from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import html_escape


class SalesRoutePlan(models.Model):
    _name = 'sales.route.plan'
    _description = 'Daily Sales Route Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'plan_date desc, id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    plan_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True, index=True)
    user_id = fields.Many2one('res.users', string='Salesperson', required=True, default=lambda self: self.env.user, tracking=True, index=True)
    route_id = fields.Many2one('sales.route', required=True, tracking=True, index=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', tracking=True, index=True, help='Supervisor responsible for this route plan.')
    team_id = fields.Many2one('crm.team', related='route_id.team_id', store=True, readonly=True)
    planned_productive_calls = fields.Integer(default=10, required=True, tracking=True)
    planned_unproductive_calls = fields.Integer(default=0)
    line_ids = fields.One2many('sales.route.plan.line', 'plan_id', string='Planned Visits')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    total_planned_calls = fields.Integer(compute='_compute_kpis', store=True)
    productive_calls = fields.Integer(compute='_compute_kpis', store=True)
    unproductive_calls = fields.Integer(compute='_compute_kpis', store=True)
    missed_calls = fields.Integer(compute='_compute_kpis', store=True)
    visit_compliance = fields.Float(compute='_compute_kpis', store=True, string='Visited %')
    off_route_visits = fields.Integer(compute='_compute_kpis', store=True)
    suspicious_visits = fields.Integer(compute='_compute_kpis', store=True)
    checked_in_calls = fields.Integer(compute='_compute_kpis', store=True)
    kpi_achievement = fields.Float(compute='_compute_kpis', store=True, string='Productive KPI %')
    total_sales_amount = fields.Monetary(compute='_compute_kpis', store=True, currency_field='company_currency_id')
    mtd_visit_count = fields.Integer(string='MTD Visits', compute='_compute_period_kpis')
    ytd_visit_count = fields.Integer(string='YTD Visits', compute='_compute_period_kpis')
    mtd_sales_order_count = fields.Integer(string='MTD Sales Orders', compute='_compute_period_kpis')
    ytd_sales_order_count = fields.Integer(string='YTD Sales Orders', compute='_compute_period_kpis')
    mtd_sales_amount = fields.Monetary(string='MTD Sales', compute='_compute_period_kpis', currency_field='company_currency_id')
    ytd_sales_amount = fields.Monetary(string='YTD Sales', compute='_compute_period_kpis', currency_field='company_currency_id')
    next_client_id = fields.Many2one('res.partner', string='Next Client', compute='_compute_next_client')
    next_client_status = fields.Char(string='Next Client Status', compute='_compute_next_client')
    company_currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    unproductive_reason_id = fields.Many2one('sales.route.call.reason', string='Unproductive Reason')
    note = fields.Text()
    auto_assigned = fields.Boolean(string='System Assigned', default=False, tracking=True, index=True, help='This route plan was generated automatically by the system.')
    assignment_source = fields.Selection([
        ('manual', 'Manual'),
        ('system', 'System Auto Assignment'),
    ], default='manual', required=True, tracking=True, index=True)
    assignment_reason = fields.Text(string='Assignment Reason', readonly=True, help='Explains why the system selected this route and clients.')
    accepted_by_salesperson = fields.Boolean(string='Accepted by Salesperson', default=False, tracking=True)
    accepted_on = fields.Datetime(string='Accepted On', readonly=True)
    # Legacy compatibility placeholders for old VAN Sales views/metadata.
    # They are not used by the clean Field Sales Core UI.
    van_id = fields.Many2one('res.partner', string='Legacy VAN Placeholder', readonly=True)
    van_location_id = fields.Many2one('res.partner', string='Legacy VAN Location Placeholder', readonly=True)
    van_stock_status = fields.Char(string='Legacy VAN Stock Status', readonly=True)
    van_load_id = fields.Many2one('res.partner', string='Legacy VAN Load Placeholder', readonly=True)
    van_load_state = fields.Char(string='Legacy VAN Load State', readonly=True)
    van_reconciliation_id = fields.Many2one('res.partner', string='Legacy VAN Reconciliation Placeholder', readonly=True)
    van_reconciliation_state = fields.Char(string='Legacy VAN Reconciliation State', readonly=True)




    def _get_default_supervisor_for_route(self, route, salesperson=False):
        if not route:
            return False
        supervisors = route.supervisor_ids
        if self.env.user in supervisors:
            return self.env.user
        if supervisors:
            return supervisors[0]
        if salesperson:
            hierarchy = self.env['sales.route.team.hierarchy'].sudo().search([
                ('salesperson_id', '=', salesperson.id),
                ('active', '=', True),
            ], limit=1)
            return hierarchy.supervisor_id if hierarchy else False
        return False




    @api.model_create_multi
    def create(self, vals_list):
        self.env['sales.route.license'].check_access_or_raise()
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('sales.route.plan') or 'New'
            if not vals.get('supervisor_id') and vals.get('route_id'):
                route = self.env['sales.route'].browse(vals.get('route_id'))
                salesperson = self.env['res.users'].browse(vals.get('user_id')) if vals.get('user_id') else self.env.user
                supervisor = self._get_default_supervisor_for_route(route, salesperson)
                if supervisor:
                    vals['supervisor_id'] = supervisor.id
        records = super().create(vals_list)
        return records




    @api.depends('line_ids.status', 'line_ids.sale_order_ids.amount_total', 'planned_productive_calls')
    def _compute_kpis(self):
        for plan in self:
            lines = plan.line_ids
            plan.total_planned_calls = len(lines)
            plan.productive_calls = len(lines.filtered(lambda l: l.status == 'productive'))
            plan.unproductive_calls = len(lines.filtered(lambda l: l.status == 'unproductive'))
            plan.missed_calls = len(lines.filtered(lambda l: l.status == 'missed'))
            plan.checked_in_calls = len(lines.filtered(lambda l: l.status in ['checked_in', 'checked_out', 'productive', 'unproductive']))
            plan.kpi_achievement = (plan.productive_calls / plan.planned_productive_calls * 100.0) if plan.planned_productive_calls else 0.0
            plan.visit_compliance = (plan.checked_in_calls / plan.total_planned_calls * 100.0) if plan.total_planned_calls else 0.0
            visits = lines.mapped('visit_id')
            plan.off_route_visits = len(visits.filtered(lambda v: v.check_in and not v.within_allowed_radius))
            plan.suspicious_visits = len(visits.filtered(lambda v: v.suspicious_visit))
            plan.total_sales_amount = sum(lines.mapped('sale_order_ids.amount_total'))


    @api.depends('plan_date', 'user_id')
    def _compute_period_kpis(self):
        Visit = self.env['sales.route.visit'].sudo()
        SaleOrder = self.env['sale.order'].sudo()
        for plan in self:
            plan.mtd_visit_count = 0
            plan.ytd_visit_count = 0
            plan.mtd_sales_order_count = 0
            plan.ytd_sales_order_count = 0
            plan.mtd_sales_amount = 0.0
            plan.ytd_sales_amount = 0.0
            if not plan.plan_date or not plan.user_id:
                continue
            plan_day = fields.Date.to_date(plan.plan_date)
            mtd_start = plan_day.replace(day=1)
            ytd_start = plan_day.replace(month=1, day=1)
            next_day = fields.Date.add(plan_day, days=1)
            common_visit_domain = [
                ('user_id', '=', plan.user_id.id),
                ('check_in', '!=', False),
                ('state', 'in', ['checked_in', 'checked_out', 'done']),
            ]
            plan.mtd_visit_count = Visit.search_count(common_visit_domain + [('check_in', '>=', fields.Datetime.to_datetime(mtd_start)), ('check_in', '<', fields.Datetime.to_datetime(next_day))])
            plan.ytd_visit_count = Visit.search_count(common_visit_domain + [('check_in', '>=', fields.Datetime.to_datetime(ytd_start)), ('check_in', '<', fields.Datetime.to_datetime(next_day))])
            common_order_domain = [
                ('user_id', '=', plan.user_id.id),
                ('state', 'in', ['sale', 'done']),
            ]
            mtd_orders = SaleOrder.search(common_order_domain + [('date_order', '>=', fields.Datetime.to_datetime(mtd_start)), ('date_order', '<', fields.Datetime.to_datetime(next_day))])
            ytd_orders = SaleOrder.search(common_order_domain + [('date_order', '>=', fields.Datetime.to_datetime(ytd_start)), ('date_order', '<', fields.Datetime.to_datetime(next_day))])
            plan.mtd_sales_order_count = len(mtd_orders)
            plan.ytd_sales_order_count = len(ytd_orders)
            plan.mtd_sales_amount = sum(mtd_orders.mapped('amount_total'))
            plan.ytd_sales_amount = sum(ytd_orders.mapped('amount_total'))

    @api.depends('line_ids.status', 'line_ids.sequence', 'line_ids.partner_id')
    def _compute_next_client(self):
        for plan in self:
            line = plan.line_ids.filtered(lambda l: l.status in ['pending', 'checked_in']).sorted('sequence')[:1]
            plan.next_client_id = line.partner_id if line else False
            plan.next_client_status = line.status if line else _('Completed')

    @api.onchange('route_id')
    def _onchange_route_id(self):
        if self.route_id and (not self.user_id or self.user_id not in self.route_id.user_ids):
            if self.route_id.user_ids and self.env.user in self.route_id.user_ids:
                self.user_id = self.env.user
            elif self.route_id.user_id:
                self.user_id = self.route_id.user_id
            elif self.route_id.user_ids:
                self.user_id = self.route_id.user_ids[0]
            supervisor = self._get_default_supervisor_for_route(self.route_id, self.user_id)
            self.supervisor_id = supervisor.id if supervisor else False



    def _get_next_actionable_line(self):
        self.ensure_one()
        return self.line_ids.filtered(lambda l: l.status in ['pending', 'checked_in']).sorted('sequence')[:1]

    def action_accept_auto_route(self):
        """Let a salesperson confirm that they will work the system route."""
        for plan in self:
            if plan.user_id != self.env.user and not (
                self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor')
                or self.env.user.has_group('field_sales_route_plan.group_field_sales_manager')
                or self.env.user.has_group('sales_team.group_sale_manager')
            ):
                raise UserError(_('You can only accept your own auto assigned route.'))
            if not plan.auto_assigned:
                raise UserError(_('This route plan was not generated by the system.'))
            vals = {
                'accepted_by_salesperson': True,
                'accepted_on': fields.Datetime.now(),
            }
            if plan.state == 'draft':
                vals['state'] = 'approved'
            plan.write(vals)
            plan.message_post(body=_('Salesperson accepted the system auto assigned route.'))
        return True

    def action_create_own_route_instead(self):
        """Open a fresh route plan while keeping the auto plan for audit/comparison."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Create My Own Route Plan'),
            'res_model': 'sales.route.plan',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_plan_date': self.plan_date,
                'default_user_id': self.user_id.id,
                'default_supervisor_id': self.supervisor_id.id,
                'default_assignment_source': 'manual',
                'default_note': _('Created by salesperson instead of following system auto assigned route %s.') % (self.name,),
            },
        }

    @api.model
    def _auto_assignment_frequency_due(self, partner, target_date):
        last_visit_date = False
        if partner.last_route_visit_date:
            last_visit_date = fields.Date.to_date(partner.last_route_visit_date)
        if not last_visit_date:
            return True
        days = (target_date - last_visit_date).days
        freq_days = {
            'daily': 1,
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'adhoc': 9999,
        }.get(partner.visit_frequency or 'weekly', 7)
        return days >= freq_days

    @api.model
    def _auto_assignment_partner_score(self, partner, target_date):
        score = 0
        reasons = []
        if not partner.last_route_visit_date:
            score += 70
            reasons.append(_('never visited'))
        elif self._auto_assignment_frequency_due(partner, target_date):
            score += 45
            reasons.append(_('visit due by frequency'))
        if partner.route_age_bucket == 'never_bought':
            score += 35
            reasons.append(_('never bought'))
        elif partner.route_age_bucket == '30_days':
            score += 30
            reasons.append(_('30+ days inactive'))
        elif partner.route_age_bucket == '14_days':
            score += 20
            reasons.append(_('14 days inactive'))
        elif partner.route_age_bucket == '7_days':
            score += 10
            reasons.append(_('7 days inactive'))
        if partner.customer_classification in ('key_account', 'high_potential'):
            score += 25
            reasons.append(_('%s customer') % dict(partner._fields['customer_classification'].selection).get(partner.customer_classification, partner.customer_classification))
        if partner.route_sales_potential:
            score += min(20, int(partner.route_sales_potential / 100000.0))
            reasons.append(_('sales potential'))
        # Previous missed planned calls get urgent priority.
        missed = self.env['sales.route.plan.line'].sudo().search_count([
            ('partner_id', '=', partner.id),
            ('status', '=', 'missed'),
            ('plan_date', '>=', fields.Date.add(target_date, days=-14)),
            ('plan_date', '<', target_date),
        ])
        if missed:
            score += 50
            reasons.append(_('recent missed call'))
        return score, ', '.join(reasons) or _('balanced coverage')

    @api.model
    def generate_daily_auto_route_plans(self, plan_date=False, user_ids=False, max_clients=20, approve=True, overwrite=False):
        """Generate one daily route plan per salesperson from assigned routes/customers.

        Criteria used: salesperson-route assignment, rotating market route coverage,
        customer visit frequency, missed calls, inactivity/no purchase ageing, customer
        classification, and estimated sales potential.
        """
        self = self.sudo()
        plan_date = fields.Date.to_date(plan_date or fields.Date.context_today(self))
        max_clients = max(1, int(max_clients or 20))
        Route = self.env['sales.route'].sudo()
        Partner = self.env['res.partner'].sudo()
        if user_ids:
            users = self.env['res.users'].sudo().browse(user_ids).exists()
        else:
            routes = Route.search([('active', '=', True), '|', ('user_id', '!=', False), ('user_ids', '!=', False)])
            users = (routes.mapped('user_id') | routes.mapped('user_ids')).filtered(lambda u: u.active)
        created = self.env['sales.route.plan']
        skipped = []

        # Prevent duplicate client allocation on the same route/day.
        # This is important where several salespeople share one market route:
        # a client already allocated to one salesperson for the day is removed
        # from the eligible pool for the next salesperson. Existing non-cancelled
        # plans are respected too, so rerunning the wizard will not double-book clients.
        existing_lines = self.env['sales.route.plan.line'].sudo().search([
            ('plan_date', '=', plan_date),
            ('route_id', '!=', False),
            ('partner_id', '!=', False),
            ('plan_id.state', 'not in', ['cancelled']),
        ])
        assigned_partner_ids_by_route = {}
        for line in existing_lines:
            assigned_partner_ids_by_route.setdefault(line.route_id.id, set()).add(line.partner_id.id)

        for user in users:
            existing = self.search([('plan_date', '=', plan_date), ('user_id', '=', user.id), ('state', 'not in', ['cancelled'])], limit=1)
            if existing and not overwrite:
                skipped.append('%s: %s' % (user.name, _('existing plan')))
                continue
            if existing and overwrite:
                existing.action_cancel()
            routes = Route.search([('active', '=', True), '|', ('user_id', '=', user.id), ('user_ids', 'in', [user.id])])
            if not routes:
                skipped.append('%s: %s' % (user.name, _('no assigned route')))
                continue
            # Rotate the main route by date so one salesperson with several routes does not keep visiting only one market.
            route = routes[plan_date.toordinal() % len(routes)]
            already_assigned_partner_ids = assigned_partner_ids_by_route.setdefault(route.id, set())
            partners = Partner.search([
                ('active', '=', True),
                ('customer_rank', '>', 0),
                ('route_id', '=', route.id),
                ('id', 'not in', list(already_assigned_partner_ids) or [0]),
            ])
            scored = []
            for partner in partners:
                score, reason = self._auto_assignment_partner_score(partner, plan_date)
                if score > 0 or partner.visit_frequency in ('daily', 'weekly'):
                    scored.append((score, partner.id, reason))
            scored.sort(key=lambda item: (-item[0], item[1]))
            selected = scored[:max_clients]
            if not selected:
                skipped.append('%s: %s' % (user.name, _('no eligible customers left on route after avoiding duplicate client assignments')))
                continue
            supervisor = self._get_default_supervisor_for_route(route, user)
            plan = self.create({
                'plan_date': plan_date,
                'user_id': user.id,
                'route_id': route.id,
                'supervisor_id': supervisor.id if supervisor else False,
                'planned_productive_calls': len(selected),
                'auto_assigned': True,
                'assignment_source': 'system',
                'assignment_reason': _('Auto selected by route rotation, customer frequency, missed calls, inactivity/no purchase ageing, customer classification and sales potential.'),
                'note': _('System generated route plan. Salesperson may accept and proceed, or create a manual route plan instead. Supervisors can compare actual work against this assigned plan.'),
                'state': 'approved' if approve else 'draft',
            })
            seq = 10
            for score, partner_id, reason in selected:
                self.env['sales.route.plan.line'].create({
                    'plan_id': plan.id,
                    'sequence': seq,
                    'partner_id': partner_id,
                    'expected_call_type': 'productive',
                    'expected_visit_purpose': 'sales',
                    'note': _('System priority score: %(score)s. Reason: %(reason)s') % {'score': score, 'reason': reason},
                })
                already_assigned_partner_ids.add(partner_id)
                seq += 10
            plan.action_optimize_route_sequence()
            plan.message_post(body=_('System auto assigned this route. Criteria: route rotation, visit frequency, missed calls, inactivity/no purchase ageing, classification, potential, and duplicate prevention so the same client is not assigned to multiple salespeople on the same route/day.'))
            created |= plan
        return created, skipped

    @api.model
    def cron_generate_daily_auto_route_plans(self):
        self.generate_daily_auto_route_plans(plan_date=fields.Date.context_today(self), approve=True, overwrite=False)
        return True

    def action_start_my_day(self):
        self.ensure_one()
        if self.state == 'draft':
            raise UserError(_('Please submit this route plan for approval first.'))
        if self.state == 'submitted':
            raise UserError(_('This route plan is waiting for supervisor approval.'))
        if self.state == 'approved':
            self.state = 'in_progress'
        line = self._get_next_actionable_line()
        if not line:
            raise UserError(_('No pending clients remain on this route plan.'))
        return line.action_start_visit()

    def action_next_client(self):
        self.ensure_one()
        if self.state not in ('approved', 'in_progress'):
            raise UserError(_('This route plan must be approved before visits can be started.'))
        line = self._get_next_actionable_line()
        if not line:
            raise UserError(_('No pending clients remain on this route plan.'))
        return line.action_start_visit()


    def action_add_new_client(self):
        self.ensure_one()
        if self.state not in ('approved', 'in_progress'):
            raise UserError(_('New field clients can only be added to approved or in-progress route plans.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add New Client to Today\'s Route'),
            'res_model': 'sales.route.plan.add.client.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_plan_id': self.id,
                'default_route_id': self.route_id.id,
                'default_user_id': self.user_id.id,
                'default_add_mode': 'new',
                'default_assign_to_route': False,
                'default_start_visit_after_add': True,
            },
        }

    def action_add_global_client(self):
        self.ensure_one()
        if self.state not in ('draft', 'approved', 'in_progress'):
            raise UserError(_('Clients can only be added while a route plan is draft, approved, or in progress.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Add Client From Any Route'),
            'res_model': 'sales.route.plan.add.client.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_plan_id': self.id,
                'default_route_id': self.route_id.id,
                'default_user_id': self.user_id.id,
                'default_add_mode': 'existing',
                'default_assign_to_route': False,
                'default_start_visit_after_add': False,
            },
        }



    def action_optimize_route_sequence(self):
        """Reorder pending route lines by nearest-neighbour using partner coordinates.

        This is intentionally lightweight and does not require paid map APIs. Lines
        without coordinates are kept at the end in their existing sequence.
        """
        def dist(a, b):
            if not a or not b:
                return 10 ** 9
            lat1, lon1 = a
            lat2, lon2 = b
            # approximate squared distance is enough for ordering in small areas
            return (lat1 - lat2) ** 2 + (lon1 - lon2) ** 2

        for plan in self:
            lines = plan.line_ids.filtered(lambda l: l.status == 'pending')
            with_coords = []
            without_coords = []
            for line in lines:
                lat = line.partner_id.partner_latitude
                lon = line.partner_id.partner_longitude
                if lat and lon:
                    with_coords.append((line, (lat, lon)))
                else:
                    without_coords.append(line)
            ordered = []
            current = None
            pool = list(with_coords)
            while pool:
                if current is None:
                    nxt = pool.pop(0)
                else:
                    nxt = min(pool, key=lambda item: dist(current, item[1]))
                    pool.remove(nxt)
                ordered.append(nxt[0])
                current = nxt[1]
            ordered += without_coords
            seq = 10
            for line in ordered:
                line.sequence = seq
                seq += 10
            plan.message_post(body=_('Route sequence optimized using available client coordinates.'))
        return True

    def _notify_route_plan_event(self, partner_users, body, summary=False, email_users=False, subject=False):
        """Post chatter/activity notification and send explicit email notifications.

        `partner_users` are the users who should receive Odoo inbox/activity notifications.
        `email_users` allows us to email extra people, for example the salesperson
        as confirmation when the supervisor is notified, without creating extra
        approval activities for the salesperson.
        """
        ActivityType = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        Mail = self.env['mail.mail'].sudo()
        for plan in self:
            partners = partner_users.mapped('partner_id').filtered(lambda p: p)
            if partners:
                plan.message_post(body=body, partner_ids=partners.ids, message_type='notification', subtype_xmlid='mail.mt_comment')
            if ActivityType:
                for user in partner_users:
                    if user.partner_id:
                        plan.activity_schedule(
                            'mail.mail_activity_data_todo',
                            user_id=user.id,
                            summary=summary or _('Route Plan Notification'),
                            note=body,
                        )

            # Explicit email notification. This does not replace Odoo internal
            # notifications; it ensures users also receive a normal email when
            # outgoing mail is configured on the server.
            mail_recipients = email_users or partner_users
            mail_recipients = mail_recipients.filtered(lambda u: u and (u.email or u.partner_id.email))
            seen_emails = set()
            for user in mail_recipients:
                email_to = user.email or user.partner_id.email
                if not email_to or email_to.lower() in seen_emails:
                    continue
                seen_emails.add(email_to.lower())
                Mail.create({
                    'subject': subject or summary or _('Route Plan Notification'),
                    'email_to': email_to,
                    'body_html': '<p>%s</p>' % html_escape(body),
                    'auto_delete': True,
                }).send()

    def action_submit(self):
        for plan in self:
            if plan.state != 'draft':
                raise UserError(_('Only draft route plans can be submitted for approval.'))
            plan.state = 'submitted'
            supervisor_users = plan.supervisor_id
            if not supervisor_users:
                group = self.env.ref('field_sales_route_plan.group_field_sales_supervisor', raise_if_not_found=False)
                supervisor_users = group.users if group else self.env['res.users']
            body = _('Route plan %s for %s has been submitted by %s and is waiting for approval.') % (
                plan.name, plan.plan_date, plan.user_id.name
            )
            plan._notify_route_plan_event(
                supervisor_users,
                body,
                summary=_('Route Plan Waiting for Approval'),
                subject=_('Route Plan Submitted for Approval'),
                email_users=(supervisor_users | plan.user_id),
            )
        return True

    def action_approve(self):
        if not self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') and not self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') and not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_('Only a supervisor can approve route plans.'))
        self.write({'state': 'approved'})
        for plan in self:
            body = _('Your route plan %s for %s has been approved by %s.') % (plan.name, plan.plan_date, self.env.user.name)
            email_users = plan.user_id | plan.supervisor_id | self.env.user
            plan._notify_route_plan_event(
                plan.user_id,
                body,
                summary=_('Route Plan Approved'),
                subject=_('Route Plan Approved'),
                email_users=email_users,
            )
        return True

    def action_add_to_facilitation_sheet(self):
        if not self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') and not self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') and not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_('Only a supervisor or sales manager can add route plans to a facilitation sheet.'))
        plans = self.filtered(lambda p: p.state in ('approved', 'in_progress', 'done'))
        if not plans:
            raise UserError(_('No approved route plans selected. Only approved, in-progress, or done route plans can be added to facilitation.'))

        today = fields.Date.context_today(self)
        old_plans = plans.filtered(lambda p: p.plan_date != today)
        if old_plans:
            raise UserError(_("Only today\'s route plans can be added to today\'s facilitation sheet. Please open a route plan dated %s.") % today)

        dates = plans.mapped('plan_date')
        if len(set(dates)) != 1:
            raise UserError(_('Please generate one facilitation form per day. Select route plans for the same day only.'))
        plan_date = dates[0]
        if plan_date != today:
            raise UserError(_("Only today\'s route plans can be added to a facilitation sheet."))

        supervisor = self.env.user
        form = self.env['sales.route.facilitation.form'].search([
            ('plan_date', '=', today),
            ('supervisor_id', '=', supervisor.id),
            ('company_id', '=', self.env.company.id),
        ], limit=1)
        if not form:
            form = self.env['sales.route.facilitation.form'].create({
                'plan_date': today,
                'supervisor_id': supervisor.id,
                'company_id': self.env.company.id,
            })
        form.action_add_plans(plans)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Daily Facilitation Sheet'),
            'res_model': 'sales.route.facilitation.form',
            'view_mode': 'form',
            'res_id': form.id,
            'target': 'current',
        }

    def action_reject(self):
        if not self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') and not self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') and not self.env.user.has_group('sales_team.group_sale_manager'):
            raise UserError(_('Only a supervisor can reject route plans.'))
        for plan in self:
            plan.state = 'draft'
            body = _('Your route plan %s for %s has been rejected by %s. Please review and resubmit.') % (
                plan.name, plan.plan_date, self.env.user.name
            )
            email_users = plan.user_id | plan.supervisor_id | self.env.user
            plan._notify_route_plan_event(
                plan.user_id,
                body,
                summary=_('Route Plan Rejected'),
                subject=_('Route Plan Rejected'),
                email_users=email_users,
            )

    def action_start(self):
        for plan in self:
            if plan.state != 'approved':
                raise UserError(_('Only approved route plans can be started.'))
        self.write({'state': 'in_progress'})

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


    def write(self, vals):
        allowed_anytime = {'state', 'message_follower_ids', 'activity_ids', 'message_ids'}
        allowed_auto_accept = {'accepted_by_salesperson', 'accepted_on'}
        protected_fields = set(vals) - allowed_anytime
        if protected_fields and not (self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') or self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') or self.env.user.has_group('sales_team.group_sale_manager')):
            locked = self.filtered(lambda p: p.state in ('submitted', 'approved', 'in_progress', 'done'))
            if locked:
                auto_accept_only = protected_fields <= allowed_auto_accept and all(p.auto_assigned and p.user_id == self.env.user for p in locked)
                if not auto_accept_only:
                    raise UserError(_('You cannot edit a route plan after it has been submitted. Ask a supervisor to reset or update it.'))
        res = super().write(vals)
        return res


class SalesRoutePlanLine(models.Model):
    _name = 'sales.route.plan.line'
    _description = 'Daily Route Plan Client Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    plan_id = fields.Many2one('sales.route.plan', required=True, ondelete='cascade', index=True)
    plan_state = fields.Selection(related='plan_id.state', string='Plan Status', readonly=True)
    plan_date = fields.Date(related='plan_id.plan_date', store=True, index=True)
    route_id = fields.Many2one(related='plan_id.route_id', store=True, index=True)
    user_id = fields.Many2one(related='plan_id.user_id', store=True, index=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, index=True, domain="[('customer_rank', '>', 0)]")
    customer_home_route_id = fields.Many2one('sales.route', related='partner_id.route_id', string='Customer Home Route', store=True, readonly=True)
    borrowed_from_route = fields.Boolean(string='Cross-Route Client', compute='_compute_borrowed_from_route', store=True)
    is_ad_hoc = fields.Boolean(string='Added in Field', default=False, help='This client was added during the sales person day and was not in the original route plan.')
    expected_call_type = fields.Selection([
        ('productive', 'Possible Productive'),
        ('unproductive', 'Possible Unproductive'),
    ], default='productive', required=True)
    expected_visit_purpose = fields.Selection([
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('delivery', 'Delivery'),
        ('merchandising', 'Merchandising'),
        ('retail_sales', 'Retail Sales Visit'),
        ('van_sales', 'Van Sales'),
        ('other', 'Other'),
    ], string='Purpose Type', default='sales', required=True)
    expected_visit_purpose_id = fields.Many2one('sales.route.visit.purpose', string='Purpose', default=lambda self: self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False))
    product_ids = fields.Many2many('product.product', string='Focus Products')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
        ('productive', 'Productive'),
        ('unproductive', 'Unproductive'),
        ('missed', 'Missed'),
    ], default='pending', tracking=True)
    visit_id = fields.Many2one('sales.route.visit', string='Visit')
    sale_order_id = fields.Many2one('sale.order', string='Latest Sales Order')
    sale_order_ids = fields.One2many('sale.order', 'route_plan_line_id', string='Sales Orders', readonly=True)
    sale_order_tag_ids = fields.Many2many('sale.order', compute='_compute_sale_order_tags', string='Sales Orders')
    sale_order_numbers = fields.Char(string='Sales Orders', compute='_compute_sale_order_tags')
    currency_id = fields.Many2one('res.currency', related='plan_id.company_id.currency_id')
    unproductive_reason = fields.Selection([
        ('closed', 'Client Closed'),
        ('no_stock', 'No Stock Required'),
        ('no_cash', 'No Cash / Credit Issue'),
        ('owner_absent', 'Owner/Buyer Absent'),
        ('competitor', 'Bought from Competitor'),
        ('other', 'Other'),
    ])
    unproductive_reason_id = fields.Many2one('sales.route.call.reason', string='Unproductive Reason')
    note = fields.Text()



    @api.depends('partner_id.route_id', 'route_id')
    def _compute_borrowed_from_route(self):
        for line in self:
            line.borrowed_from_route = bool(line.partner_id.route_id and line.route_id and line.partner_id.route_id != line.route_id)

    @api.onchange('expected_visit_purpose_id')
    def _onchange_expected_visit_purpose_id(self):
        for line in self:
            if line.expected_visit_purpose_id:
                line.expected_visit_purpose = line.expected_visit_purpose_id.category or 'other'

    @api.depends('sale_order_ids', 'sale_order_ids.name')
    def _compute_sale_order_tags(self):
        for line in self:
            orders = line.sale_order_ids.sorted('id')
            line.sale_order_tag_ids = orders
            line.sale_order_numbers = ', '.join(orders.mapped('name'))

    def write(self, vals):
        if vals and not (self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') or self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') or self.env.user.has_group('sales_team.group_sale_manager')):
            locked = self.filtered(lambda l: l.plan_id.state in ('submitted', 'approved', 'done'))
            allowed = {'status', 'visit_id', 'sale_order_id', 'note'}
            if locked and vals.get('is_ad_hoc'):
                allowed |= {'sequence', 'plan_id', 'partner_id', 'expected_call_type', 'expected_visit_purpose', 'expected_visit_purpose_id', 'product_ids', 'is_ad_hoc'}
            if locked and (set(vals) - allowed):
                raise UserError(_('You cannot edit planned client visits after the route plan has been submitted.'))
        return super().write(vals)

    def unlink(self):
        if not (self.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') or self.env.user.has_group('field_sales_route_plan.group_field_sales_manager') or self.env.user.has_group('sales_team.group_sale_manager')) and self.filtered(lambda l: l.plan_id.state != 'draft'):
            raise UserError(_('You cannot remove planned client visits after the route plan has been submitted.'))
        return super().unlink()

    def action_view_sale_orders(self):
        self.ensure_one()
        orders = self.sale_order_ids
        if not orders:
            raise UserError(_('No sales order has been created for this visit yet.'))
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Sales Orders'),
            'res_model': 'sale.order',
            'target': 'current',
            'context': {'create': False},
        }
        if len(orders) == 1:
            action.update({'view_mode': 'form', 'views': [(False, 'form')], 'res_id': orders.id})
        else:
            action.update({'view_mode': 'tree,form', 'domain': [('id', 'in', orders.ids)]})
        return action

    @api.onchange('plan_id', 'route_id', 'is_ad_hoc')
    def _onchange_route_domain(self):
        for line in self:
            if line.partner_id and line.route_id and line.partner_id.route_id and line.partner_id.route_id != line.route_id and not line.is_ad_hoc:
                line.partner_id = False
            return {'domain': {'partner_id': [('customer_rank', '>', 0)]}}

    @api.constrains('partner_id', 'route_id')
    def _check_partner_on_route(self):
        for line in self:
            if line.partner_id and line.route_id and line.partner_id.route_id and line.partner_id.route_id != line.route_id and not line.is_ad_hoc:
                raise ValidationError(_('The selected client is not assigned to the selected route. Please add the client to the market route first or use Add New Client for field additions.'))

    def action_start_visit(self):
        self.ensure_one()
        if self.plan_id.state not in ('approved', 'in_progress'):
            raise UserError(_('This route plan must be approved before any visit can be started.'))
        if self.visit_id:
            return self.visit_id.action_open_visit_form()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Choose Visit Purpose'),
            'res_model': 'sales.route.visit.purpose.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_plan_line_id': self.id,
                'default_visit_purpose': self.expected_visit_purpose or 'sales',
                'default_visit_purpose_id': self.expected_visit_purpose_id.id or False,
            },
        }

    def action_check_in(self):
        self.ensure_one()
        if self.plan_id.state not in ('approved', 'in_progress'):
            raise UserError(_('This route plan must be approved before any visit can be checked in.'))
        if self.visit_id and self.visit_id.state == 'checked_in':
            raise UserError(_('This client is already checked in.'))
        visit = self.visit_id or self.env['sales.route.visit'].create({
            'plan_line_id': self.id,
            'plan_id': self.plan_id.id,
            'route_id': self.route_id.id,
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'visit_purpose_id': self.expected_visit_purpose_id.id if self.expected_visit_purpose_id else False,
            'visit_purpose': self.expected_visit_purpose or 'sales',
        })
        self.write({'visit_id': visit.id})
        if self.env.context.get('gps_latitude') is not None and self.env.context.get('gps_longitude') is not None:
            visit.action_check_in()
            self.write({'status': 'checked_in'})
            return True
        return visit.action_open_gps_checkin()

    def action_check_out(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError(_('Please check in before checking out.'))
        if self.env.context.get('gps_latitude') is not None and self.env.context.get('gps_longitude') is not None:
            self.visit_id.action_check_out()
            if self.status == 'checked_in':
                self.status = 'checked_out'
            return True
        return self.visit_id.action_open_gps_checkout()

    def action_mark_productive(self):
        self.write({'status': 'productive'})

    def action_mark_unproductive(self):
        self.write({'status': 'unproductive'})

    def action_mark_missed(self):
        self.write({'status': 'missed'})

    def action_create_sale_order(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a client before creating an order.'))
        return {
            'type': 'ir.actions.client',
            'tag': 'field_sales_route_plan.sale_terminal',
            'name': _('Route Sales Terminal'),
            'target': 'current',
            'context': {
                'plan_line_id': self.id,
            },
        }
