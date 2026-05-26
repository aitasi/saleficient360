from odoo import api, fields, models, _
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _auto_init(self):
        """Create FMCG partner columns before ORM/related-field reads.

        Some existing databases can crash during login/registry loading before a
        normal module upgrade has completed because res.partner is read with
        these fields in the SELECT list while the SQL columns are still absent.
        This defensive initializer keeps upgrades from older/partial builds safe.
        """
        cr = self.env.cr
        cr.execute("""
            ALTER TABLE res_partner
                ADD COLUMN IF NOT EXISTS fmcg_partner_type varchar,
                ADD COLUMN IF NOT EXISTS trade_channel varchar,
                ADD COLUMN IF NOT EXISTS distributor_id integer,
                ADD COLUMN IF NOT EXISTS depot_id integer,
                ADD COLUMN IF NOT EXISTS credit_limit_amount numeric,
                ADD COLUMN IF NOT EXISTS credit_hold boolean;
        """)
        cr.execute("CREATE INDEX IF NOT EXISTS res_partner_fmcg_partner_type_idx ON res_partner(fmcg_partner_type)")
        cr.execute("CREATE INDEX IF NOT EXISTS res_partner_trade_channel_idx ON res_partner(trade_channel)")
        cr.execute("CREATE INDEX IF NOT EXISTS res_partner_distributor_id_idx ON res_partner(distributor_id)")
        cr.execute("CREATE INDEX IF NOT EXISTS res_partner_depot_id_idx ON res_partner(depot_id)")
        return super()._auto_init()

    fmcg_partner_type = fields.Selection([
        ('manufacturer', 'Manufacturer'),
        ('distributor', 'Depot Distributor'),
        ('depot', 'Depot'),
        ('hypermarket', 'Hypermarket'),
        ('supermarket', 'Supermarket'),
        ('wholesale', 'Wholesale'),
        ('retail_outlet', 'Retail Outlet'),
        ('pharmacy', 'Pharmacy'),
        ('horeca', 'HoReCa'),
        ('institution', 'Institution'),
    ], string='FMCG Partner Type', tracking=True)
    trade_channel = fields.Selection([
        ('modern_trade', 'Modern Trade'),
        ('general_trade', 'General Trade'),
        ('traditional_trade', 'Traditional Trade'),
        ('institutional', 'Institutional'),
        ('distributor', 'Distributor'),
    ], string='Trade Channel', tracking=True)
    distributor_id = fields.Many2one('res.partner', string='Depot Distributor', domain=[('fmcg_partner_type', '=', 'distributor')])
    depot_id = fields.Many2one('fmcg.depot', string='Servicing Depot')
    credit_limit_amount = fields.Monetary(string='Credit Limit')
    credit_hold = fields.Boolean(string='Credit Hold')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)


class FMCGDepot(models.Model):
    _name = 'fmcg.depot'
    _description = 'FMCG Depot'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(tracking=True)
    active = fields.Boolean(default=True)
    partner_id = fields.Many2one('res.partner', string='Depot Contact')
    distributor_id = fields.Many2one('res.partner', string='Depot Distributor', domain=[('fmcg_partner_type', '=', 'distributor')])
    route_ids = fields.Many2many('sales.route', string='Served Market Routes')
    user_id = fields.Many2one('res.users', string='Depot Manager')
    location_note = fields.Text(string='Location / Operating Notes')


class FMCGVanVehicle(models.Model):
    _name = 'fmcg.van.vehicle'
    _description = 'FMCG VAN / Field Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    plate_number = fields.Char(string='Plate Number', tracking=True)
    depot_id = fields.Many2one('fmcg.depot', string='Home Depot')
    user_id = fields.Many2one('res.users', string='Assigned Salesperson')
    route_id = fields.Many2one('sales.route', string='Default Market Route')
    active = fields.Boolean(default=True)
    capacity_note = fields.Text(string='Capacity / Vehicle Notes')


