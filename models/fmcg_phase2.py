from odoo import api, fields, models, _
from odoo.exceptions import UserError


class FMCGMerchVisit(models.Model):
    _name = 'fmcg.merch.visit'
    _description = 'FMCG Merchandizer Retail Execution Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New Merchandising Visit', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    date_stop = fields.Date(string='End Date', default=fields.Date.context_today, required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Outlet', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Merchandizer', default=lambda self: self.env.user, tracking=True)
    route_id = fields.Many2one('sales.route', string='Market Route', related='partner_id.route_id', store=True, readonly=False)
    trade_channel = fields.Selection(related='partner_id.trade_channel', store=True, readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'), ('in_progress', 'In Progress'), ('submitted', 'Submitted'), ('approved', 'Approved'), ('cancelled', 'Cancelled')
    ], default='draft', tracking=True)
    shelf_score = fields.Float(string='Shelf / Execution Score', compute='_compute_scores', store=True)
    sku_availability_score = fields.Float(string='SKU Availability %', compute='_compute_scores', store=True)
    line_ids = fields.One2many('fmcg.merch.visit.line', 'visit_id', string='SKU Checks')
    photo_ids = fields.One2many('fmcg.execution.photo', 'merch_visit_id', string='Photos / Evidence')
    competitor_note = fields.Text(string='Competitor Intelligence')
    recommendation = fields.Text(string='Recommendation / Action Required')

    @api.depends('line_ids.is_available', 'line_ids.planogram_ok')
    def _compute_scores(self):
        for rec in self:
            lines = rec.line_ids
            total = len(lines)
            if not total:
                rec.sku_availability_score = 0.0
                rec.shelf_score = 0.0
                continue
            available = len(lines.filtered(lambda l: l.is_available))
            compliant = len(lines.filtered(lambda l: l.planogram_ok))
            rec.sku_availability_score = (available / total) * 100.0
            rec.shelf_score = (compliant / total) * 100.0

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class FMCGMerchVisitLine(models.Model):
    _name = 'fmcg.merch.visit.line'
    _description = 'FMCG Merchandising SKU Check'

    visit_id = fields.Many2one('fmcg.merch.visit', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    is_available = fields.Boolean(string='Available')
    shelf_qty = fields.Float(string='Shelf Qty')
    backroom_qty = fields.Float(string='Backroom Qty')
    facing_count = fields.Integer(string='Facings')
    planogram_ok = fields.Boolean(string='Planogram OK')
    price = fields.Float(string='Observed Price')
    competitor_price = fields.Float(string='Competitor Price')
    note = fields.Char()


class FMCGRetailExecutionVisit(models.Model):
    _name = 'fmcg.retail.execution.visit'
    _description = 'FMCG Retail / Supermarket Execution Visit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New Retail Execution Visit', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    date_stop = fields.Date(string='End Date', default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one('res.partner', string='Outlet / Store', required=True)
    user_id = fields.Many2one('res.users', string='Field User', default=lambda self: self.env.user)
    route_id = fields.Many2one('sales.route', string='Market Route', related='partner_id.route_id', store=True, readonly=False)
    visit_type = fields.Selection([
        ('supermarket', 'Supermarket Servicing'), ('hypermarket', 'Hypermarket / Modern Trade'), ('wholesale', 'Wholesale'), ('retail', 'Retail Outlet')
    ], default='retail', required=True)
    order_id = fields.Many2one('sale.order', string='Related Sales Order')
    delivery_required = fields.Boolean()
    payment_collected = fields.Boolean()
    return_required = fields.Boolean()
    compliance_score = fields.Float(string='Compliance Score')
    issue_note = fields.Text(string='Issues / Escalations')
    state = fields.Selection([('draft','Draft'),('done','Done'),('cancelled','Cancelled')], default='draft')

    def action_done(self):
        self.write({'state': 'done'})


class FMCGModernTradeAccount(models.Model):
    _name = 'fmcg.modern.trade.account'
    _description = 'FMCG Hypermarket / Modern Trade Account'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Head Office / Chain', required=True)
    store_ids = fields.Many2many('res.partner', string='Stores / Branches')
    key_account_manager_id = fields.Many2one('res.users', string='Key Account Manager')
    payment_terms_note = fields.Text()
    listing_note = fields.Text(string='Listing / Range Notes')
    promotion_note = fields.Text(string='Promotion Notes')
    state = fields.Selection([('active','Active'),('inactive','Inactive')], default='active')


class FMCGMarketImpactActivity(models.Model):
    _name = 'fmcg.market.impact.activity'
    _description = 'FMCG Market Impact / Activation Activity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(required=True, tracking=True)
    campaign_id = fields.Many2one('fmcg.market.impact.campaign', required=True, ondelete='cascade')
    date = fields.Date(default=fields.Date.context_today, required=True)
    date_stop = fields.Date(string='End Date', default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one('res.partner', string='Outlet / Location')
    route_id = fields.Many2one('sales.route', string='Route')
    user_ids = fields.Many2many('res.users', string='Activation Team')
    footfall = fields.Integer()
    leads_generated = fields.Integer()
    samples_issued = fields.Integer()
    sales_generated = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    media_ids = fields.One2many('fmcg.execution.photo', 'impact_activity_id', string='Media Evidence')
    note = fields.Text()
    state = fields.Selection([('planned','Planned'),('active','Active'),('done','Done'),('cancelled','Cancelled')], default='planned')

    def action_start(self):
        self.write({'state': 'active'})

    def action_done(self):
        self.write({'state': 'done'})


class FMCGExecutionPhoto(models.Model):
    _name = 'fmcg.execution.photo'
    _description = 'FMCG Execution Photo / Evidence'
    _order = 'id desc'

    name = fields.Char(required=True, default='Execution Photo')
    image = fields.Binary(string='Photo / Evidence', attachment=True)
    filename = fields.Char()
    merch_visit_id = fields.Many2one('fmcg.merch.visit', ondelete='cascade')
    impact_activity_id = fields.Many2one('fmcg.market.impact.activity', ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Outlet')
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user)
    date = fields.Datetime(default=fields.Datetime.now)
    latitude = fields.Float(digits=(16, 6))
    longitude = fields.Float(digits=(16, 6))
    note = fields.Char()


class FMCGCollectionPayment(models.Model):
    _name = 'fmcg.collection.payment'
    _description = 'FMCG Field Collection / Payment Capture'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New Collection', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    partner_id = fields.Many2one('res.partner', required=True, string='Customer')
    user_id = fields.Many2one('res.users', string='Collected By', default=lambda self: self.env.user)
    route_id = fields.Many2one('sales.route', related='partner_id.route_id', store=True, readonly=False)
    sale_order_id = fields.Many2one('sale.order', string='Related Sales Order')
    payment_method = fields.Selection([('cash','Cash'),('mobile_money','Mobile Money'),('cheque','Cheque'),('bank','Bank Transfer')], required=True)
    amount = fields.Monetary(required=True)
    reference = fields.Char(string='Receipt / Transaction Reference')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('rejected','Rejected')], default='draft', tracking=True)
    note = fields.Text()

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_reject(self):
        self.write({'state': 'rejected'})


class FMCGCreditApproval(models.Model):
    _name = 'fmcg.credit.approval'
    _description = 'FMCG Credit Hold / Limit Approval'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New Credit Approval', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today)
    partner_id = fields.Many2one('res.partner', required=True)
    requested_limit = fields.Monetary()
    current_limit = fields.Monetary(related='partner_id.credit_limit_amount', readonly=True)
    reason = fields.Text(required=True)
    requested_by = fields.Many2one('res.users', default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([('draft','Draft'),('submitted','Submitted'),('approved','Approved'),('rejected','Rejected')], default='draft', tracking=True)

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        for rec in self:
            rec.partner_id.credit_limit_amount = rec.requested_limit
            rec.approved_by = self.env.user
            rec.state = 'approved'

    def action_reject(self):
        self.write({'state': 'rejected'})


class FMCGMDMDevicePolicy(models.Model):
    _name = 'fmcg.mdm.device.policy'
    _description = 'FMCG Mobile Device Management Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    user_ids = fields.Many2many('res.users', string='Assigned Users')
    kiosk_mode = fields.Boolean(string='Kiosk Mode')
    gps_required = fields.Boolean(string='GPS Required')
    allow_screenshot = fields.Boolean(string='Allow Screenshots', default=True)
    remote_wipe_enabled = fields.Boolean(string='Remote Wipe Enabled')
    allowed_app_list = fields.Text(string='Allowed Apps')
    policy_note = fields.Text()
    state = fields.Selection([('draft','Draft'),('active','Active'),('retired','Retired')], default='draft')

    def action_activate(self):
        self.write({'state': 'active'})

    def action_retire(self):
        self.write({'state': 'retired'})
