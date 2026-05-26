from odoo import fields, models, tools


class SalesRouteDashboardReport(models.Model):
    _name = 'sales.route.dashboard.report'
    _description = 'Field Sales Manager Dashboard Report'
    _auto = False
    _rec_name = 'route_id'
    _order = 'plan_date desc'

    plan_date = fields.Date(readonly=True)
    user_id = fields.Many2one('res.users', readonly=True)
    route_id = fields.Many2one('sales.route', readonly=True)
    team_id = fields.Many2one('crm.team', readonly=True)
    planned_calls = fields.Integer(readonly=True)
    visited_calls = fields.Integer(readonly=True)
    productive_calls = fields.Integer(readonly=True)
    unproductive_calls = fields.Integer(readonly=True)
    missed_calls = fields.Integer(readonly=True)
    off_route_visits = fields.Integer(readonly=True)
    suspicious_visits = fields.Integer(readonly=True)
    gps_compliant_visits = fields.Integer(readonly=True)
    total_sales_amount = fields.Float(readonly=True)
    mtd_visits = fields.Integer(readonly=True, string='MTD Visits')
    ytd_visits = fields.Integer(readonly=True, string='YTD Visits')
    today_sales_orders = fields.Integer(readonly=True, string='Today Sales Orders')
    mtd_sales_orders = fields.Integer(readonly=True, string='MTD Sales Orders')
    ytd_sales_orders = fields.Integer(readonly=True, string='YTD Sales Orders')
    today_sales_amount = fields.Float(readonly=True, string='Today Sales')
    mtd_sales_amount = fields.Float(readonly=True, string='MTD Sales')
    ytd_sales_amount = fields.Float(readonly=True, string='YTD Sales')
    today_van_sales_amount = fields.Float(readonly=True, string='Today Van Sales')
    mtd_van_sales_amount = fields.Float(readonly=True, string='MTD Van Sales')
    ytd_van_sales_amount = fields.Float(readonly=True, string='YTD Van Sales')
    today_pos_payments = fields.Float(readonly=True, string='Today POS Payments')
    mtd_pos_payments = fields.Float(readonly=True, string='MTD POS Payments')
    ytd_pos_payments = fields.Float(readonly=True, string='YTD POS Payments')
    today_amount_due = fields.Float(readonly=True, string='Today Amount Due')
    mtd_amount_due = fields.Float(readonly=True, string='MTD Amount Due')
    ytd_amount_due = fields.Float(readonly=True, string='YTD Amount Due')
    visit_compliance = fields.Float(readonly=True, string='Visited %')
    productive_compliance = fields.Float(readonly=True, string='Productive KPI %')
    route_customer_count = fields.Integer(readonly=True, string='Route Clients')
    mtd_unique_clients_served = fields.Integer(readonly=True, string='MTD Unique Clients Served')
    mtd_route_client_achievement = fields.Float(readonly=True, string='MTD Route Client Achievement %')
    marketing_clients_served = fields.Integer(readonly=True, string='Marketing Clients Served')
    marketing_visit_count = fields.Integer(readonly=True, string='Marketing Visits')
    sales_clients_served = fields.Integer(readonly=True, string='Sales Clients Served')
    sales_visit_count = fields.Integer(readonly=True, string='Sales Visits')
    van_sales_clients_served = fields.Integer(readonly=True, string='Van Sales Clients Served')
    van_sales_visit_count = fields.Integer(readonly=True, string='Van Sales Visits')
    retail_clients_served = fields.Integer(readonly=True, string='Retail Clients Served')
    retail_visit_count = fields.Integer(readonly=True, string='Retail Visits')
    merchandising_clients_served = fields.Integer(readonly=True, string='Merchandising Clients Served')
    merchandising_visit_count = fields.Integer(readonly=True, string='Merchandising Visits')
    delivery_clients_served = fields.Integer(readonly=True, string='Delivery Clients Served')
    delivery_visit_count = fields.Integer(readonly=True, string='Delivery Visits')
    other_clients_served = fields.Integer(readonly=True, string='Other Clients Served')
    other_visit_count = fields.Integer(readonly=True, string='Other Visits')

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    p.id AS id,
                    p.plan_date AS plan_date,
                    p.user_id AS user_id,
                    p.route_id AS route_id,
                    p.team_id AS team_id,
                    p.total_planned_calls AS planned_calls,
                    p.checked_in_calls AS visited_calls,
                    p.productive_calls AS productive_calls,
                    p.unproductive_calls AS unproductive_calls,
                    p.missed_calls AS missed_calls,
                    COALESCE(SUM(CASE WHEN v.within_allowed_radius IS FALSE AND v.check_in IS NOT NULL THEN 1 ELSE 0 END), 0)::integer AS off_route_visits,
                    COALESCE(SUM(CASE WHEN v.suspicious_visit IS TRUE THEN 1 ELSE 0 END), 0)::integer AS suspicious_visits,
                    COALESCE(SUM(CASE WHEN v.within_allowed_radius IS TRUE THEN 1 ELSE 0 END), 0)::integer AS gps_compliant_visits,
                    p.total_sales_amount AS total_sales_amount,
                    (
                        SELECT COUNT(DISTINCT rp.id)::integer
                        FROM res_partner rp
                        WHERE rp.route_id = p.route_id AND COALESCE(rp.active, TRUE) = TRUE
                    ) AS route_customer_count,
                    (
                        SELECT COUNT(DISTINCT uv.partner_id)::integer
                        FROM sales_route_visit uv
                        WHERE uv.route_id = p.route_id AND uv.partner_id IS NOT NULL AND uv.check_in IS NOT NULL
                          AND uv.state IN ('checked_in', 'checked_out', 'done')
                          AND uv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND uv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_unique_clients_served,
                    (
                        SELECT CASE WHEN COUNT(DISTINCT rp.id) > 0 THEN ROUND((
                            (SELECT COUNT(DISTINCT uv.partner_id)::numeric
                             FROM sales_route_visit uv
                             WHERE uv.route_id = p.route_id AND uv.partner_id IS NOT NULL AND uv.check_in IS NOT NULL
                               AND uv.state IN ('checked_in', 'checked_out', 'done')
                               AND uv.check_in >= date_trunc('month', p.plan_date::timestamp)
                               AND uv.check_in < (p.plan_date::timestamp + interval '1 day'))
                            / COUNT(DISTINCT rp.id)::numeric) * 100, 2) ELSE 0 END
                        FROM res_partner rp
                        WHERE rp.route_id = p.route_id AND COALESCE(rp.active, TRUE) = TRUE
                    ) AS mtd_route_client_achievement,
                    (
                        SELECT COUNT(DISTINCT mv.partner_id)::integer FROM sales_route_visit mv
                        WHERE mv.route_id = p.route_id AND mv.partner_id IS NOT NULL AND mv.check_in IS NOT NULL
                          AND mv.visit_purpose = 'marketing' AND mv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS marketing_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit mv
                        WHERE mv.route_id = p.route_id AND mv.check_in IS NOT NULL AND mv.visit_purpose = 'marketing'
                          AND mv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS marketing_visit_count,
                    (
                        SELECT COUNT(DISTINCT sv.partner_id)::integer FROM sales_route_visit sv
                        WHERE sv.route_id = p.route_id AND sv.partner_id IS NOT NULL AND sv.check_in IS NOT NULL
                          AND sv.visit_purpose = 'sales' AND sv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND sv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS sales_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit sv
                        WHERE sv.route_id = p.route_id AND sv.check_in IS NOT NULL AND sv.visit_purpose = 'sales'
                          AND sv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND sv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS sales_visit_count,
                    (
                        SELECT COUNT(DISTINCT vv.partner_id)::integer FROM sales_route_visit vv
                        WHERE vv.route_id = p.route_id AND vv.partner_id IS NOT NULL AND vv.check_in IS NOT NULL
                          AND vv.visit_purpose = 'van_sales' AND vv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND vv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS van_sales_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit vv
                        WHERE vv.route_id = p.route_id AND vv.check_in IS NOT NULL AND vv.visit_purpose = 'van_sales'
                          AND vv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND vv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS van_sales_visit_count,
                    (
                        SELECT COUNT(DISTINCT rv.partner_id)::integer FROM sales_route_visit rv
                        WHERE rv.route_id = p.route_id AND rv.partner_id IS NOT NULL AND rv.check_in IS NOT NULL
                          AND rv.visit_purpose = 'retail_sales' AND rv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND rv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS retail_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit rv
                        WHERE rv.route_id = p.route_id AND rv.check_in IS NOT NULL AND rv.visit_purpose = 'retail_sales'
                          AND rv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND rv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS retail_visit_count,
                    (
                        SELECT COUNT(DISTINCT hv.partner_id)::integer FROM sales_route_visit hv
                        WHERE hv.route_id = p.route_id AND hv.partner_id IS NOT NULL AND hv.check_in IS NOT NULL
                          AND hv.visit_purpose = 'merchandising' AND hv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND hv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS merchandising_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit hv
                        WHERE hv.route_id = p.route_id AND hv.check_in IS NOT NULL AND hv.visit_purpose = 'merchandising'
                          AND hv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND hv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS merchandising_visit_count,
                    (
                        SELECT COUNT(DISTINCT dv.partner_id)::integer FROM sales_route_visit dv
                        WHERE dv.route_id = p.route_id AND dv.partner_id IS NOT NULL AND dv.check_in IS NOT NULL
                          AND dv.visit_purpose = 'delivery' AND dv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND dv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS delivery_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit dv
                        WHERE dv.route_id = p.route_id AND dv.check_in IS NOT NULL AND dv.visit_purpose = 'delivery'
                          AND dv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND dv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS delivery_visit_count,
                    (
                        SELECT COUNT(DISTINCT ov.partner_id)::integer FROM sales_route_visit ov
                        WHERE ov.route_id = p.route_id AND ov.partner_id IS NOT NULL AND ov.check_in IS NOT NULL
                          AND ov.visit_purpose = 'other' AND ov.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND ov.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS other_clients_served,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit ov
                        WHERE ov.route_id = p.route_id AND ov.check_in IS NOT NULL AND ov.visit_purpose = 'other'
                          AND ov.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND ov.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS other_visit_count,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit mv
                        WHERE mv.user_id = p.user_id AND mv.check_in IS NOT NULL
                          AND mv.state IN ('checked_in', 'checked_out', 'done')
                          AND mv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_visits,
                    (
                        SELECT COUNT(*)::integer FROM sales_route_visit yv
                        WHERE yv.user_id = p.user_id AND yv.check_in IS NOT NULL
                          AND yv.state IN ('checked_in', 'checked_out', 'done')
                          AND yv.check_in >= date_trunc('year', p.plan_date::timestamp)
                          AND yv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_visits,
                    (
                        SELECT COUNT(*)::integer FROM sale_order tod_o
                        WHERE tod_o.user_id = p.user_id AND tod_o.state IN ('sale', 'done')
                          AND tod_o.date_order >= p.plan_date::timestamp
                          AND tod_o.date_order < (p.plan_date::timestamp + interval '1 day')
                    ) AS today_sales_orders,
                    (
                        SELECT COUNT(*)::integer FROM sale_order mo
                        WHERE mo.user_id = p.user_id AND mo.state IN ('sale', 'done')
                          AND mo.date_order >= date_trunc('month', p.plan_date::timestamp)
                          AND mo.date_order < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_sales_orders,
                    (
                        SELECT COUNT(*)::integer FROM sale_order yo
                        WHERE yo.user_id = p.user_id AND yo.state IN ('sale', 'done')
                          AND yo.date_order >= date_trunc('year', p.plan_date::timestamp)
                          AND yo.date_order < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_sales_orders,
                    (
                        SELECT COALESCE(SUM(COALESCE(tinv.pos_order_total_amount, 0.0)), 0.0)
                        FROM sales_route_visit tinv
                        WHERE tinv.user_id = p.user_id AND tinv.check_in IS NOT NULL
                          AND tinv.check_in >= p.plan_date::timestamp
                          AND tinv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS today_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(mcol.pos_order_paid_amount, COALESCE(mcol.pos_order_payment_amount, 0.0))), 0.0)
                        FROM sales_route_visit mcol
                        WHERE mcol.user_id = p.user_id AND mcol.check_in IS NOT NULL
                          AND mcol.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mcol.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(yvar.pos_order_due_amount, 0.0)), 0.0)
                        FROM sales_route_visit yvar
                        WHERE yvar.user_id = p.user_id AND yvar.check_in IS NOT NULL
                          AND yvar.check_in >= date_trunc('year', p.plan_date::timestamp)
                          AND yvar.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(tvv.sale_order_total_amount, 0.0) + COALESCE(tvv.pos_order_total_amount, 0.0)), 0.0)
                        FROM sales_route_visit tvv
                        WHERE tvv.user_id = p.user_id AND tvv.check_in IS NOT NULL
                          AND (tvv.visit_purpose = 'van_sales')
                          AND tvv.check_in >= p.plan_date::timestamp
                          AND tvv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS today_van_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(mvv.sale_order_total_amount, 0.0) + COALESCE(mvv.pos_order_total_amount, 0.0)), 0.0)
                        FROM sales_route_visit mvv
                        WHERE mvv.user_id = p.user_id AND mvv.check_in IS NOT NULL
                          AND (mvv.visit_purpose = 'van_sales')
                          AND mvv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mvv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_van_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(yvv.sale_order_total_amount, 0.0) + COALESCE(yvv.pos_order_total_amount, 0.0)), 0.0)
                        FROM sales_route_visit yvv
                        WHERE yvv.user_id = p.user_id AND yvv.check_in IS NOT NULL
                          AND (yvv.visit_purpose = 'van_sales')
                          AND yvv.check_in >= date_trunc('year', p.plan_date::timestamp)
                          AND yvv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_van_sales_amount,
                    (
                        SELECT COALESCE(SUM(COALESCE(tv.pos_order_payment_amount, 0.0)), 0.0)
                        FROM sales_route_visit tv
                        WHERE tv.user_id = p.user_id AND tv.check_in IS NOT NULL
                          AND tv.check_in >= p.plan_date::timestamp
                          AND tv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS today_pos_payments,
                    (
                        SELECT COALESCE(SUM(COALESCE(mv.pos_order_payment_amount, 0.0)), 0.0)
                        FROM sales_route_visit mv
                        WHERE mv.user_id = p.user_id AND mv.check_in IS NOT NULL
                          AND mv.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND mv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_pos_payments,
                    (
                        SELECT COALESCE(SUM(COALESCE(yv.pos_order_payment_amount, 0.0)), 0.0)
                        FROM sales_route_visit yv
                        WHERE yv.user_id = p.user_id AND yv.check_in IS NOT NULL
                          AND yv.check_in >= date_trunc('year', p.plan_date::timestamp)
                          AND yv.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_pos_payments,
                    (
                        SELECT COALESCE(SUM(COALESCE(td.pos_order_due_amount, 0.0)), 0.0)
                        FROM sales_route_visit td
                        WHERE td.user_id = p.user_id AND td.check_in IS NOT NULL
                          AND td.check_in >= p.plan_date::timestamp
                          AND td.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS today_amount_due,
                    (
                        SELECT COALESCE(SUM(COALESCE(md.pos_order_due_amount, 0.0)), 0.0)
                        FROM sales_route_visit md
                        WHERE md.user_id = p.user_id AND md.check_in IS NOT NULL
                          AND md.check_in >= date_trunc('month', p.plan_date::timestamp)
                          AND md.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS mtd_amount_due,
                    (
                        SELECT COALESCE(SUM(COALESCE(yd.pos_order_due_amount, 0.0)), 0.0)
                        FROM sales_route_visit yd
                        WHERE yd.user_id = p.user_id AND yd.check_in IS NOT NULL
                          AND yd.check_in >= date_trunc('year', p.plan_date::timestamp)
                          AND yd.check_in < (p.plan_date::timestamp + interval '1 day')
                    ) AS ytd_amount_due,
                    CASE WHEN p.total_planned_calls > 0 THEN (p.checked_in_calls::float / p.total_planned_calls::float) * 100 ELSE 0 END AS visit_compliance,
                    p.kpi_achievement AS productive_compliance
                FROM sales_route_plan p
                LEFT JOIN sales_route_visit v ON v.plan_id = p.id
                GROUP BY p.id, p.plan_date, p.user_id, p.route_id, p.team_id, p.total_planned_calls, p.checked_in_calls,
                         p.productive_calls, p.unproductive_calls, p.missed_calls, p.total_sales_amount, p.kpi_achievement
            )
        """ % self._table)
