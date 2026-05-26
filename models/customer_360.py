from odoo import api, fields, models, tools, _


class FieldSalesCustomer360(models.Model):
    _name = 'field.sales.customer.360'
    _description = 'Customer 360 Commercial Intelligence'
    _auto = False
    _order = 'ytd_sales desc, last_visit_date desc, id desc'

    partner_id = fields.Many2one('res.partner', string='Client', readonly=True)
    route_id = fields.Many2one('sales.route', string='Route', readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Assigned Salesperson', readonly=True)
    customer_classification = fields.Char(string='Client Class', readonly=True)
    route_sales_potential = fields.Float(string='Sales Potential', readonly=True)
    last_visit_date = fields.Datetime(string='Last Visit', readonly=True)
    last_productive_date = fields.Datetime(string='Last Productive Call', readonly=True)
    visit_count_30 = fields.Integer(string='Visits 30 Days', readonly=True)
    productive_count_30 = fields.Integer(string='Productive Calls 30 Days', readonly=True)
    today_sales = fields.Monetary(string='Today Sales', currency_field='currency_id', readonly=True)
    mtd_sales = fields.Monetary(string='MTD Sales', currency_field='currency_id', readonly=True)
    ytd_sales = fields.Monetary(string='YTD Sales', currency_field='currency_id', readonly=True)
    pos_collections_ytd = fields.Monetary(string='YTD POS Collections', currency_field='currency_id', readonly=True)
    amount_due_ytd = fields.Monetary(string='YTD POS Amount Due', currency_field='currency_id', readonly=True)
    avg_basket = fields.Monetary(string='Average Basket', currency_field='currency_id', readonly=True)
    sale_order_count_ytd = fields.Integer(string='YTD Orders', readonly=True)
    communication_summary = fields.Text(string='Latest Communication', readonly=True)
    ai_insight = fields.Text(string='AI Commercial Insight', readonly=True)
    opportunity_note = fields.Text(string='Suggested Opportunity', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                WITH base AS (
                    SELECT
                        rp.id AS id,
                        rp.id AS partner_id,
                        rp.route_id AS route_id,
                        rp.route_user_id AS salesperson_id,
                        COALESCE(rp.customer_classification, '') AS customer_classification,
                        COALESCE(rp.route_sales_potential, 0.0) AS route_sales_potential,
                        (SELECT company.currency_id FROM res_company company ORDER BY company.id LIMIT 1) AS currency_id,
                        (SELECT MAX(v.check_in) FROM sales_route_visit v WHERE v.partner_id = rp.id) AS last_visit_date,
                        (SELECT MAX(v.check_in) FROM sales_route_visit v WHERE v.partner_id = rp.id AND COALESCE(v.pos_order_total_amount,0) > 0) AS last_productive_date,
                        (SELECT COUNT(*) FROM sales_route_visit v WHERE v.partner_id = rp.id AND v.check_in >= (now() - interval '30 days')) AS visit_count_30,
                        (SELECT COUNT(*) FROM sales_route_visit v WHERE v.partner_id = rp.id AND COALESCE(v.pos_order_total_amount,0) > 0 AND v.check_in >= (now() - interval '30 days')) AS productive_count_30,
                        (SELECT COALESCE(SUM(so.amount_total),0) FROM sale_order so WHERE so.partner_id = rp.id AND so.state IN ('sale','done') AND so.date_order::date = CURRENT_DATE) AS today_sales,
                        (SELECT COALESCE(SUM(so.amount_total),0) FROM sale_order so WHERE so.partner_id = rp.id AND so.state IN ('sale','done') AND so.date_order::date >= date_trunc('month', CURRENT_DATE)::date AND so.date_order::date <= CURRENT_DATE) AS mtd_sales,
                        (SELECT COALESCE(SUM(so.amount_total),0) FROM sale_order so WHERE so.partner_id = rp.id AND so.state IN ('sale','done') AND so.date_order::date >= date_trunc('year', CURRENT_DATE)::date AND so.date_order::date <= CURRENT_DATE) AS ytd_sales,
                        (SELECT COUNT(*) FROM sale_order so WHERE so.partner_id = rp.id AND so.state IN ('sale','done') AND so.date_order::date >= date_trunc('year', CURRENT_DATE)::date AND so.date_order::date <= CURRENT_DATE) AS sale_order_count_ytd,
                        (SELECT COALESCE(SUM(v.pos_order_paid_amount),0) FROM sales_route_visit v WHERE v.partner_id = rp.id AND v.check_in::date >= date_trunc('year', CURRENT_DATE)::date AND v.check_in::date <= CURRENT_DATE) AS pos_collections_ytd,
                        (SELECT COALESCE(SUM(v.pos_order_due_amount),0) FROM sales_route_visit v WHERE v.partner_id = rp.id AND v.check_in::date >= date_trunc('year', CURRENT_DATE)::date AND v.check_in::date <= CURRENT_DATE) AS amount_due_ytd,
                        (SELECT COALESCE(AVG(so.amount_total),0) FROM sale_order so WHERE so.partner_id = rp.id AND so.state IN ('sale','done') AND so.date_order::date >= date_trunc('year', CURRENT_DATE)::date AND so.date_order::date <= CURRENT_DATE) AS avg_basket,
                        (SELECT COALESCE(v.marketing_notes, v.marketing_activities_done, v.followup_note, v.note, '') FROM sales_route_visit v WHERE v.partner_id = rp.id ORDER BY v.check_in DESC NULLS LAST, v.id DESC LIMIT 1) AS communication_summary
                    FROM res_partner rp
                    WHERE COALESCE(rp.customer_rank,0) > 0 OR rp.route_id IS NOT NULL
                )
                SELECT
                    base.*,
                    CASE
                        WHEN base.ytd_sales <= 0 AND base.visit_count_30 > 0 THEN 'Visited recently but no captured sales. Review conversion and offer relevant category bundles.'
                        WHEN base.amount_due_ytd > (base.pos_collections_ytd * 0.5) THEN 'Collections risk is high. Prioritize settlement before extending more credit.'
                        WHEN base.last_visit_date IS NULL THEN 'Client has not been visited. Add to route coverage plan.'
                        WHEN base.last_visit_date < (now() - interval '30 days') THEN 'Client has not been visited in 30+ days. Schedule recovery call.'
                        ELSE 'Client is active. Continue coverage and grow basket/category penetration.'
                    END AS ai_insight,
                    CASE
                        WHEN base.mtd_sales <= 0 THEN 'Opportunity: recover this client this month with priority visit and targeted offer.'
                        WHEN base.avg_basket > 0 THEN 'Opportunity: grow average basket by cross-selling adjacent product categories.'
                        ELSE 'Opportunity: confirm buying needs and activate first productive order.'
                    END AS opportunity_note
                FROM base
            )
        """ % self._table)


class FieldSalesAIOpportunity(models.Model):
    _name = 'field.sales.ai.opportunity'
    _description = 'AI Sales Opportunity Engine'
    _auto = False
    _order = 'opportunity_score desc, id desc'

    partner_id = fields.Many2one('res.partner', string='Client', readonly=True)
    route_id = fields.Many2one('sales.route', string='Route', readonly=True)
    salesperson_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    opportunity_type = fields.Char(string='Opportunity Type', readonly=True)
    opportunity_score = fields.Float(string='Score', readonly=True)
    estimated_value = fields.Monetary(string='Estimated Value', currency_field='currency_id', readonly=True)
    recommendation = fields.Text(string='AI Recommendation', readonly=True)
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT
                    c.id AS id,
                    c.partner_id,
                    c.route_id,
                    c.salesperson_id,
                    CASE
                        WHEN c.ytd_sales <= 0 THEN 'Dormant / No YTD Purchase'
                        WHEN c.amount_due_ytd > (c.pos_collections_ytd * 0.5) THEN 'Collection Recovery'
                        WHEN c.mtd_sales <= 0 THEN 'Monthly Recovery'
                        ELSE 'Basket Growth'
                    END AS opportunity_type,
                    CASE
                        WHEN c.ytd_sales <= 0 THEN 95
                        WHEN c.mtd_sales <= 0 THEN 80
                        WHEN c.amount_due_ytd > (c.pos_collections_ytd * 0.5) THEN 75
                        ELSE 55
                    END AS opportunity_score,
                    GREATEST(COALESCE(c.route_sales_potential,0), COALESCE(c.avg_basket,0), COALESCE(c.mtd_sales,0) * 0.25) AS estimated_value,
                    CASE
                        WHEN c.ytd_sales <= 0 THEN 'Visit and activate this client. Start with high-moving categories and confirm decision maker/payment readiness.'
                        WHEN c.mtd_sales <= 0 THEN 'Client has no current month purchase. Schedule a recovery call and propose a focused order.'
                        WHEN c.amount_due_ytd > (c.pos_collections_ytd * 0.5) THEN 'Prioritize collections and settlement before growing exposure.'
                        ELSE 'Upsell/cross-sell by adding complementary product categories to the next order.'
                    END AS recommendation,
                    c.currency_id
                FROM field_sales_customer_360 c
            )
        """ % self._table)


class FieldSalesOfflineQueue(models.Model):
    _name = 'field.sales.offline.queue'
    _description = 'Field Sales Offline Sync Queue'
    _order = 'create_date desc'

    name = fields.Char(default='Offline Sync Item', required=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, index=True, required=True)
    model_name = fields.Char(string='Target Model', required=True)
    operation = fields.Selection([('create', 'Create'), ('write', 'Update')], default='create', required=True)
    payload = fields.Text(string='Payload JSON')
    state = fields.Selection([('pending', 'Pending'), ('synced', 'Synced'), ('failed', 'Failed')], default='pending', index=True)
    error_message = fields.Text(string='Last Error')
    synced_on = fields.Datetime(string='Synced On')

    def action_mark_synced(self):
        self.write({'state': 'synced', 'synced_on': fields.Datetime.now(), 'error_message': False})
        return True

    def action_mark_failed(self):
        self.write({'state': 'failed'})
        return True
