from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FMCGDistributorScorecard(models.Model):
    _name = 'fmcg.distributor.scorecard'
    _description = 'FMCG Distributor Performance Scorecard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(default='Distributor Scorecard', required=True, tracking=True)
    distributor_id = fields.Many2one('res.partner', string='Distributor', required=True, domain=[('fmcg_partner_type', '=', 'distributor')], tracking=True)
    depot_id = fields.Many2one('fmcg.depot', string='Depot')
    date_from = fields.Date(required=True, default=fields.Date.context_today)
    date_to = fields.Date(required=True, default=fields.Date.context_today)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    sell_in_amount = fields.Monetary(string='Sell-in Value')
    sell_out_amount = fields.Monetary(string='Sell-out Value')
    fulfilment_rate = fields.Float(string='Fulfilment %')
    stock_aging_days = fields.Float(string='Average Stock Aging Days')
    gross_margin = fields.Monetary(string='Gross Margin')
    route_count = fields.Integer(string='Routes Covered')
    outlet_count = fields.Integer(string='Outlets Served')
    score = fields.Float(string='Distributor Score', compute='_compute_score', store=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed'), ('closed', 'Closed')], default='draft', tracking=True)
    note = fields.Text()

    @api.depends('sell_in_amount', 'sell_out_amount', 'fulfilment_rate', 'stock_aging_days')
    def _compute_score(self):
        for rec in self:
            sales_score = 0.0
            if rec.sell_in_amount:
                sales_score = min((rec.sell_out_amount / rec.sell_in_amount) * 40.0, 40.0)
            fulfilment_score = min(rec.fulfilment_rate * 0.4, 40.0)
            aging_penalty = min(rec.stock_aging_days / 3.0, 20.0)
            rec.score = max(sales_score + fulfilment_score - aging_penalty + 20.0, 0.0)

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_close(self):
        self.write({'state': 'closed'})


class FMCGVanSettlement(models.Model):
    _name = 'fmcg.van.settlement'
    _description = 'Advanced VAN Settlement / Profitability'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New VAN Settlement', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    load_id = fields.Many2one('fmcg.van.stock.load', string='VAN Load / Dispatch Sheet', required=True)
    van_id = fields.Many2one('fmcg.van.vehicle', related='load_id.van_id', store=True)
    user_id = fields.Many2one('res.users', related='load_id.user_id', store=True, string='Salesperson')
    route_id = fields.Many2one('sales.route', related='load_id.route_id', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    sales_amount = fields.Monetary(string='Sales Value')
    cash_collected = fields.Monetary()
    mobile_money_collected = fields.Monetary()
    cheque_collected = fields.Monetary()
    total_collected = fields.Monetary(compute='_compute_totals', store=True)
    expected_amount = fields.Monetary(string='Expected Collection')
    variance_amount = fields.Monetary(compute='_compute_totals', store=True)
    operating_cost = fields.Monetary(string='Route Operating Cost')
    gross_profit = fields.Monetary(compute='_compute_totals', store=True)
    state = fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('rejected','Rejected')], default='draft', tracking=True)
    note = fields.Text()

    @api.depends('cash_collected', 'mobile_money_collected', 'cheque_collected', 'expected_amount', 'sales_amount', 'operating_cost')
    def _compute_totals(self):
        for rec in self:
            rec.total_collected = rec.cash_collected + rec.mobile_money_collected + rec.cheque_collected
            rec.variance_amount = rec.total_collected - rec.expected_amount
            rec.gross_profit = rec.sales_amount - rec.operating_cost

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})


class FMCGStockDamage(models.Model):
    _name = 'fmcg.stock.damage'
    _description = 'VAN / Depot Damaged Stock Capture'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Damaged Stock Report', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    depot_id = fields.Many2one('fmcg.depot')
    van_id = fields.Many2one('fmcg.van.vehicle')
    load_id = fields.Many2one('fmcg.van.stock.load')
    product_id = fields.Many2one('product.product', required=True)
    qty = fields.Float(required=True)
    reason = fields.Selection([('breakage','Breakage'),('expiry','Expiry'),('shortage','Shortage'),('quality','Quality Issue'),('other','Other')], default='breakage')
    responsible_user_id = fields.Many2one('res.users', string='Responsible User')
    state = fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('written_off','Written Off')], default='draft')
    note = fields.Text()

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_write_off(self):
        self.write({'state': 'written_off'})


