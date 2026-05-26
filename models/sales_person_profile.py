from odoo import fields, models, tools, _
from odoo.osv import expression


class SalesPersonProfile(models.Model):
    _name = 'sales.person.profile'
    _description = 'Sales Person Profile Dashboard'
    _auto = False
    _rec_name = 'user_id'
    _order = 'mtd_total_sales desc, user_id'

    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    partner_id = fields.Many2one('res.partner', string='Contact', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    image_128 = fields.Image(string='Photo', related='user_id.image_128', readonly=True)
    assigned_route_count = fields.Integer(string='Assigned Routes', readonly=True)
    assigned_route_names = fields.Char(string='Assigned Route Names', readonly=True)
    supervised_by_names = fields.Char(string='Supervisors', readonly=True)
    customer_count = fields.Integer(string='Route Customers', readonly=True)

    # Selected sales/marketing period route usage. Counts each route client only once
    # in the selected period, and only when the first counted interaction is a
    # successful productive call (sale order amount or POS order amount > 0).
    selected_period_label = fields.Char(string='Selected Period', compute='_compute_selected_period_route_usage')
    selected_period_date_from = fields.Date(string='Period From', compute='_compute_selected_period_route_usage')
    selected_period_date_to = fields.Date(string='Period To', compute='_compute_selected_period_route_usage')
    period_route_clients = fields.Integer(string='Period Route Clients', compute='_compute_selected_period_route_usage')
    period_productive_clients = fields.Integer(string='Productive Clients Served', compute='_compute_selected_period_route_usage')
    period_productive_visits = fields.Integer(string='Productive Visit Attempts', compute='_compute_selected_period_route_usage')
    period_route_achievement = fields.Float(string='Route Performance %', compute='_compute_selected_period_route_usage')
    period_route_performance = fields.Char(string='Route Performance', compute='_compute_selected_period_route_usage')

    # MTD visit-purpose coverage. Clients served are unique customers visited by this salesperson.
    # Visit counts preserve repeat visits, so supervisors can see both reach and activity.
    mtd_marketing_clients = fields.Integer(string='Marketing Clients Served', readonly=True)
    mtd_marketing_visits = fields.Integer(string='Marketing Visits', readonly=True)
    mtd_marketing_achievement = fields.Float(string='Marketing Achievement %', readonly=True)
    mtd_sales_clients = fields.Integer(string='Sales Clients Served', readonly=True)
    mtd_sales_visits = fields.Integer(string='Sales Visits', readonly=True)
    mtd_sales_achievement = fields.Float(string='Sales Achievement %', readonly=True)
    mtd_van_sales_clients = fields.Integer(string='Van Sales Clients Served', readonly=True)
    mtd_van_sales_visits = fields.Integer(string='Van Sales Visits', readonly=True)
    mtd_van_sales_achievement = fields.Float(string='Van Sales Achievement %', readonly=True)
    mtd_retail_sales_clients = fields.Integer(string='Retail Clients Served', readonly=True)
    mtd_retail_sales_visits = fields.Integer(string='Retail Visits', readonly=True)
    mtd_retail_sales_achievement = fields.Float(string='Retail Achievement %', readonly=True)
    mtd_merchandising_clients = fields.Integer(string='Merchandising Clients Served', readonly=True)
    mtd_merchandising_visits = fields.Integer(string='Merchandising Visits', readonly=True)
    mtd_merchandising_achievement = fields.Float(string='Merchandising Achievement %', readonly=True)
    mtd_delivery_clients = fields.Integer(string='Delivery Clients Served', readonly=True)
    mtd_delivery_visits = fields.Integer(string='Delivery Visits', readonly=True)
    mtd_delivery_achievement = fields.Float(string='Delivery Achievement %', readonly=True)
    mtd_other_clients = fields.Integer(string='Other Purpose Clients Served', readonly=True)
    mtd_other_visits = fields.Integer(string='Other Purpose Visits', readonly=True)
    mtd_other_achievement = fields.Float(string='Other Purpose Achievement %', readonly=True)

    today_plan_count = fields.Integer(string='Today Plans', readonly=True)
    mtd_plan_count = fields.Integer(string='MTD Plans', readonly=True)
    ytd_plan_count = fields.Integer(string='YTD Plans', readonly=True)

    today_visit_count = fields.Integer(string='Today Visits', readonly=True)
    mtd_visit_count = fields.Integer(string='MTD Visits', readonly=True)
    ytd_visit_count = fields.Integer(string='YTD Visits', readonly=True)
    today_productive_calls = fields.Integer(string='Today Productive Calls', readonly=True)
    mtd_productive_calls = fields.Integer(string='MTD Productive Calls', readonly=True)
    ytd_productive_calls = fields.Integer(string='YTD Productive Calls', readonly=True)
    missed_calls_mtd = fields.Integer(string='MTD Missed Calls', readonly=True)
    off_route_visits_mtd = fields.Integer(string='MTD Off-route Visits', readonly=True)
    suspicious_visits_mtd = fields.Integer(string='MTD Suspicious Visits', readonly=True)
    visit_compliance_mtd = fields.Float(string='MTD Visit Compliance %', readonly=True)
    productive_rate_mtd = fields.Float(string='MTD Productive Rate %', readonly=True)

    today_sales_order_count = fields.Integer(string='Today Sale Orders', readonly=True)
    mtd_sales_order_count = fields.Integer(string='MTD Sale Orders', readonly=True)
    ytd_sales_order_count = fields.Integer(string='YTD Sale Orders', readonly=True)
    today_sales_amount = fields.Float(string='Today Sales Orders Amount', readonly=True)
    mtd_sales_amount = fields.Float(string='MTD Sales Orders Amount', readonly=True)
    ytd_sales_amount = fields.Float(string='YTD Sales Orders Amount', readonly=True)

    today_pos_order_count = fields.Integer(string='Today POS Orders', readonly=True)
    mtd_pos_order_count = fields.Integer(string='MTD POS Orders', readonly=True)
    ytd_pos_order_count = fields.Integer(string='YTD POS Orders', readonly=True)
    today_pos_amount = fields.Float(string='Today POS Amount', readonly=True)
    mtd_pos_amount = fields.Float(string='MTD POS Amount', readonly=True)
    ytd_pos_amount = fields.Float(string='YTD POS Amount', readonly=True)
    today_pos_amount_due = fields.Float(string='POS Today Amount Due', readonly=True)
    mtd_pos_amount_due = fields.Float(string='POS MTD Amount Due', readonly=True)
    ytd_pos_amount_due = fields.Float(string='POS YTD Amount Due', readonly=True)

    today_total_sales = fields.Float(string='Today Sales', readonly=True)
    mtd_total_sales = fields.Float(string='MTD Sales', readonly=True)
    ytd_total_sales = fields.Float(string='YTD Sales', readonly=True)
    last_visit_date = fields.Datetime(string='Last Visit', readonly=True)
    last_order_date = fields.Datetime(string='Last Sale Order', readonly=True)
    last_attendance_start = fields.Datetime(string='Last Day Start', readonly=True)
    last_attendance_end = fields.Datetime(string='Last Day End', readonly=True)
    attendance_hours_mtd = fields.Float(string='MTD Attendance Hours', readonly=True)
    gamification_points_mtd = fields.Integer(string='MTD Gamification Points', readonly=True)

    sku_today_count = fields.Integer(string='SKUs Today', compute='_compute_extended_profile_metrics')
    sku_mtd_count = fields.Integer(string='SKUs MTD', compute='_compute_extended_profile_metrics')
    sku_ytd_count = fields.Integer(string='SKUs YTD', compute='_compute_extended_profile_metrics')
    top_sku_today = fields.Char(string='Top Sales SKU Today', compute='_compute_extended_profile_metrics')
    top_sku_mtd = fields.Char(string='Top Sales SKU MTD', compute='_compute_extended_profile_metrics')
    top_sku_ytd = fields.Char(string='Top Sales SKU YTD', compute='_compute_extended_profile_metrics')
    target_amount_mtd = fields.Float(string='Target MTD', compute='_compute_extended_profile_metrics')
    achievement_amount_mtd = fields.Float(string='Achievement MTD', compute='_compute_extended_profile_metrics')
    achievement_rate_mtd = fields.Float(string='Achievement %', compute='_compute_extended_profile_metrics')
    top_5_clients = fields.Text(string='Top 5 Clients', compute='_compute_extended_profile_metrics')
    poor_5_clients = fields.Text(string='Poor 5 Clients', compute='_compute_extended_profile_metrics')
    top_5_missed_clients = fields.Text(string='Top 5 Missed Clients', compute='_compute_extended_profile_metrics')
    ai_performance_appraisal = fields.Text(string='AI Suggested Performance Appraisal', compute='_compute_extended_profile_metrics')
    ai_appraisal_grade = fields.Selection([
        ('good', 'Good'),
        ('poor', 'Poor'),
        ('bad', 'Bad'),
    ], string='AI Appraisal Grade', compute='_compute_extended_profile_metrics')
    rank_recommendation = fields.Selection([
        ('reward', 'Reward'),
        ('pip', 'PiP'),
        ('terminate', 'Terminate'),
    ], string='Rank Recommendation', compute='_compute_extended_profile_metrics')

    ai_coach_score = fields.Float(string='AI Coach Score', compute='_compute_extended_profile_metrics')
    ai_coach_risk = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('warning', 'Warning'),
        ('critical', 'Critical'),
    ], string='AI Coach Risk', compute='_compute_extended_profile_metrics')
    ai_coach_summary = fields.Text(string='AI Sales Coach Summary', compute='_compute_extended_profile_metrics')
    ai_coach_recommendations = fields.Text(string='AI Sales Coach Recommendations', compute='_compute_extended_profile_metrics')
    leaderboard_rank_mtd = fields.Integer(string='MTD Leaderboard Rank', compute='_compute_extended_profile_metrics')
    leaderboard_badges = fields.Char(string='Leaderboard Badges', compute='_compute_extended_profile_metrics')

    sku_target_qty_mtd = fields.Float(string='SKU Target Qty MTD', compute='_compute_sku_target_tracking_metrics')
    sku_sold_qty_mtd = fields.Float(string='SKU Sold Qty MTD', compute='_compute_sku_target_tracking_metrics')
    sku_target_gap_mtd = fields.Float(string='SKU Target Gap MTD', compute='_compute_sku_target_tracking_metrics')
    sku_target_achievement_mtd = fields.Float(string='SKU Target Achievement %', compute='_compute_sku_target_tracking_metrics')
    sku_compliance_summary = fields.Char(string='SKU Compliance Summary', compute='_compute_sku_target_tracking_metrics')
    missed_target_skus = fields.Text(string='Top Missed Target SKUs', compute='_compute_sku_target_tracking_metrics')


    def _compute_sku_target_tracking_metrics(self):
        Perf = self.env['sales.route.sku.target.performance'].sudo() if 'sales.route.sku.target.performance' in self.env.registry else False
        today = fields.Date.context_today(self)
        month_start = today.replace(day=1)
        for rec in self:
            rec.sku_target_qty_mtd = rec.sku_sold_qty_mtd = rec.sku_target_gap_mtd = rec.sku_target_achievement_mtd = 0.0
            rec.sku_compliance_summary = _('No active SKU target')
            rec.missed_target_skus = _('No missed target SKUs')
            if not Perf or not rec.user_id:
                continue
            domain = [('salesperson_id', '=', rec.user_id.id), ('date_end', '>=', month_start), ('date_start', '<=', today)]
            groups = Perf.read_group(domain, ['target_qty:sum', 'total_qty:sum', 'gap_qty:sum'], [])
            totals = groups[0] if groups else {}
            target_qty = totals.get('target_qty') or 0.0
            sold_qty = totals.get('total_qty') or 0.0
            gap_qty = totals.get('gap_qty') or 0.0
            rec.sku_target_qty_mtd = target_qty
            rec.sku_sold_qty_mtd = sold_qty
            rec.sku_target_gap_mtd = gap_qty
            rec.sku_target_achievement_mtd = (sold_qty / target_qty * 100.0) if target_qty else 0.0
            rec.sku_compliance_summary = _('%s / %s target qty sold') % (round(sold_qty, 2), round(target_qty, 2)) if target_qty else _('No active SKU target')
            rows = Perf.search(domain + [('gap_qty', '>', 0)], order='gap_qty desc, achievement_percent asc', limit=5)
            lines = []
            for idx, row in enumerate(rows, 1):
                sku = row.product_category_id.display_name or _('Product Category')
                lines.append('%s. %s - Gap %s, %s%% achieved' % (idx, sku, round(row.gap_qty, 2), round(row.achievement_percent, 1)))
            if lines:
                rec.missed_target_skus = '\n'.join(lines)

    def action_view_sku_target_performance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Category SKU Target Performance - %s') % (self.user_id.name or ''),
            'res_model': 'sales.route.sku.target.performance',
            'view_mode': 'tree,kanban,pivot,graph',
            'domain': [('salesperson_id', '=', self.user_id.id)],
            'context': {'create': False, 'search_default_underperforming': 1, 'search_default_group_category': 1},
        }

    def _selected_sales_marketing_period(self):
        """Return (start_date, end_date, label) for fixed or custom sales/marketing period.

        Periods are:
        - January to April
        - May to August
        - September to December
        A custom date range can be supplied through context by the period wizard.
        """
        ctx = self.env.context or {}
        today = fields.Date.context_today(self)
        year = int(ctx.get('fsrp_period_year') or today.year)
        key = ctx.get('fsrp_period_key') or 'today'
        if key == 'today':
            return today, today, _('Today %s') % today
        if key == 'custom':
            start = ctx.get('fsrp_date_from') or ctx.get('date_from')
            end = ctx.get('fsrp_date_to') or ctx.get('date_to')
            start = fields.Date.to_date(start) if start else today.replace(day=1)
            end = fields.Date.to_date(end) if end else today
            if end < start:
                start, end = end, start
            return start, end, _('Custom: %s to %s') % (start, end)
        if key == 'jan_apr' or (key == 'current' and today.month <= 4):
            return today.replace(year=year, month=1, day=1), today.replace(year=year, month=4, day=30), _('January to April %s') % year
        if key == 'may_aug' or (key == 'current' and today.month <= 8):
            return today.replace(year=year, month=5, day=1), today.replace(year=year, month=8, day=31), _('May to August %s') % year
        return today.replace(year=year, month=9, day=1), today.replace(year=year, month=12, day=31), _('September to December %s') % year

    def _productive_visit_domain_for_period(self, start_date, end_date, user_id=None, route_ids=None):
        start_dt = fields.Datetime.to_datetime(start_date)
        end_dt = fields.Datetime.to_datetime(fields.Date.add(end_date, days=1))
        amount_domain = ['|', ('sale_order_total_amount', '>', 0), ('pos_order_total_amount', '>', 0)]
        domain = [
            ('check_in', '>=', fields.Datetime.to_string(start_dt)),
            ('check_in', '<', fields.Datetime.to_string(end_dt)),
            ('check_in', '!=', False),
            ('partner_id', '!=', False),
        ] + amount_domain
        if user_id:
            domain.append(('user_id', '=', user_id))
        if route_ids:
            domain.append(('route_id', 'in', route_ids))
        return domain

    def _compute_selected_period_route_usage(self):
        Visit = self.env['sales.route.visit'].sudo()
        Route = self.env['sales.route'].sudo()
        Partner = self.env['res.partner'].sudo()
        start_date, end_date, label = self._selected_sales_marketing_period()
        for rec in self:
            route_domain = [('active', '=', True), '|', ('user_id', '=', rec.user_id.id), ('user_ids', 'in', [rec.user_id.id])]
            routes = Route.search(route_domain) if rec.user_id else Route.browse()
            route_ids = routes.ids
            total_clients = Partner.search_count([('route_id', 'in', route_ids), ('active', '=', True)]) if route_ids else 0
            productive_visits = Visit.search(self._productive_visit_domain_for_period(start_date, end_date, rec.user_id.id, route_ids)) if rec.user_id and route_ids else Visit.browse()
            productive_client_ids = set(productive_visits.mapped('partner_id').ids)
            client_count = len(productive_client_ids)
            rec.selected_period_label = label
            rec.selected_period_date_from = start_date
            rec.selected_period_date_to = end_date
            rec.period_route_clients = total_clients
            rec.period_productive_clients = client_count
            rec.period_productive_visits = len(productive_visits)
            rec.period_route_achievement = round((client_count / total_clients) * 100.0, 2) if total_clients else 0.0
            rec.period_route_performance = '%s/%s' % (client_count, total_clients)

    def _period_bounds(self):
        today = fields.Date.context_today(self)
        today_dt = fields.Datetime.to_datetime(today)
        tomorrow_dt = fields.Datetime.to_datetime(fields.Date.add(today, days=1))
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        return {
            'today': (today_dt, tomorrow_dt),
            'mtd': (fields.Datetime.to_datetime(month_start), tomorrow_dt),
            'ytd': (fields.Datetime.to_datetime(year_start), tomorrow_dt),
            'today_date': today,
            'month_start': month_start,
            'year_start': year_start,
        }

    def _format_ranked_names(self, rows, amount_key='amount'):
        lines = []
        for idx, row in enumerate(rows[:5], 1):
            name = row.get('name') or _('Unknown')
            amount = row.get(amount_key, 0.0) or 0.0
            lines.append('%s. %s (%s)' % (idx, name, '{:,.2f}'.format(amount)))
        return '\n'.join(lines) if lines else _('No data yet')

    def _compute_extended_profile_metrics(self):
        SaleOrder = self.env['sale.order'].sudo()
        SaleLine = self.env['sale.order.line'].sudo()
        PosOrder = self.env['pos.order'].sudo()
        PosLine = self.env['pos.order.line'].sudo()
        Target = self.env['sales.route.target'].sudo()
        PlanLine = self.env['sales.route.plan.line'].sudo()
        Partner = self.env['res.partner'].sudo()
        bounds = self._period_bounds()

        def order_domain(user, start, end):
            return [('user_id', '=', user.id), ('date_order', '>=', start), ('date_order', '<', end), ('state', 'in', ['sale', 'done'])]

        def pos_domain(user, start, end):
            return [('user_id', '=', user.id), ('date_order', '>=', start), ('date_order', '<', end), ('state', 'in', ['paid', 'done', 'invoiced'])]

        def product_metrics(user, start, end):
            product_totals = {}
            product_names = {}
            sale_orders = SaleOrder.search(order_domain(user, start, end))
            if sale_orders:
                line_domain = [('order_id', 'in', sale_orders.ids), ('product_id', '!=', False)]
                if 'display_type' in SaleLine._fields:
                    line_domain.append(('display_type', '=', False))
                for line in SaleLine.search(line_domain):
                    product_totals[line.product_id.id] = product_totals.get(line.product_id.id, 0.0) + (line.price_total or 0.0)
                    product_names[line.product_id.id] = line.product_id.display_name
            pos_orders = PosOrder.search(pos_domain(user, start, end))
            if pos_orders:
                for line in PosLine.search([('order_id', 'in', pos_orders.ids), ('product_id', '!=', False)]):
                    amount = 0.0
                    if 'price_subtotal_incl' in PosLine._fields:
                        amount = line.price_subtotal_incl or 0.0
                    elif 'price_subtotal' in PosLine._fields:
                        amount = line.price_subtotal or 0.0
                    product_totals[line.product_id.id] = product_totals.get(line.product_id.id, 0.0) + amount
                    product_names[line.product_id.id] = line.product_id.display_name
            if not product_totals:
                return 0, _('No SKU sales')
            top_product_id = max(product_totals, key=product_totals.get)
            return len(product_totals), product_names.get(top_product_id, _('Unknown SKU'))

        def client_sales(user, start, end):
            totals = {}
            names = {}
            for order in SaleOrder.search(order_domain(user, start, end)):
                if order.partner_id:
                    totals[order.partner_id.id] = totals.get(order.partner_id.id, 0.0) + (order.amount_total or 0.0)
                    names[order.partner_id.id] = order.partner_id.display_name
            for order in PosOrder.search(pos_domain(user, start, end)):
                if order.partner_id:
                    totals[order.partner_id.id] = totals.get(order.partner_id.id, 0.0) + (order.amount_total or 0.0)
                    names[order.partner_id.id] = order.partner_id.display_name
            return [{'id': pid, 'name': names.get(pid), 'amount': amount} for pid, amount in totals.items()]

        for rec in self:
            user = rec.user_id
            # Defaults
            rec.sku_today_count = rec.sku_mtd_count = rec.sku_ytd_count = 0
            rec.top_sku_today = rec.top_sku_mtd = rec.top_sku_ytd = _('No SKU sales')
            rec.target_amount_mtd = 0.0
            rec.achievement_amount_mtd = rec.mtd_total_sales or 0.0
            rec.achievement_rate_mtd = 0.0
            rec.top_5_clients = rec.poor_5_clients = rec.top_5_missed_clients = _('No data yet')
            rec.ai_performance_appraisal = _('Not enough data to appraise yet.')
            rec.ai_appraisal_grade = 'poor'
            rec.rank_recommendation = 'pip'
            rec.ai_coach_score = 0.0
            rec.ai_coach_risk = 'warning'
            rec.ai_coach_summary = _('Not enough data for coaching yet.')
            rec.ai_coach_recommendations = _("Start by completing today's assigned route and capturing every customer visit outcome.")
            rec.leaderboard_rank_mtd = 0
            rec.leaderboard_badges = _('No badge yet')
            if not user:
                continue

            rec.sku_today_count, rec.top_sku_today = product_metrics(user, *bounds['today'])
            rec.sku_mtd_count, rec.top_sku_mtd = product_metrics(user, *bounds['mtd'])
            rec.sku_ytd_count, rec.top_sku_ytd = product_metrics(user, *bounds['ytd'])

            targets = Target.search([
                ('active', '=', True),
                ('target_scope', 'in', ['salesperson', 'route_salesperson']),
                ('user_id', '=', user.id),
                ('date_start', '<=', bounds['today_date']),
                ('date_end', '>=', bounds['month_start']),
            ])
            rec.target_amount_mtd = sum(targets.mapped('sales_order_target_amount'))
            rec.achievement_amount_mtd = rec.mtd_total_sales or 0.0
            rec.achievement_rate_mtd = (rec.achievement_amount_mtd / rec.target_amount_mtd * 100.0) if rec.target_amount_mtd else 0.0

            clients = sorted(client_sales(user, *bounds['mtd']), key=lambda r: r['amount'], reverse=True)
            rec.top_5_clients = rec._format_ranked_names(clients[:5])
            if rec.assigned_route_names:
                route_ids = self.env['sales.route'].sudo().search(['|', ('user_id', '=', user.id), ('user_ids', 'in', [user.id])]).ids
                route_clients = Partner.search([('route_id', 'in', route_ids), ('customer_rank', '>', 0)]) if route_ids else Partner.browse()
                client_amount_by_id = {row['id']: row['amount'] for row in clients}
                poor_rows = [{'id': c.id, 'name': c.display_name, 'amount': client_amount_by_id.get(c.id, 0.0)} for c in route_clients]
                poor_rows = sorted(poor_rows, key=lambda r: r['amount'])[:5]
            else:
                poor_rows = sorted(clients, key=lambda r: r['amount'])[:5]
            rec.poor_5_clients = rec._format_ranked_names(poor_rows)

            # Odoo 16 read_group cannot safely order by generated aggregate aliases
            # such as partner_id_count. Read the grouped rows first, then sort in Python.
            missed_groups = PlanLine.read_group([
                ('user_id', '=', user.id),
                ('plan_date', '>=', bounds['month_start']),
                ('plan_date', '<=', bounds['today_date']),
                ('status', '=', 'missed'),
                ('partner_id', '!=', False),
            ], ['partner_id'], ['partner_id'])
            missed_groups = sorted(
                missed_groups,
                key=lambda g: g.get('partner_id_count') or g.get('__count') or 0,
                reverse=True,
            )[:5]
            missed_lines = []
            for idx, g in enumerate(missed_groups, 1):
                partner_tuple = g.get('partner_id')
                missed_count = g.get('partner_id_count') or g.get('__count') or 0
                missed_lines.append('%s. %s (%s missed)' % (idx, partner_tuple[1] if partner_tuple else _('Unknown'), missed_count))
            rec.top_5_missed_clients = '\n'.join(missed_lines) if missed_lines else _('No missed clients MTD')

            compliance = rec.visit_compliance_mtd or 0.0
            productive = rec.productive_rate_mtd or 0.0
            achievement = rec.achievement_rate_mtd or 0.0
            misses = rec.missed_calls_mtd or 0
            suspicious = rec.suspicious_visits_mtd or 0
            sku_diversity = min((rec.sku_mtd_count or 0) * 5.0, 100.0)
            route_score = min(compliance, 100.0) * 0.25
            target_score = min(achievement, 120.0) * 0.25
            sku_score = sku_diversity * 0.15
            missed_score = max(0.0, 100.0 - (misses * 10.0)) * 0.15
            productive_score = min(productive, 100.0) * 0.10
            control_score = max(0.0, 100.0 - (suspicious * 20.0)) * 0.10
            score = max(0.0, min(100.0, route_score + target_score + sku_score + missed_score + productive_score + control_score))
            rec.ai_coach_score = score

            # Leaderboard rank is based on MTD total sales within the same company.
            self.env.cr.execute("""
                SELECT COUNT(*) + 1
                  FROM sales_person_profile spp
                 WHERE spp.company_id = %s
                   AND COALESCE(spp.mtd_total_sales, 0) > %s
            """, (rec.company_id.id if rec.company_id else self.env.company.id, rec.mtd_total_sales or 0.0))
            rec.leaderboard_rank_mtd = self.env.cr.fetchone()[0] or 1

            badges = []
            if rec.leaderboard_rank_mtd == 1:
                badges.append(_('🥇 Team Leader'))
            elif rec.leaderboard_rank_mtd == 2:
                badges.append(_('🥈 Runner Up'))
            elif rec.leaderboard_rank_mtd == 3:
                badges.append(_('🥉 Top Three'))
            if compliance >= 95 and misses == 0:
                badges.append(_('Zero Miss Legend'))
            if rec.sku_mtd_count >= 10:
                badges.append(_('SKU Master'))
            if productive >= 80:
                badges.append(_('Conversion Hero'))
            if achievement >= 100:
                badges.append(_('Target Crusher'))
            rec.leaderboard_badges = ', '.join(badges) if badges else _('Keep pushing')

            recommendations = []
            if achievement < 80:
                recommendations.append(_('Push high-value and repeat clients to close the MTD target gap.'))
            if compliance < 80:
                recommendations.append(_('Improve route discipline: visit all system assigned clients before adding off-route calls.'))
            if misses:
                recommendations.append(_('Recover missed clients first; they are visible to supervisors and affect ranking.'))
            if rec.sku_mtd_count < 5:
                recommendations.append(_('Increase SKU diversity by cross-selling more product categories.'))
            if productive < 60:
                recommendations.append(_('Improve conversion: prepare order suggestions before each client visit.'))
            if suspicious:
                recommendations.append(_('Resolve GPS/control exceptions immediately with your supervisor.'))
            if not recommendations:
                recommendations.append(_('Maintain this performance and mentor weaker team members.'))
            rec.ai_coach_recommendations = '\n'.join('- %s' % r for r in recommendations)

            if score >= 85 and achievement >= 90 and compliance >= 85:
                rec.ai_coach_risk = 'excellent'
                rec.ai_appraisal_grade = 'good'
                rec.rank_recommendation = 'reward'
                rec.ai_coach_summary = _('Excellent performer: strong target achievement, route compliance, SKU breadth and client conversion.')
                rec.ai_performance_appraisal = _('Good: reward recommended. Strong target delivery, route compliance and productive call conversion. Keep assigning high-value clients and consider incentives.')
            elif score >= 70:
                rec.ai_coach_risk = 'good'
                rec.ai_appraisal_grade = 'good'
                rec.rank_recommendation = 'reward'
                rec.ai_coach_summary = _('Good performer: generally reliable, with clear opportunities to lift SKU mix, conversion or missed-client recovery.')
                rec.ai_performance_appraisal = _('Good: reward recommended. Performance is above acceptable level; use coaching to convert remaining gaps into stronger results.')
            elif score < 35 or (achievement < 35 and compliance < 50) or suspicious >= 5:
                rec.ai_coach_risk = 'critical'
                rec.ai_appraisal_grade = 'bad'
                rec.rank_recommendation = 'terminate'
                rec.ai_coach_summary = _('Critical risk: weak sales/route execution or repeated control exceptions require urgent management review.')
                rec.ai_performance_appraisal = _('Bad: termination review recommended. Performance shows very weak achievement/compliance or repeated control risks. Review evidence and HR policy before action.')
            else:
                rec.ai_coach_risk = 'warning'
                rec.ai_appraisal_grade = 'poor'
                rec.rank_recommendation = 'pip'
                rec.ai_coach_summary = _('Needs coaching: performance gaps are visible in route completion, target achievement, SKU diversity or missed clients.')
                rec.ai_performance_appraisal = _('Poor: PiP recommended. Salesperson needs a performance improvement plan focused on missed clients, daily route adherence, SKU selling and conversion.')


    def _supervised_salesperson_domain(self):
        """Restrict supervisors to only the salespeople on routes they supervise.

        Sales managers and system administrators keep full visibility. This is enforced
        at model search level so it applies to kanban, list, form, pivot and graph.
        """
        user = self.env.user
        if user.has_group('field_sales_route_plan.group_field_sales_manager') or user.has_group('base.group_system'):
            return []
        if user.has_group('field_sales_route_plan.group_field_sales_supervisor'):
            routes = self.env['sales.route'].sudo().search([('supervisor_ids', 'in', [user.id]), ('active', '=', True)])
            salesperson_ids = set(routes.mapped('user_id').ids) | set(routes.mapped('user_ids').ids)
            if not salesperson_ids:
                return [('id', '=', 0)]
            return [('user_id', 'in', list(salesperson_ids))]
        return [('user_id', '=', user.id)]

    def _search(self, args, offset=0, limit=None, order=None, count=False, access_rights_uid=None):
        args = expression.AND([args or [], self._supervised_salesperson_domain()])
        return super()._search(args, offset=offset, limit=limit, order=order, count=count, access_rights_uid=access_rights_uid)

    def read_group(self, domain, fields, groupby, offset=0, limit=None, orderby=False, lazy=True):
        domain = expression.AND([domain or [], self._supervised_salesperson_domain()])
        return super().read_group(domain, fields, groupby, offset=offset, limit=limit, orderby=orderby, lazy=lazy)

    def _date_sql(self):
        return {
            'today_start': "CURRENT_DATE",
            'tomorrow_start': "CURRENT_DATE + INTERVAL '1 day'",
            'month_start': "date_trunc('month', CURRENT_DATE)::date",
            'year_start': "date_trunc('year', CURRENT_DATE)::date",
        }

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH route_assignments AS (
                    SELECT ru.user_id, r.id route_id, r.name route_name
                    FROM sales_route_user_rel ru
                    JOIN sales_route r ON r.id = ru.route_id
                    WHERE r.active IS TRUE
                    UNION
                    SELECT r.user_id, r.id route_id, r.name route_name
                    FROM sales_route r
                    WHERE r.active IS TRUE AND r.user_id IS NOT NULL
                ),
                route_summary AS (
                    SELECT
                        ra.user_id,
                        COUNT(DISTINCT ra.route_id)::integer AS assigned_route_count,
                        STRING_AGG(DISTINCT ra.route_name, ', ' ORDER BY ra.route_name) AS assigned_route_names,
                        COUNT(DISTINCT rp.id)::integer AS customer_count
                    FROM route_assignments ra
                    LEFT JOIN res_partner rp ON rp.route_id = ra.route_id AND COALESCE(rp.active, TRUE) = TRUE
                    GROUP BY ra.user_id
                ),
                supervisor_summary AS (
                    SELECT
                        ra.user_id,
                        STRING_AGG(DISTINCT sup_partner.name, ', ' ORDER BY sup_partner.name) AS supervised_by_names
                    FROM route_assignments ra
                    JOIN sales_route_supervisor_rel srel ON srel.route_id = ra.route_id
                    JOIN res_users sup ON sup.id = srel.user_id
                    JOIN res_partner sup_partner ON sup_partner.id = sup.partner_id
                    GROUP BY ra.user_id
                ),
                plan_summary AS (
                    SELECT
                        p.user_id,
                        COUNT(*) FILTER (WHERE p.plan_date = CURRENT_DATE)::integer AS today_plan_count,
                        COUNT(*) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date)::integer AS mtd_plan_count,
                        COUNT(*) FILTER (WHERE p.plan_date >= date_trunc('year', CURRENT_DATE)::date)::integer AS ytd_plan_count,
                        COALESCE(SUM(p.total_planned_calls) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS planned_calls_mtd,
                        COALESCE(SUM(p.checked_in_calls) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS checked_in_calls_mtd,
                        COALESCE(SUM(p.missed_calls) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS missed_calls_mtd,
                        COALESCE(SUM(p.off_route_visits) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS off_route_visits_mtd,
                        COALESCE(SUM(p.suspicious_visits) FILTER (WHERE p.plan_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS suspicious_visits_mtd
                    FROM sales_route_plan p
                    GROUP BY p.user_id
                ),
                visit_summary AS (
                    SELECT
                        v.user_id,
                        COUNT(*) FILTER (WHERE v.check_in >= CURRENT_DATE AND v.check_in < CURRENT_DATE + INTERVAL '1 day')::integer AS today_visit_count,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE))::integer AS mtd_visit_count,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('year', CURRENT_DATE))::integer AS ytd_visit_count,
                        COUNT(*) FILTER (WHERE v.check_in >= CURRENT_DATE AND v.check_in < CURRENT_DATE + INTERVAL '1 day' AND (COALESCE(v.sale_order_total_amount,0) + COALESCE(v.pos_order_total_amount,0)) > 0)::integer AS today_productive_calls,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND (COALESCE(v.sale_order_total_amount,0) + COALESCE(v.pos_order_total_amount,0)) > 0)::integer AS mtd_productive_calls,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('year', CURRENT_DATE) AND (COALESCE(v.sale_order_total_amount,0) + COALESCE(v.pos_order_total_amount,0)) > 0)::integer AS ytd_productive_calls,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'marketing')::integer AS mtd_marketing_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'marketing')::integer AS mtd_marketing_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'sales')::integer AS mtd_sales_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'sales')::integer AS mtd_sales_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'van_sales')::integer AS mtd_van_sales_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'van_sales')::integer AS mtd_van_sales_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'retail_sales')::integer AS mtd_retail_sales_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'retail_sales')::integer AS mtd_retail_sales_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'merchandising')::integer AS mtd_merchandising_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'merchandising')::integer AS mtd_merchandising_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'delivery')::integer AS mtd_delivery_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'delivery')::integer AS mtd_delivery_visits,
                        COUNT(DISTINCT v.partner_id) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'other')::integer AS mtd_other_clients,
                        COUNT(*) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE) AND v.visit_purpose = 'other')::integer AS mtd_other_visits,
                        MAX(v.check_in) AS last_visit_date
                    FROM sales_route_visit v
                    WHERE v.check_in IS NOT NULL
                    GROUP BY v.user_id
                ),
                visit_money_summary AS (
                    SELECT
                        v.user_id,
                        -- Salesperson Profile Sales cards use POS paid/collection amounts.
                        -- Today/MTD/YTD Sales = POS Amount Paid captured on route visits.
                        COALESCE(SUM(v.pos_order_paid_amount) FILTER (WHERE v.check_in >= CURRENT_DATE AND v.check_in < CURRENT_DATE + INTERVAL '1 day'), 0) AS today_sales_metric,
                        COALESCE(SUM(v.pos_order_paid_amount) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE)), 0) AS mtd_sales_metric,
                        COALESCE(SUM(v.pos_order_paid_amount) FILTER (WHERE v.check_in >= date_trunc('year', CURRENT_DATE)), 0) AS ytd_sales_metric,
                        COALESCE(SUM(v.pos_order_total_amount) FILTER (WHERE v.check_in >= CURRENT_DATE AND v.check_in < CURRENT_DATE + INTERVAL '1 day'), 0) AS today_pos_order_total,
                        COALESCE(SUM(v.pos_order_paid_amount) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE)), 0) AS mtd_pos_payments,
                        COALESCE(SUM(v.pos_order_due_amount) FILTER (WHERE v.check_in >= CURRENT_DATE AND v.check_in < CURRENT_DATE + INTERVAL '1 day'), 0) AS today_pos_amount_due,
                        COALESCE(SUM(v.pos_order_due_amount) FILTER (WHERE v.check_in >= date_trunc('month', CURRENT_DATE)), 0) AS mtd_pos_amount_due,
                        COALESCE(SUM(v.pos_order_due_amount) FILTER (WHERE v.check_in >= date_trunc('year', CURRENT_DATE)), 0) AS ytd_pos_amount_due
                    FROM sales_route_visit v
                    WHERE v.check_in IS NOT NULL
                    GROUP BY v.user_id
                ),
                sale_summary AS (
                    SELECT
                        so.user_id,
                        COUNT(*) FILTER (WHERE so.date_order >= CURRENT_DATE AND so.date_order < CURRENT_DATE + INTERVAL '1 day')::integer AS today_sales_order_count,
                        COUNT(*) FILTER (WHERE so.date_order >= date_trunc('month', CURRENT_DATE))::integer AS mtd_sales_order_count,
                        COUNT(*) FILTER (WHERE so.date_order >= date_trunc('year', CURRENT_DATE))::integer AS ytd_sales_order_count,
                        COALESCE(SUM(so.amount_total) FILTER (WHERE so.date_order >= CURRENT_DATE AND so.date_order < CURRENT_DATE + INTERVAL '1 day'), 0) AS today_sales_amount,
                        COALESCE(SUM(so.amount_total) FILTER (WHERE so.date_order >= date_trunc('month', CURRENT_DATE)), 0) AS mtd_sales_amount,
                        COALESCE(SUM(so.amount_total) FILTER (WHERE so.date_order >= date_trunc('year', CURRENT_DATE)), 0) AS ytd_sales_amount,
                        MAX(so.date_order) AS last_order_date
                    FROM sale_order so
                    WHERE so.state IN ('sale', 'done')
                    GROUP BY so.user_id
                ),
                pos_summary AS (
                    SELECT
                        po.user_id,
                        COUNT(*) FILTER (WHERE po.date_order >= CURRENT_DATE AND po.date_order < CURRENT_DATE + INTERVAL '1 day')::integer AS today_pos_order_count,
                        COUNT(*) FILTER (WHERE po.date_order >= date_trunc('month', CURRENT_DATE))::integer AS mtd_pos_order_count,
                        COUNT(*) FILTER (WHERE po.date_order >= date_trunc('year', CURRENT_DATE))::integer AS ytd_pos_order_count,
                        COALESCE(SUM(po.amount_total) FILTER (WHERE po.date_order >= CURRENT_DATE AND po.date_order < CURRENT_DATE + INTERVAL '1 day'), 0) AS today_pos_amount,
                        COALESCE(SUM(po.amount_total) FILTER (WHERE po.date_order >= date_trunc('month', CURRENT_DATE)), 0) AS mtd_pos_amount,
                        COALESCE(SUM(po.amount_total) FILTER (WHERE po.date_order >= date_trunc('year', CURRENT_DATE)), 0) AS ytd_pos_amount
                    FROM pos_order po
                    WHERE po.state IN ('paid', 'done', 'invoiced')
                    GROUP BY po.user_id
                ),
                attendance_summary AS (
                    SELECT
                        a.user_id,
                        MAX(a.start_time) AS last_attendance_start,
                        MAX(a.end_time) AS last_attendance_end,
                        COALESCE(SUM(a.duration_hours) FILTER (WHERE a.attendance_date >= date_trunc('month', CURRENT_DATE)::date), 0) AS attendance_hours_mtd
                    FROM sales_route_attendance a
                    GROUP BY a.user_id
                ),
                game_summary AS (
                    SELECT
                        g.user_id,
                        COALESCE(SUM(g.total_points) FILTER (WHERE g.score_date >= date_trunc('month', CURRENT_DATE)::date), 0)::integer AS gamification_points_mtd
                    FROM sales_route_game_score g
                    GROUP BY g.user_id
                )
                SELECT
                    u.id AS id,
                    u.id AS user_id,
                    u.partner_id AS partner_id,
                    u.company_id AS company_id,
                    COALESCE(rs.assigned_route_count, 0) AS assigned_route_count,
                    COALESCE(rs.assigned_route_names, '') AS assigned_route_names,
                    COALESCE(ss.supervised_by_names, '') AS supervised_by_names,
                    COALESCE(rs.customer_count, 0) AS customer_count,
                    COALESCE(vs.mtd_marketing_clients, 0) AS mtd_marketing_clients,
                    COALESCE(vs.mtd_marketing_visits, 0) AS mtd_marketing_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_marketing_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_marketing_achievement,
                    COALESCE(vs.mtd_sales_clients, 0) AS mtd_sales_clients,
                    COALESCE(vs.mtd_sales_visits, 0) AS mtd_sales_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_sales_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_sales_achievement,
                    COALESCE(vs.mtd_van_sales_clients, 0) AS mtd_van_sales_clients,
                    COALESCE(vs.mtd_van_sales_visits, 0) AS mtd_van_sales_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_van_sales_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_van_sales_achievement,
                    COALESCE(vs.mtd_retail_sales_clients, 0) AS mtd_retail_sales_clients,
                    COALESCE(vs.mtd_retail_sales_visits, 0) AS mtd_retail_sales_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_retail_sales_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_retail_sales_achievement,
                    COALESCE(vs.mtd_merchandising_clients, 0) AS mtd_merchandising_clients,
                    COALESCE(vs.mtd_merchandising_visits, 0) AS mtd_merchandising_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_merchandising_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_merchandising_achievement,
                    COALESCE(vs.mtd_delivery_clients, 0) AS mtd_delivery_clients,
                    COALESCE(vs.mtd_delivery_visits, 0) AS mtd_delivery_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_delivery_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_delivery_achievement,
                    COALESCE(vs.mtd_other_clients, 0) AS mtd_other_clients,
                    COALESCE(vs.mtd_other_visits, 0) AS mtd_other_visits,
                    CASE WHEN COALESCE(rs.customer_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_other_clients, 0)::numeric / rs.customer_count::numeric) * 100, 2) ELSE 0 END AS mtd_other_achievement,
                    COALESCE(ps.today_plan_count, 0) AS today_plan_count,
                    COALESCE(ps.mtd_plan_count, 0) AS mtd_plan_count,
                    COALESCE(ps.ytd_plan_count, 0) AS ytd_plan_count,
                    COALESCE(vs.today_visit_count, 0) AS today_visit_count,
                    COALESCE(vs.mtd_visit_count, 0) AS mtd_visit_count,
                    COALESCE(vs.ytd_visit_count, 0) AS ytd_visit_count,
                    COALESCE(vs.today_productive_calls, 0) AS today_productive_calls,
                    COALESCE(vs.mtd_productive_calls, 0) AS mtd_productive_calls,
                    COALESCE(vs.ytd_productive_calls, 0) AS ytd_productive_calls,
                    COALESCE(ps.missed_calls_mtd, 0) AS missed_calls_mtd,
                    COALESCE(ps.off_route_visits_mtd, 0) AS off_route_visits_mtd,
                    COALESCE(ps.suspicious_visits_mtd, 0) AS suspicious_visits_mtd,
                    CASE WHEN COALESCE(ps.planned_calls_mtd, 0) > 0 THEN ROUND((COALESCE(ps.checked_in_calls_mtd, 0)::numeric / ps.planned_calls_mtd::numeric) * 100, 2) ELSE 0 END AS visit_compliance_mtd,
                    CASE WHEN COALESCE(vs.mtd_visit_count, 0) > 0 THEN ROUND((COALESCE(vs.mtd_productive_calls, 0)::numeric / vs.mtd_visit_count::numeric) * 100, 2) ELSE 0 END AS productive_rate_mtd,
                    COALESCE(sos.today_sales_order_count, 0) AS today_sales_order_count,
                    COALESCE(sos.mtd_sales_order_count, 0) AS mtd_sales_order_count,
                    COALESCE(sos.ytd_sales_order_count, 0) AS ytd_sales_order_count,
                    COALESCE(sos.today_sales_amount, 0) AS today_sales_amount,
                    COALESCE(sos.mtd_sales_amount, 0) AS mtd_sales_amount,
                    COALESCE(sos.ytd_sales_amount, 0) AS ytd_sales_amount,
                    COALESCE(pos.today_pos_order_count, 0) AS today_pos_order_count,
                    COALESCE(pos.mtd_pos_order_count, 0) AS mtd_pos_order_count,
                    COALESCE(pos.ytd_pos_order_count, 0) AS ytd_pos_order_count,
                    COALESCE(pos.today_pos_amount, 0) AS today_pos_amount,
                    COALESCE(pos.mtd_pos_amount, 0) AS mtd_pos_amount,
                    COALESCE(pos.ytd_pos_amount, 0) AS ytd_pos_amount,
                    COALESCE(vms.today_pos_amount_due, 0) AS today_pos_amount_due,
                    COALESCE(vms.mtd_pos_amount_due, 0) AS mtd_pos_amount_due,
                    COALESCE(vms.ytd_pos_amount_due, 0) AS ytd_pos_amount_due,
                    COALESCE(vms.today_sales_metric, sos.today_sales_amount, 0) AS today_total_sales,
                    COALESCE(vms.mtd_sales_metric, sos.mtd_sales_amount, 0) AS mtd_total_sales,
                    COALESCE(vms.ytd_sales_metric, sos.ytd_sales_amount, 0) AS ytd_total_sales,
                    vs.last_visit_date AS last_visit_date,
                    sos.last_order_date AS last_order_date,
                    ats.last_attendance_start AS last_attendance_start,
                    ats.last_attendance_end AS last_attendance_end,
                    COALESCE(ats.attendance_hours_mtd, 0) AS attendance_hours_mtd,
                    COALESCE(gs.gamification_points_mtd, 0) AS gamification_points_mtd
                FROM res_users u
                LEFT JOIN route_summary rs ON rs.user_id = u.id
                LEFT JOIN supervisor_summary ss ON ss.user_id = u.id
                LEFT JOIN plan_summary ps ON ps.user_id = u.id
                LEFT JOIN visit_summary vs ON vs.user_id = u.id
                LEFT JOIN sale_summary sos ON sos.user_id = u.id
                LEFT JOIN pos_summary pos ON pos.user_id = u.id
                LEFT JOIN visit_money_summary vms ON vms.user_id = u.id
                LEFT JOIN attendance_summary ats ON ats.user_id = u.id
                LEFT JOIN game_summary gs ON gs.user_id = u.id
                -- Only show true field salespeople assigned to active market routes.
                -- This prevents ordinary employees/users with sales, POS, visit, or attendance history
                -- from appearing in Sales Person Profiles unless they are explicitly assigned on
                -- sales.route.user_id or sales.route.user_ids.
                WHERE u.active IS TRUE
                  AND rs.user_id IS NOT NULL
            )
        """ % self._table)

    def _action_for(self, name, model, domain, view_mode='tree,form'):
        self.ensure_one()
        return {'type': 'ir.actions.act_window', 'name': name, 'res_model': model, 'view_mode': view_mode, 'domain': domain, 'context': {'search_default_this_month': 1}}

    def action_open_period_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Select Sales / Marketing Period'),
            'res_model': 'sales.marketing.period.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': dict(self.env.context or {}, active_model=self._name, active_id=self.id),
        }

    def action_view_period_productive_clients(self):
        self.ensure_one()
        start_date, end_date, label = self._selected_sales_marketing_period()
        route_ids = self.env['sales.route'].sudo().search([('active', '=', True), '|', ('user_id', '=', self.user_id.id), ('user_ids', 'in', [self.user_id.id])]).ids
        return self._action_for(
            _('Productive Clients Served - %s') % label,
            'sales.route.visit',
            self._productive_visit_domain_for_period(start_date, end_date, self.user_id.id, route_ids),
            'tree,form,pivot,graph'
        )

    def action_view_purpose_visits(self, purpose):
        self.ensure_one()
        return self._action_for(
            _('%s Visit Clients') % dict(self.env['sales.route.visit']._fields['visit_purpose'].selection).get(purpose, purpose),
            'sales.route.visit',
            [('user_id', '=', self.user_id.id), ('visit_purpose', '=', purpose), ('check_in', '!=', False)],
            'tree,form,pivot,graph'
        )

    def action_view_marketing_clients(self):
        return self.action_view_purpose_visits('marketing')

    def action_view_sales_clients(self):
        return self.action_view_purpose_visits('sales')

    def action_view_van_sales_clients(self):
        return self.action_view_purpose_visits('van_sales')

    def action_view_retail_sales_clients(self):
        return self.action_view_purpose_visits('retail_sales')

    def action_view_merchandising_clients(self):
        return self.action_view_purpose_visits('merchandising')

    def action_view_delivery_clients(self):
        return self.action_view_purpose_visits('delivery')

    def action_view_other_purpose_clients(self):
        return self.action_view_purpose_visits('other')

    def action_view_routes(self):
        self.ensure_one()
        return self._action_for(_('Assigned Routes'), 'sales.route', ['|', ('user_id', '=', self.user_id.id), ('user_ids', 'in', [self.user_id.id])])

    def action_view_plans(self):
        return self._action_for(_('Route Plans'), 'sales.route.plan', [('user_id', '=', self.user_id.id)], 'tree,form,pivot,graph')

    def action_view_visits(self):
        return self._action_for(_('Route Visits'), 'sales.route.visit', [('user_id', '=', self.user_id.id)], 'tree,form,pivot,graph')

    def action_view_sale_orders(self):
        return self._action_for(_('Sales Orders'), 'sale.order', [('user_id', '=', self.user_id.id)], 'tree,form,pivot,graph')

    def action_view_pos_orders(self):
        return self._action_for(_('POS Orders'), 'pos.order', [('user_id', '=', self.user_id.id)], 'tree,form')

    def action_view_attendance(self):
        return self._action_for(_('Attendance'), 'sales.route.attendance', [('user_id', '=', self.user_id.id)])
