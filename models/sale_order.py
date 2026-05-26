import ast

from odoo import _, api, fields, models
from odoo.osv import expression


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    route_id = fields.Many2one('sales.route', string='Market Route')
    route_plan_id = fields.Many2one('sales.route.plan', string='Daily Route Plan')
    route_plan_line_id = fields.Many2one('sales.route.plan.line', string='Route Plan Client')

    fsrp_transfer_to_pos_available = fields.Boolean(
        string='Transfer to POS Available',
        compute='_compute_fsrp_pos_settlement',
        help='Technical indicator used by Field Sales Route Plan. It is true when this Sales Order can be transferred/settled through POS in this database.'
    )
    fsrp_pos_order_ids = fields.Many2many(
        'pos.order',
        compute='_compute_fsrp_pos_settlement',
        string='POS Orders from this Sales Order',
    )
    fsrp_pos_receipt_numbers = fields.Char(
        compute='_compute_fsrp_pos_settlement',
        string='POS Receipt Number',
    )
    fsrp_pos_order_amount = fields.Monetary(
        compute='_compute_fsrp_pos_settlement',
        string='POS Order Amount',
        currency_field='currency_id',
    )
    fsrp_pos_paid_amount = fields.Monetary(
        compute='_compute_fsrp_pos_settlement',
        string='POS Paid Amount',
        currency_field='currency_id',
    )
    fsrp_pos_due_amount = fields.Monetary(
        compute='_compute_fsrp_pos_settlement',
        string='POS Amount Due',
        currency_field='currency_id',
    )
    fsrp_pos_fully_processed = fields.Boolean(
        compute='_compute_fsrp_pos_settlement',
        string='Fully Processed in POS',
    )

    fsrp_delivery_visit_ids = fields.Many2many(
        'sales.route.visit',
        compute='_compute_fsrp_delivery_summary',
        string='Delivery Visits',
    )
    fsrp_delivery_count = fields.Integer(
        compute='_compute_fsrp_delivery_summary',
        string='Delivery Count',
    )
    fsrp_ordered_qty = fields.Float(
        compute='_compute_fsrp_delivery_summary',
        string='Ordered Qty',
    )
    fsrp_delivered_qty = fields.Float(
        compute='_compute_fsrp_delivery_summary',
        string='Delivered Qty',
    )
    fsrp_pending_delivery_qty = fields.Float(
        compute='_compute_fsrp_delivery_summary',
        string='Pending Delivery Qty',
    )
    fsrp_delivery_state = fields.Selection([
        ('not_started', 'Not Started'),
        ('partial', 'Partially Delivered'),
        ('delivered', 'Delivered'),
    ], compute='_compute_fsrp_delivery_summary', string='Delivery State')

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._refresh_route_visit_order_summary_cache()
        return orders

    def write(self, vals):
        before_visits = self._linked_route_visits()
        res = super().write(vals)
        if any(key in vals for key in ['route_plan_line_id', 'route_plan_id', 'route_id', 'name', 'amount_total', 'order_line', 'state']):
            (before_visits | self._linked_route_visits())._compute_visit_orders()
        return res

    def _linked_route_visits(self):
        Visit = self.env['sales.route.visit'].sudo()
        visits = Visit.browse()
        for order in self.sudo():
            if order.route_plan_line_id:
                visits |= Visit.search([('plan_line_id', '=', order.route_plan_line_id.id)])
        return visits

    def _refresh_route_visit_order_summary_cache(self):
        visits = self._linked_route_visits()
        if visits:
            visits._compute_visit_orders()
        return True

    def action_confirm(self):
        res = super().action_confirm()
        for order in self:
            if order.route_plan_line_id:
                order.route_plan_line_id.write({
                    'sale_order_id': order.id,
                    'status': 'productive',
                })
        self._refresh_route_visit_order_summary_cache()
        return res

    def _fsrp_has_transfer_to_pos_button(self):
        """Return True when this sales order is in a database that supports the
        POS quotation/order transfer flow.

        Odoo exposes the label "Transfer to POS" through POS/Sale views. The
        exact Python action name may differ by minor version or customization,
        so this helper checks for the common server methods/fields and the
        installed pos_sale/point_of_sale stack instead of hard-coding one view
        label. It is intentionally permissive because the actual settlement is
        still verified by finding a real pos.order linked back to the sale order.
        """
        self.ensure_one()
        module_names = ['pos_sale', 'point_of_sale']
        installed = self.env['ir.module.module'].sudo().search_count([
            ('name', 'in', module_names),
            ('state', '=', 'installed'),
        ])
        if installed:
            return True
        common_action_names = [
            'action_transfer_to_pos',
            'action_open_pos',
            'action_view_pos_order',
            'action_pos_order',
            'action_open_pos_order',
        ]
        return any(hasattr(type(self), name) or hasattr(self, name) for name in common_action_names)

    @api.depends('name', 'route_plan_line_id')
    def _compute_fsrp_pos_settlement(self):
        for order in self:
            pos_orders = order._fsrp_find_pos_orders_from_sale_order()
            order.fsrp_transfer_to_pos_available = order._fsrp_has_transfer_to_pos_button()
            order.fsrp_pos_order_ids = pos_orders
            order.fsrp_pos_receipt_numbers = ', '.join([
                po.pos_reference or po.name or '' for po in pos_orders if po.pos_reference or po.name
            ])
            order.fsrp_pos_order_amount = sum(pos_orders.mapped('amount_total'))
            order.fsrp_pos_paid_amount = order._fsrp_sum_pos_paid_amount(pos_orders)
            order.fsrp_pos_due_amount = max((order.fsrp_pos_order_amount or 0.0) - (order.fsrp_pos_paid_amount or 0.0), 0.0)
            order.fsrp_pos_fully_processed = bool(order.fsrp_transfer_to_pos_available and pos_orders)



    @api.depends('order_line.product_uom_qty', 'route_plan_line_id')
    def _compute_fsrp_delivery_summary(self):
        """Compute delivery progress for a Sales Order safely.

        This method must exist because the fields above reference it. It is
        intentionally defensive so Sales Order reads do not crash when delivery
        models/columns are being upgraded or when a database has older records.
        """
        Visit = self.env['sales.route.visit'].sudo() if 'sales.route.visit' in self.env.registry else False
        for order in self:
            visits = Visit.browse() if Visit else False
            if Visit and 'delivery_source_sale_order_id' in Visit._fields:
                try:
                    visits = Visit.search([('delivery_source_sale_order_id', '=', order.id)])
                except Exception:
                    visits = Visit.browse()

            ordered_qty = 0.0
            try:
                ordered_qty = sum(order.order_line.filtered(lambda l: not l.display_type).mapped('product_uom_qty'))
            except Exception:
                ordered_qty = 0.0

            delivered_qty = 0.0
            try:
                if visits:
                    if 'delivery_line_ids' in Visit._fields:
                        delivered_qty = sum(visits.mapped('delivery_line_ids.delivered_qty'))
                    elif 'delivery_total_delivered_qty' in Visit._fields:
                        delivered_qty = sum(visits.mapped('delivery_total_delivered_qty'))
            except Exception:
                delivered_qty = 0.0

            pending_qty = max((ordered_qty or 0.0) - (delivered_qty or 0.0), 0.0)
            order.fsrp_delivery_visit_ids = [(6, 0, visits.ids)] if visits else [(5, 0, 0)]
            order.fsrp_delivery_count = len(visits) if visits else 0
            order.fsrp_ordered_qty = ordered_qty
            order.fsrp_delivered_qty = delivered_qty
            order.fsrp_pending_delivery_qty = pending_qty
            if ordered_qty and delivered_qty >= ordered_qty:
                order.fsrp_delivery_state = 'delivered'
            elif delivered_qty > 0:
                order.fsrp_delivery_state = 'partial'
            else:
                order.fsrp_delivery_state = 'not_started'



    def _fsrp_sum_pos_paid_amount(self, pos_orders):
        total = 0.0
        for po in pos_orders:
            if 'amount_paid' in po._fields:
                paid = po.amount_paid or 0.0
                if 'amount_return' in po._fields:
                    paid -= po.amount_return or 0.0
                if 'amount_total' in po._fields and po.amount_total:
                    paid = min(paid, po.amount_total)
                total += max(paid, 0.0)
            elif 'payment_ids' in po._fields:
                total += sum(po.payment_ids.mapped('amount'))
            else:
                total += po.amount_total or 0.0
        return total

    def _fsrp_find_pos_orders_from_sale_order(self):
        """Find real POS receipts created from this Sales Order.

        This production-safe lookup starts from the Sales Order, just like the
        cashier flow: Sales Order > Transfer to POS / POS Quotations & Orders >
        settle. Different Odoo 16 POS/Sale installations store the relationship
        differently, so this method checks every reliable source in order:

        1. The Sales Order smart-button action for POS Orders, where available.
        2. Any direct POS fields exposed on sale.order.
        3. Any sale.order link fields exposed on pos.order.
        4. POS order line links to sale.order or sale.order.line.
        5. Controlled fallback using origin/note/reference text.

        Paid/done/invoiced POS orders and open draft/new POS orders are returned.
        Draft/new orders do not mark the route visit as settled, but their receipt
        reference, total, paid and due amounts are still shown for tracking.
        """
        self.ensure_one()
        if 'pos.order' not in self.env.registry:
            return self.env['pos.order'].browse()

        PosOrder = self.env['pos.order'].sudo()
        pos_orders = PosOrder.browse()

        def add_orders(records):
            nonlocal pos_orders
            if records:
                pos_orders |= records.exists().sudo()

        # 1) Prefer the Sales Order smart-button/action domain because this is
        # the same relation Odoo uses to display POS receipts on the SO form.
        for method_name in [
            'action_view_pos_order',
            'action_view_pos_orders',
            'action_pos_order',
            'action_open_pos_order',
            'action_view_pos_orders_from_sale',
        ]:
            method = getattr(self, method_name, None)
            if not method:
                continue
            try:
                action = method()
            except Exception:
                continue
            if not isinstance(action, dict):
                continue
            res_model = action.get('res_model') or 'pos.order'
            if res_model != 'pos.order':
                continue
            if action.get('res_id'):
                add_orders(PosOrder.browse(action['res_id']))
            domain = action.get('domain') or []
            if isinstance(domain, str):
                try:
                    domain = ast.literal_eval(domain)
                except Exception:
                    domain = []
            if domain:
                try:
                    add_orders(PosOrder.search(domain))
                except Exception:
                    pass

        # 2) Direct/computed POS order relations on sale.order, if installed.
        for field_name, field in self._fields.items():
            if getattr(field, 'comodel_name', False) == 'pos.order':
                try:
                    add_orders(self[field_name])
                except Exception:
                    pass

        # 3) POS order fields linking back to sale.order.
        for field_name, field in PosOrder._fields.items():
            try:
                if getattr(field, 'comodel_name', False) != 'sale.order':
                    continue
                operator = 'in' if field.type in ('many2many', 'one2many') else '='
                value = [self.id] if operator == 'in' else self.id
                add_orders(PosOrder.search([(field_name, operator, value)]))
            except Exception:
                pass

        # 4) Route context added by this module, if already synced.
        if self.route_plan_line_id and 'route_plan_line_id' in PosOrder._fields:
            add_orders(PosOrder.search([('route_plan_line_id', '=', self.route_plan_line_id.id)]))

        # 5) POS order line links. Odoo pos_sale commonly links POS lines to the
        # source sale order/order line rather than storing a simple POS header FK.
        if 'pos.order.line' in self.env.registry:
            PosLine = self.env['pos.order.line'].sudo()
            for field_name, field in PosLine._fields.items():
                try:
                    if getattr(field, 'comodel_name', False) == 'sale.order.line' and self.order_line:
                        operator = 'in' if field.type in ('many2many', 'one2many') else 'in'
                        value = self.order_line.ids
                        lines = PosLine.search([(field_name, operator, value)])
                        if 'order_id' in PosLine._fields:
                            add_orders(lines.mapped('order_id'))
                    elif getattr(field, 'comodel_name', False) == 'sale.order':
                        operator = 'in' if field.type in ('many2many', 'one2many') else '='
                        value = [self.id] if operator == 'in' else self.id
                        lines = PosLine.search([(field_name, operator, value)])
                        if 'order_id' in PosLine._fields:
                            add_orders(lines.mapped('order_id'))
                except Exception:
                    pass

        # 6) Controlled text fallbacks. These are useful for customized POS
        # connectors that store the SO number only as origin/note/reference.
        if self.name:
            for field_name in ['origin', 'note', 'pos_reference', 'name', 'session_move_id']:
                if field_name not in PosOrder._fields:
                    continue
                try:
                    field = PosOrder._fields[field_name]
                    if field.type in ('char', 'text'):
                        add_orders(PosOrder.search([(field_name, 'ilike', self.name)]))
                except Exception:
                    pass

        # Keep POS receipts/quotations that belong to this Sales Order. We include
        # draft/new/open states so field teams can track Sales Orders already moved
        # into POS but not yet paid. Cancelled orders are excluded.
        if 'state' in PosOrder._fields:
            visible_states = ['draft', 'new', 'quotation', 'open', 'partial', 'paid', 'done', 'invoiced']
            pos_orders = pos_orders.filtered(lambda po: not po.state or po.state in visible_states)

        return pos_orders.sorted('id')