class FMCGTerritoryScorecard(models.Model):
    _name = 'fmcg.territory.scorecard'
    _description = 'Territory / Route Intelligence Scorecard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Territory Scorecard', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    route_id = fields.Many2one('sales.route', required=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor')
    planned_visits = fields.Integer()
    completed_visits = fields.Integer()
    missed_visits = fields.Integer(compute='_compute_metrics', store=True)
    outlet_count = fields.Integer()
    active_outlets = fields.Integer()
    coverage_rate = fields.Float(compute='_compute_metrics', store=True)
    compliance_rate = fields.Float(string='Geo / Route Compliance %')
    sales_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    productivity_score = fields.Float(compute='_compute_metrics', store=True)
    note = fields.Text()

    @api.depends('planned_visits', 'completed_visits', 'outlet_count', 'active_outlets', 'compliance_rate')
    def _compute_metrics(self):
        for rec in self:
            rec.missed_visits = max(rec.planned_visits - rec.completed_visits, 0)
            rec.coverage_rate = (rec.active_outlets / rec.outlet_count * 100.0) if rec.outlet_count else 0.0
            completion = (rec.completed_visits / rec.planned_visits * 100.0) if rec.planned_visits else 0.0
            rec.productivity_score = (completion * 0.45) + (rec.coverage_rate * 0.35) + (rec.compliance_rate * 0.20)


class FMCGCollectionAllocation(models.Model):
    _name = 'fmcg.collection.allocation'
    _description = 'Collection Invoice Allocation / Reconciliation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Collection Allocation', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    collection_id = fields.Many2one('fmcg.collection.payment', required=True)
    partner_id = fields.Many2one('res.partner', related='collection_id.partner_id', store=True)
    invoice_id = fields.Many2one('account.move', string='Invoice', domain=[('move_type', '=', 'out_invoice')])
    amount_allocated = fields.Monetary(required=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([('draft','Draft'),('allocated','Allocated'),('reconciled','Reconciled'),('cancelled','Cancelled')], default='draft', tracking=True)
    note = fields.Text()

    def action_allocate(self):
        self.write({'state': 'allocated'})

    def action_reconcile(self):
        self.write({'state': 'reconciled'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class FMCGCreditRiskScore(models.Model):
    _name = 'fmcg.credit.risk.score'
    _description = 'Customer Credit Risk Intelligence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Credit Risk Score', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one('res.partner', required=True)
    overdue_amount = fields.Monetary()
    exposure_amount = fields.Monetary()
    credit_limit = fields.Monetary(related='partner_id.credit_limit_amount', readonly=True)
    days_overdue = fields.Integer()
    payment_reliability = fields.Float(string='Payment Reliability %')
    risk_score = fields.Float(compute='_compute_risk', store=True)
    risk_level = fields.Selection([('low','Low'),('medium','Medium'),('high','High'),('critical','Critical')], compute='_compute_risk', store=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    recommendation = fields.Text()

    @api.depends('overdue_amount', 'exposure_amount', 'credit_limit', 'days_overdue', 'payment_reliability')
    def _compute_risk(self):
        for rec in self:
            exposure_ratio = (rec.exposure_amount / rec.credit_limit * 100.0) if rec.credit_limit else 0.0
            rec.risk_score = min((exposure_ratio * 0.35) + (rec.days_overdue * 1.2) + ((100.0 - rec.payment_reliability) * 0.35), 100.0)
            if rec.risk_score >= 80:
                rec.risk_level = 'critical'
            elif rec.risk_score >= 60:
                rec.risk_level = 'high'
            elif rec.risk_score >= 35:
                rec.risk_level = 'medium'
            else:
                rec.risk_level = 'low'


class FMCGPromotionPerformance(models.Model):
    _name = 'fmcg.promotion.performance'
    _description = 'Trade Promotion Performance / ROI'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(default='Promotion Performance', required=True)
    promotion_id = fields.Many2one('fmcg.promotion.scheme', string='Promotion')
    date_from = fields.Date(default=fields.Date.context_today, required=True)
    date_to = fields.Date(default=fields.Date.context_today, required=True)
    route_id = fields.Many2one('sales.route')
    partner_id = fields.Many2one('res.partner', string='Retailer / Outlet')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    promo_cost = fields.Monetary()
    incremental_sales = fields.Monetary()
    gross_margin = fields.Monetary()
    roi_percent = fields.Float(compute='_compute_roi', store=True)
    compliance_rate = fields.Float(string='Retailer Compliance %')
    note = fields.Text()

    @api.depends('promo_cost', 'gross_margin')
    def _compute_roi(self):
        for rec in self:
            rec.roi_percent = ((rec.gross_margin - rec.promo_cost) / rec.promo_cost * 100.0) if rec.promo_cost else 0.0


class FMCGMarketImpactScorecard(models.Model):
    _name = 'fmcg.market.impact.scorecard'
    _description = 'Market Impact / Activation ROI Scorecard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_from desc, id desc'

    name = fields.Char(default='Market Impact Scorecard', required=True)
    campaign_id = fields.Many2one('fmcg.market.impact.campaign', required=True)
    date_from = fields.Date(default=fields.Date.context_today, required=True)
    date_to = fields.Date(default=fields.Date.context_today, required=True)
    route_id = fields.Many2one('sales.route')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    attendance_count = fields.Integer()
    outlets_covered = fields.Integer()
    samples_issued = fields.Integer()
    leads_generated = fields.Integer()
    campaign_cost = fields.Monetary()
    sales_generated = fields.Monetary()
    roi_percent = fields.Float(compute='_compute_roi', store=True)
    media_count = fields.Integer(string='Media Evidence Count')
    score = fields.Float(compute='_compute_roi', store=True)
    note = fields.Text()

    @api.depends('campaign_cost', 'sales_generated', 'outlets_covered', 'leads_generated', 'media_count')
    def _compute_roi(self):
        for rec in self:
            rec.roi_percent = ((rec.sales_generated - rec.campaign_cost) / rec.campaign_cost * 100.0) if rec.campaign_cost else 0.0
            rec.score = min((rec.outlets_covered * 0.4) + (rec.leads_generated * 0.3) + (rec.media_count * 0.3), 100.0)


class FMCGModernTradeAppointment(models.Model):
    _name = 'fmcg.modern.trade.appointment'
    _description = 'Modern Trade Delivery Appointment'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'appointment_date desc, id desc'

    name = fields.Char(default='Delivery Appointment', required=True)
    account_id = fields.Many2one('fmcg.modern.trade.account', required=True)
    store_id = fields.Many2one('res.partner', string='Store / Branch')
    sale_order_id = fields.Many2one('sale.order')
    appointment_date = fields.Datetime(required=True, default=fields.Datetime.now)
    appointment_date_stop = fields.Datetime(string='End Time', default=fields.Datetime.now, required=True)
    delivery_window = fields.Char()
    dock_reference = fields.Char()
    state = fields.Selection([('scheduled','Scheduled'),('confirmed','Confirmed'),('delivered','Delivered'),('missed','Missed'),('cancelled','Cancelled')], default='scheduled', tracking=True)
    note = fields.Text()

    def action_confirm(self):
        self.write({'state': 'confirmed'})

    def action_delivered(self):
        self.write({'state': 'delivered'})

    def action_missed(self):
        self.write({'state': 'missed'})


class FMCGInvoiceDispute(models.Model):
    _name = 'fmcg.invoice.dispute'
    _description = 'Modern Trade Invoice Dispute Tracking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Invoice Dispute', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    account_id = fields.Many2one('fmcg.modern.trade.account')
    partner_id = fields.Many2one('res.partner')
    invoice_id = fields.Many2one('account.move', domain=[('move_type', '=', 'out_invoice')])
    dispute_amount = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    reason = fields.Selection([('pricing','Pricing'),('quantity','Quantity'),('delivery','Delivery'),('return','Return'),('other','Other')], default='other')
    owner_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    state = fields.Selection([('open','Open'),('under_review','Under Review'),('resolved','Resolved'),('rejected','Rejected')], default='open', tracking=True)
    resolution_note = fields.Text()

    def action_review(self):
        self.write({'state': 'under_review'})

    def action_resolve(self):
        self.write({'state': 'resolved'})

    def action_reject(self):
        self.write({'state': 'rejected'})


class FMCGExecutiveDashboardSnapshot(models.Model):
    _name = 'fmcg.executive.dashboard.snapshot'
    _description = 'Executive Intelligence Dashboard Snapshot'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='Executive Dashboard Snapshot', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    dashboard_type = fields.Selection([
        ('ceo','CEO'),('commercial','Commercial Director'),('sales','Sales Director'),('distribution','Distribution Manager'),('regional','Regional Manager')
    ], default='ceo', required=True)
    route_id = fields.Many2one('sales.route')
    user_id = fields.Many2one('res.users', string='Responsible Manager')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    revenue = fields.Monetary()
    gross_profit = fields.Monetary()
    route_compliance = fields.Float(string='Route Compliance %')
    visit_completion = fields.Float(string='Visit Completion %')
    collection_efficiency = fields.Float(string='Collection Efficiency %')
    distributor_score = fields.Float()
    van_profitability = fields.Monetary()
    promotion_roi = fields.Float(string='Promotion ROI %')
    activation_roi = fields.Float(string='Activation ROI %')
    executive_score = fields.Float(compute='_compute_executive_score', store=True)
    note = fields.Text()

    @api.depends('route_compliance', 'visit_completion', 'collection_efficiency', 'distributor_score', 'promotion_roi', 'activation_roi')
    def _compute_executive_score(self):
        for rec in self:
            rec.executive_score = (
                (rec.route_compliance * 0.20) +
                (rec.visit_completion * 0.20) +
                (rec.collection_efficiency * 0.20) +
                (rec.distributor_score * 0.20) +
                (min(max(rec.promotion_roi, 0.0), 100.0) * 0.10) +
                (min(max(rec.activation_roi, 0.0), 100.0) * 0.10)
            )
