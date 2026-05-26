
from datetime import datetime, time

from odoo import api, fields, models, _


class SalesRouteSkuTargetPerformance(models.Model):
    _name = 'sales.route.sku.target.performance'
    _description = 'SKU Target Performance Snapshot'
    _order = 'date_start desc, achievement_percent asc, salesperson_id, product_category_id'
    _rec_name = 'display_name'

    display_name = fields.Char(compute='_compute_display_name', store=True)
    target_id = fields.Many2one('sales.route.target', string='Target', required=True, index=True, ondelete='cascade')
    target_line_id = fields.Many2one('sales.route.target.sku.line', string='Target SKU Line', required=True, index=True, ondelete='cascade')
    salesperson_id = fields.Many2one('res.users', string='Salesperson', index=True)
    route_id = fields.Many2one('sales.route', string='Market Route', index=True)
    product_category_id = fields.Many2one('product.category', string='Product Category', index=True)
    product_id = fields.Many2one('product.product', string='SKU / Product', index=True)
    company_id = fields.Many2one('res.company', string='Company', required=True, index=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', store=True, readonly=True)
    date_start = fields.Date(index=True)
    date_end = fields.Date(index=True)
    target_qty = fields.Float(string='Target Qty')
    target_amount = fields.Monetary(string='Target Amount', currency_field='currency_id')
    sale_order_qty = fields.Float(string='Legacy Sales Order Qty')
    sale_order_amount = fields.Monetary(string='Legacy Sales Order Amount', currency_field='currency_id')
    pos_order_qty = fields.Float(string='POS Qty')
    pos_order_amount = fields.Monetary(string='POS Amount', currency_field='currency_id')
    total_qty = fields.Float(string='POS Sold Qty', compute='_compute_totals', store=True)
    total_amount = fields.Monetary(string='POS Sold Amount', currency_field='currency_id', compute='_compute_totals', store=True)
    gap_qty = fields.Float(string='Qty Gap', compute='_compute_totals', store=True)
    gap_amount = fields.Monetary(string='Amount Gap', currency_field='currency_id', compute='_compute_totals', store=True)
    achievement_percent = fields.Float(string='Achievement %', compute='_compute_totals', store=True)
    compliance_state = fields.Selection([
        ('not_started', 'Not Started'),
        ('critical', 'Critical'),
        ('behind', 'Behind'),
        ('on_track', 'On Track'),
        ('achieved', 'Achieved'),
    ], string='Status', compute='_compute_totals', store=True, index=True)
    last_recomputed = fields.Datetime(string='Last Recomputed', readonly=True)

    _sql_constraints = [
        ('uniq_target_line_snapshot', 'unique(target_line_id)', 'Each target SKU line can have only one performance snapshot.'),
    ]

    @api.depends('target_id.name', 'salesperson_id.name', 'route_id.name', 'product_category_id.name', 'product_id.name')
    def _compute_display_name(self):
        for rec in self:
            item = rec.product_category_id.display_name or _('Product Category')
            owner = rec.salesperson_id.name or rec.route_id.name or _('Group')
            rec.display_name = '%s - %s - %s' % (rec.target_id.name or _('Target'), owner, item)

    @api.depends('sale_order_qty', 'pos_order_qty', 'sale_order_amount', 'pos_order_amount', 'target_qty', 'target_amount')
    def _compute_totals(self):
        for rec in self:
            # SKU achievement is intentionally based on Sales Order lines by product category.
            # POS values are kept for reference only; they are not used for SKU target achievement.
            rec.total_qty = rec.sale_order_qty or 0.0
            rec.total_amount = rec.sale_order_amount or 0.0
            rec.gap_qty = max((rec.target_qty or 0.0) - rec.total_qty, 0.0)
            rec.gap_amount = max((rec.target_amount or 0.0) - rec.total_amount, 0.0)
            denominator = rec.target_qty or 0.0
            if not denominator and rec.target_amount:
                denominator = rec.target_amount
                numerator = rec.total_amount
            else:
                numerator = rec.total_qty
            progress = (numerator / denominator * 100.0) if denominator else 0.0
            rec.achievement_percent = progress
            if progress >= 100:
                rec.compliance_state = 'achieved'
            elif progress >= 80:
                rec.compliance_state = 'on_track'
            elif progress >= 40:
                rec.compliance_state = 'behind'
            elif progress > 0:
                rec.compliance_state = 'critical'
            else:
                rec.compliance_state = 'not_started'

    def action_view_sale_order_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order Lines for %s') % (self.product_category_id.display_name or _('Product Category')),
            'res_model': 'sale.order.line',
            'view_mode': 'tree,form,pivot,graph',
            'domain': self._sale_order_line_domain(),
            'context': {'create': False},
        }

    def _sale_order_line_domain(self):
        self.ensure_one()
        start_dt = datetime.combine(self.date_start, time.min)
        end_dt = datetime.combine(self.date_end, time.max)
        orders = self.target_id._settled_sale_orders_for_sku_achievement() if self.target_id and hasattr(self.target_id, '_settled_sale_orders_for_sku_achievement') else self.env['sale.order']
        domain = [
            ('order_id', 'in', orders.ids),
            ('display_type', '=', False),
        ]
        if self.product_category_id:
            domain.append(('product_id.categ_id', 'child_of', self.product_category_id.id))
        return domain

    @api.model
    def _aggregate_sale_lines(self, target, line):
        """Aggregate SKU achievement from Sales Orders by product category only.

        The business rule is: SKU target tracking on salesperson profiles is category-based,
        not individual-product-based. Existing target lines may still contain a product; in that
        case we use the product's category and aggregate all sale.order.line quantities/amounts
        in that category for the target period/salesperson/route.
        """
        SaleOrder = self.env['sale.order'].sudo()
        SaleLine = self.env['sale.order.line'].sudo()
        category = line.product_category_id or line.product_id.categ_id
        if not category:
            return 0.0, 0.0
        # Count only Sales Orders that appear in the Route Visits list and have
        # POS settlement status = Settled.  SKU achievement remains based on
        # Sales Order lines by product category, but the eligible sales orders
        # are restricted to settled route-visit orders.
        if hasattr(target, '_settled_sale_orders_for_sku_achievement'):
            orders = target._settled_sale_orders_for_sku_achievement()
        else:
            orders = SaleOrder.search(target._sale_order_domain())
        order_ids = orders.ids
        if not order_ids:
            return 0.0, 0.0
        domain = [
            ('order_id', 'in', order_ids),
            ('display_type', '=', False),
            ('product_id.categ_id', 'child_of', category.id),
        ]
        grouped = SaleLine.read_group(domain, ['product_uom_qty:sum', 'price_subtotal:sum'], [])
        totals = grouped[0] if grouped else {}
        return totals.get('product_uom_qty') or 0.0, totals.get('price_subtotal') or 0.0

    @api.model
    def _aggregate_pos_lines(self, target, line):
        if 'pos.order.line' not in self.env.registry:
            return 0.0, 0.0
        PosLine = self.env['pos.order.line'].sudo()
        start_dt = datetime.combine(target.date_start, time.min)
        end_dt = datetime.combine(target.date_end, time.max)
        domain = [
            ('order_id.date_order', '>=', fields.Datetime.to_string(start_dt)),
            ('order_id.date_order', '<=', fields.Datetime.to_string(end_dt)),
            ('order_id.state', 'in', ['paid', 'done', 'invoiced']),
        ]
        if target.company_id:
            domain.append(('order_id.company_id', '=', target.company_id.id))
        if target.user_id and target.target_scope in ('salesperson', 'route_salesperson'):
            domain.append(('order_id.user_id', '=', target.user_id.id))
        # Route is not standard on POS Orders in all databases; filter safely only when present.
        if target.route_id and 'route_id' in self.env['pos.order']._fields:
            domain.append(('order_id.route_id', '=', target.route_id.id))
        if line.product_id:
            domain.append(('product_id', '=', line.product_id.id))
        elif line.product_category_id:
            domain.append(('product_id.categ_id', 'child_of', line.product_category_id.id))
        lines = PosLine.search(domain)
        qty = sum(lines.mapped('qty')) if 'qty' in PosLine._fields else 0.0
        amount = sum(lines.mapped('price_subtotal_incl')) if 'price_subtotal_incl' in PosLine._fields else sum(lines.mapped('price_subtotal'))
        return qty, amount

    @api.model
    def recompute_for_targets(self, targets=None, date_from=None, date_to=None, limit=200):
        Target = self.env['sales.route.target'].sudo()
        if targets is None:
            domain = [('active', '=', True), ('sku_target_line_ids', '!=', False)]
            if date_from:
                domain.append(('date_end', '>=', date_from))
            if date_to:
                domain.append(('date_start', '<=', date_to))
            targets = Target.search(domain, order='date_start desc, id desc', limit=limit)
        now = fields.Datetime.now()
        for target in targets.sudo():
            for line in target.sku_target_line_ids:
                sale_qty, sale_amount = self._aggregate_sale_lines(target, line)
                pos_qty, pos_amount = 0.0, 0.0
                category = line.product_category_id or line.product_id.categ_id
                vals = {
                    'target_id': target.id,
                    'target_line_id': line.id,
                    'salesperson_id': target.user_id.id or False,
                    'route_id': target.route_id.id or False,
                    'product_category_id': category.id if category else False,
                    'product_id': False,
                    'company_id': target.company_id.id or self.env.company.id,
                    'date_start': target.date_start,
                    'date_end': target.date_end,
                    'target_qty': line.target_qty or 0.0,
                    'target_amount': line.target_amount or 0.0,
                    'sale_order_qty': sale_qty,
                    'sale_order_amount': sale_amount,
                    'pos_order_qty': pos_qty,
                    'pos_order_amount': pos_amount,
                    'last_recomputed': now,
                }
                existing = self.sudo().search([('target_line_id', '=', line.id)], limit=1)
                if existing:
                    existing.write(vals)
                else:
                    self.sudo().create(vals)
        return True

    @api.model
    def cron_recompute_active_sku_target_performance(self):
        today = fields.Date.context_today(self)
        self.recompute_for_targets(date_from=today, date_to=today, limit=300)
        return True

    @api.model
    def dashboard_summary(self, user_ids=None, route_ids=None, date_from=None, date_to=None, limit=12):
        domain = []
        if user_ids:
            domain.append(('salesperson_id', 'in', user_ids))
        if route_ids:
            domain.append(('route_id', 'in', route_ids))
        if date_from:
            domain.append(('date_end', '>=', date_from))
        if date_to:
            domain.append(('date_start', '<=', date_to))
        rows = self.sudo().search(domain, order='achievement_percent asc, gap_qty desc', limit=limit)
        overall = self.sudo().read_group(domain, ['target_qty:sum', 'total_qty:sum', 'target_amount:sum', 'total_amount:sum'], []) if domain or True else []
        totals = overall[0] if overall else {}
        target_qty = totals.get('target_qty') or 0.0
        total_qty = totals.get('total_qty') or 0.0
        target_amount = totals.get('target_amount') or 0.0
        total_amount = totals.get('total_amount') or 0.0
        return {
            'target_qty': round(target_qty, 2),
            'sold_qty': round(total_qty, 2),
            'qty_progress': round((total_qty / target_qty * 100.0) if target_qty else 0.0, 1),
            'target_amount': round(target_amount, 2),
            'sold_amount': round(total_amount, 2),
            'amount_progress': round((total_amount / target_amount * 100.0) if target_amount else 0.0, 1),
            'worst_skus': [{
                'id': r.id,
                'sku': r.product_category_id.display_name or '',
                'salesperson': r.salesperson_id.name or '',
                'route': r.route_id.name or '',
                'target_qty': round(r.target_qty, 2),
                'sold_qty': round(r.total_qty, 2),
                'gap_qty': round(r.gap_qty, 2),
                'progress': round(r.achievement_percent, 1),
                'state': r.compliance_state,
            } for r in rows],
        }