class FMCGVanStockLoad(models.Model):
    _name = 'fmcg.van.stock.load'
    _description = 'VAN Stock Load / Dispatch Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New VAN Load', required=True, tracking=True)
    date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    depot_id = fields.Many2one('fmcg.depot', required=True, tracking=True)
    van_id = fields.Many2one('fmcg.van.vehicle', required=True, tracking=True)
    user_id = fields.Many2one('res.users', string='Salesperson', related='van_id.user_id', store=True, readonly=False)
    route_id = fields.Many2one('sales.route', string='Route', related='van_id.route_id', store=True, readonly=False)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('loaded', 'Loaded'),
        ('dispatched', 'Dispatched'),
        ('reconciled', 'Reconciled'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    line_ids = fields.One2many('fmcg.van.stock.load.line', 'load_id', string='Loaded Products')
    note = fields.Text()

    def action_loaded(self):
        self.write({'state': 'loaded'})

    def action_dispatch(self):
        self.write({'state': 'dispatched'})

    def action_reconcile(self):
        self.write({'state': 'reconciled'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})


class FMCGVanStockLoadLine(models.Model):
    _name = 'fmcg.van.stock.load.line'
    _description = 'VAN Stock Load Line'

    load_id = fields.Many2one('fmcg.van.stock.load', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', required=True)
    qty_loaded = fields.Float(string='Qty Loaded', default=0.0)
    qty_sold = fields.Float(string='Qty Sold', default=0.0)
    qty_returned = fields.Float(string='Qty Returned', default=0.0)
    qty_damaged = fields.Float(string='Qty Damaged', default=0.0)
    qty_variance = fields.Float(string='YTD Sales', compute='_compute_variance', store=True)

    @api.depends('qty_loaded', 'qty_sold', 'qty_returned', 'qty_damaged')
    def _compute_variance(self):
        for line in self:
            line.qty_variance = line.qty_loaded - line.qty_sold - line.qty_returned - line.qty_damaged


class FMCGVanReconciliation(models.Model):
    _name = 'fmcg.van.reconciliation'
    _description = 'VAN Reconciliation / Cash Settlement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(default='New VAN Reconciliation', required=True)
    date = fields.Date(default=fields.Date.context_today, required=True)
    load_id = fields.Many2one('fmcg.van.stock.load', required=True)
    van_id = fields.Many2one('fmcg.van.vehicle', related='load_id.van_id', store=True)
    user_id = fields.Many2one('res.users', related='load_id.user_id', store=True, string='Salesperson')
    total_cash = fields.Monetary(string='Cash Collected')
    total_mobile_money = fields.Monetary(string='Mobile Money Collected')
    total_cheque = fields.Monetary(string='Cheque Collected')
    variance_amount = fields.Monetary(string='Settlement Variance')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved')], default='draft', tracking=True)
    note = fields.Text()

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({'state': 'approved'})


class FMCGMarketImpactCampaign(models.Model):
    _name = 'fmcg.market.impact.campaign'
    _description = 'Market Impact / Trade Activation Campaign'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True, tracking=True)
    date_start = fields.Date()
    date_end = fields.Date()
    route_ids = fields.Many2many('sales.route', string='Target Routes')
    user_ids = fields.Many2many('res.users', string='Market Impact Team')
    objective = fields.Text()
    budget = fields.Monetary()
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    state = fields.Selection([('draft', 'Draft'), ('active', 'Active'), ('done', 'Done'), ('cancelled', 'Cancelled')], default='draft')

    def action_activate(self):
        self.write({'state': 'active'})

    def action_done(self):
        self.write({'state': 'done'})


class FMCGPromotionScheme(models.Model):
    _name = 'fmcg.promotion.scheme'
    _description = 'FMCG Trade Promotion Scheme'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(required=True)
    date_start = fields.Date()
    date_end = fields.Date()
    channel = fields.Selection([
        ('modern_trade', 'Modern Trade'),
        ('general_trade', 'General Trade'),
        ('distributor', 'Distributor'),
        ('all', 'All Channels'),
    ], default='all')
    route_ids = fields.Many2many('sales.route', string='Applicable Routes')
    product_ids = fields.Many2many('product.product', string='Products')
    mechanic = fields.Text(string='Promotion Mechanic')
    state = fields.Selection([('draft', 'Draft'), ('approved', 'Approved'), ('active', 'Active'), ('closed', 'Closed')], default='draft')

    def action_approve(self):
        self.write({'state': 'approved'})

    def action_activate(self):
        self.write({'state': 'active'})

    def action_close(self):
        self.write({'state': 'closed'})