# v10.6 digital order signature extension
class SaleOrderDigitalSignature(models.Model):
    _inherit = 'sale.order'

    fsrp_customer_signature = fields.Binary(string='Customer Digital Signature')
    fsrp_customer_signature_filename = fields.Char(string='Signature Filename')
    fsrp_signature_name = fields.Char(string='Signed By')
    fsrp_signature_date = fields.Datetime(string='Signature Date')
    fsrp_signature_note = fields.Text(string='Signature Note')

    def action_fsrp_stamp_signature_date(self):
        for order in self:
            if order.fsrp_customer_signature and not order.fsrp_signature_date:
                order.fsrp_signature_date = fields.Datetime.now()
        return True

# v16 SKU target prefill extension
class SaleOrderSkuTargetPrefill(models.Model):
    _inherit = 'sale.order'

    fsrp_target_id = fields.Many2one('sales.route.target', string='Applied Sales/SKU Target', copy=False)
    fsrp_target_sku_line_ids = fields.One2many('sale.order.target.sku.line', 'order_id', string='Target SKUs', copy=False)

    def _fsrp_applicable_target_domain(self):
        self.ensure_one()
        order_date = fields.Date.to_date(self.date_order) if self.date_order else fields.Date.context_today(self)
        domain = [
            ('active', '=', True),
            ('date_start', '<=', order_date),
            ('date_end', '>=', order_date),
            ('company_id', '=', self.company_id.id),
            ('sku_target_line_ids', '!=', False),
        ]
        scope_domains = []
        if self.user_id:
            scope_domains.append([('target_scope', '=', 'salesperson'), ('user_id', '=', self.user_id.id)])
        if self.route_id:
            scope_domains.append([('target_scope', '=', 'route'), ('route_id', '=', self.route_id.id)])
        if self.user_id and self.route_id:
            scope_domains.append([('target_scope', '=', 'route_salesperson'), ('user_id', '=', self.user_id.id), ('route_id', '=', self.route_id.id)])
        scope_domains.append([('target_scope', '=', 'all_routes')])
        if scope_domains:
            domain = expression.AND([domain, expression.OR(scope_domains)])
        return domain

    def _fsrp_find_applicable_sku_target(self):
        self.ensure_one()
        if 'sales.route.target' not in self.env.registry:
            return self.env['sales.route.target'].browse()
        try:
            return self.env['sales.route.target'].sudo().search(self._fsrp_applicable_target_domain(), order='target_scope desc, date_end asc, id desc', limit=1)
        except Exception:
            return self.env['sales.route.target'].browse()

    def _fsrp_prefill_target_skus(self):
        TargetLine = self.env['sale.order.target.sku.line'].sudo()
        for order in self:
            if order.fsrp_target_sku_line_ids:
                continue
            target = order._fsrp_find_applicable_sku_target()
            if not target:
                continue
            order.fsrp_target_id = target.id
            vals_list = []
            for line in target.sku_target_line_ids:
                vals_list.append({
                    'order_id': order.id,
                    'target_id': target.id,
                    'target_line_id': line.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id if line.product_id else False,
                    'target_qty': line.target_qty,
                    'target_amount': line.target_amount,
                })
            if vals_list:
                TargetLine.create(vals_list)
        return True

    @api.onchange('partner_id', 'user_id', 'route_id', 'date_order', 'company_id')
    def _onchange_fsrp_prefill_target_skus(self):
        for order in self:
            target = order._fsrp_find_applicable_sku_target() if order.user_id or order.route_id else False
            if target and not order.fsrp_target_id:
                order.fsrp_target_id = target
                order.fsrp_target_sku_line_ids = [(5, 0, 0)] + [(0, 0, {
                    'target_id': target.id,
                    'target_line_id': line.id,
                    'product_category_id': line.product_category_id.id,
                    'product_id': line.product_id.id if line.product_id else False,
                    'target_qty': line.target_qty,
                    'target_amount': line.target_amount,
                }) for line in target.sku_target_line_ids]

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._fsrp_prefill_target_skus()
        return orders

    def action_fsrp_refresh_target_skus(self):
        for order in self:
            order.fsrp_target_sku_line_ids.unlink()
            order.fsrp_target_id = False
        self._fsrp_prefill_target_skus()
        return True

    def action_fsrp_add_target_skus_to_order_lines(self):
        for order in self:
            if not order.fsrp_target_sku_line_ids:
                order._fsrp_prefill_target_skus()
            for target_line in order.fsrp_target_sku_line_ids.filtered(lambda l: l.product_id):
                already = order.order_line.filtered(lambda l: not l.display_type and l.product_id == target_line.product_id)
                if already:
                    continue
                order.order_line = [(0, 0, {
                    'product_id': target_line.product_id.id,
                    'product_uom_qty': target_line.target_qty or 1.0,
                })]
        return True


class SaleOrderTargetSkuLine(models.Model):
    _name = 'sale.order.target.sku.line'
    _description = 'Sales Order Prefilled Target SKU'
    _order = 'sequence, product_category_id, product_id, id'

    sequence = fields.Integer(default=10)
    order_id = fields.Many2one('sale.order', required=True, ondelete='cascade', index=True)
    target_id = fields.Many2one('sales.route.target', string='Target', readonly=True)
    target_line_id = fields.Many2one('sales.route.target.sku.line', string='Target SKU Line', readonly=True)
    product_category_id = fields.Many2one('product.category', string='Product Category', readonly=True)
    product_id = fields.Many2one('product.product', string='SKU / Product', readonly=True)
    target_qty = fields.Float(string='Target Qty', readonly=True)
    target_amount = fields.Monetary(string='Target Amount', currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id', readonly=True)
    ordered_qty = fields.Float(string='Ordered Qty', compute='_compute_ordered')
    ordered_amount = fields.Monetary(string='Ordered Amount', currency_field='currency_id', compute='_compute_ordered')
    achievement = fields.Float(string='Achievement %', compute='_compute_ordered')

    @api.depends('order_id.order_line.product_id', 'order_id.order_line.product_uom_qty', 'order_id.order_line.price_subtotal', 'product_id', 'product_category_id', 'target_qty')
    def _compute_ordered(self):
        for rec in self:
            lines = rec.order_id.order_line.filtered(lambda l: not l.display_type)
            if rec.product_id:
                lines = lines.filtered(lambda l: l.product_id == rec.product_id)
            elif rec.product_category_id:
                allowed = self.env['product.category'].search([('id', 'child_of', rec.product_category_id.id)]).ids
                lines = lines.filtered(lambda l: l.product_id.categ_id.id in allowed)
            qty = sum(lines.mapped('product_uom_qty'))
            amount = sum(lines.mapped('price_subtotal'))
            rec.ordered_qty = qty
            rec.ordered_amount = amount
            rec.achievement = (qty / rec.target_qty * 100.0) if rec.target_qty else 0.0
