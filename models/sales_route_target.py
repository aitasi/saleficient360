
from datetime import datetime, time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.osv import expression


class SalesRouteTarget(models.Model):
    _name = 'sales.route.target'
    _description = 'Field Invoice / POS Order Target'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start desc, id desc'

    name = fields.Char(required=True, tracking=True)
    active = fields.Boolean(default=True)
    target_scope = fields.Selection([
        ('salesperson', 'Salesperson'),
        ('route', 'Route'),
        ('route_salesperson', 'Route + Salesperson'),
        ('all_routes', 'All Routes / Group'),
    ], string='Target For', default='salesperson', required=True, tracking=True, index=True)
    user_id = fields.Many2one('res.users', string='Salesperson', tracking=True, index=True)
    route_id = fields.Many2one('sales.route', string='Market Route', tracking=True, index=True)
    date_start = fields.Date(required=True, default=fields.Date.context_today, tracking=True, index=True)
    date_end = fields.Date(required=True, default=fields.Date.context_today, tracking=True, index=True)
    sales_order_target_amount = fields.Monetary(
        string='Invoice / POS Target Amount',
        currency_field='currency_id',
        tracking=True,
        help='Target amount set by supervisor/manager. Existing saved values are preserved. Achievement is measured only against settled Route Visit POS Order Amount, not sale.order.amount_total.'
    )
    sales_order_target_count = fields.Integer(string='Productive POS Order Target', tracking=True)
    sku_target_line_ids = fields.One2many('sales.route.target.sku.line', 'target_id', string='SKU Targets', copy=True)
    sku_target_count = fields.Integer(string='SKU Target Lines', compute='_compute_sku_target_summary')
    achieved_sku_qty = fields.Float(string='Achieved SKU Qty', compute='_compute_achievement')
    sku_target_qty_total = fields.Float(string='Target SKU Qty', compute='_compute_sku_target_summary')
    sku_progress = fields.Float(string='SKU Progress %', compute='_compute_achievement')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id, required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True, index=True)
    achieved_sales_amount = fields.Monetary(string='Achieved Settled POS Order Amount', currency_field='currency_id', compute='_compute_achievement', help='Actual amount from settled Route Visits: sum of sales.route.visit.pos_order_total_amount where POS settlement status is Settled.')
    achieved_collection_amount = fields.Monetary(string='Collections', currency_field='currency_id', compute='_compute_achievement')
    achieved_variance_amount = fields.Monetary(string='Amount Due', currency_field='currency_id', compute='_compute_achievement')
    achieved_sales_count = fields.Integer(string='Productive POS Orders', compute='_compute_achievement')
    amount_progress = fields.Float(string='Amount Progress %', compute='_compute_achievement')
    count_progress = fields.Float(string='Count Progress %', compute='_compute_achievement')
    remaining_amount = fields.Monetary(string='Remaining Invoice / POS Target', currency_field='currency_id', compute='_compute_achievement')
    remaining_count = fields.Integer(string='Remaining POS Orders', compute='_compute_achievement')
    state = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('achieved', 'Achieved'),
        ('expired', 'Expired'),
    ], compute='_compute_achievement', string='Status')
    note = fields.Text()

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rec in self:
            if rec.date_start and rec.date_end and rec.date_end < rec.date_start:
                raise ValidationError(_('End Date cannot be before Start Date.'))

    @api.constrains('target_scope', 'user_id', 'route_id')
    def _check_scope(self):
        for rec in self:
            if rec.target_scope == 'salesperson' and not rec.user_id:
                raise ValidationError(_('Please select a salesperson for a Salesperson target.'))
            if rec.target_scope == 'route' and not rec.route_id:
                raise ValidationError(_('Please select a market route for a Route target.'))
            if rec.target_scope == 'route_salesperson' and (not rec.route_id or not rec.user_id):
                raise ValidationError(_('Please select both route and salesperson for a Route + Salesperson target.'))

    @api.depends('sku_target_line_ids.target_qty')
    def _compute_sku_target_summary(self):
        for rec in self:
            rec.sku_target_count = len(rec.sku_target_line_ids)
            rec.sku_target_qty_total = sum(rec.sku_target_line_ids.mapped('target_qty'))

    def _get_sku_target_order_lines_domain(self):
        self.ensure_one()
        orders = self._settled_sale_orders_for_sku_achievement()
        if not orders:
            return [('id', '=', 0)]
        product_ids = self.sku_target_line_ids.mapped('product_id').ids
        category_ids = self.sku_target_line_ids.mapped('product_category_id').ids
        domain = [('order_id', 'in', orders.ids), ('display_type', '=', False)]
        sku_domain = []
        if product_ids:
            sku_domain = expression.OR([sku_domain, [('product_id', 'in', product_ids)]]) if sku_domain else [('product_id', 'in', product_ids)]
        if category_ids:
            sku_domain = expression.OR([sku_domain, [('product_id.categ_id', 'child_of', category_ids)]]) if sku_domain else [('product_id.categ_id', 'child_of', category_ids)]
        if sku_domain:
            domain = expression.AND([domain, sku_domain])
        return domain

    def _sale_order_domain(self):
        self.ensure_one()
        start_dt = datetime.combine(self.date_start, time.min)
        end_dt = datetime.combine(self.date_end, time.max)
        domain = [
            ('company_id', '=', self.company_id.id),
            ('date_order', '>=', fields.Datetime.to_string(start_dt)),
            ('date_order', '<=', fields.Datetime.to_string(end_dt)),
            ('state', 'not in', ['cancel']),
        ]
        if self.target_scope in ('salesperson', 'route_salesperson') and self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.target_scope in ('route', 'route_salesperson') and self.route_id:
            domain.append(('route_id', '=', self.route_id.id))
        return domain

    def _route_visit_domain(self):
        self.ensure_one()
        start_dt = datetime.combine(self.date_start, time.min)
        end_dt = datetime.combine(self.date_end, time.max)
        domain = [
            ('check_in', '>=', fields.Datetime.to_string(start_dt)),
            ('check_in', '<=', fields.Datetime.to_string(end_dt)),
            ('check_in', '!=', False),
            ('state', 'in', ['checked_in', 'checked_out', 'done']),
        ]
        if self.target_scope in ('salesperson', 'route_salesperson') and self.user_id:
            domain.append(('user_id', '=', self.user_id.id))
        if self.target_scope in ('route', 'route_salesperson') and self.route_id:
            domain.append(('route_id', '=', self.route_id.id))
        return domain

    def _settled_route_visit_domain(self):
        """Route visits that are settled in the route visit list.

        SKU achievement must count only Sales Orders that are attached to route
        visits whose POS settlement status is Settled.  This keeps SKU target
        tracking aligned with the field workflow instead of counting draft,
        unprocessed, or not-settled sales orders.
        """
        self.ensure_one()
        domain = list(self._route_visit_domain())
        Visit = self.env['sales.route.visit']
        if 'pos_settlement_status' in Visit._fields:
            domain.append(('pos_settlement_status', '=', 'settled'))
        return domain

    def _settled_sale_orders_for_sku_achievement(self):
        """Return only Sales Orders shown on settled route visits."""
        self.ensure_one()
        if 'sales.route.visit' not in self.env.registry:
            return self.env['sale.order']
        visits = self.env['sales.route.visit'].sudo().search(self._settled_route_visit_domain())
        orders = visits.mapped('sale_order_tag_ids') if visits and 'sale_order_tag_ids' in visits._fields else self.env['sale.order']
        if not orders:
            return orders
        # Keep the existing target scope/date/company safeguards as an additional filter.
        return orders.filtered_domain(self._sale_order_domain())

    def action_view_route_visit_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Settled Route Visit POS Orders / Collections / Amount Due'),
            'res_model': 'sales.route.visit',
            'view_mode': 'tree,form,pivot,graph',
            'domain': self._settled_route_visit_domain(),
            'context': {'create': False},
        }

    def _get_achievement_values(self):
        self.ensure_one()
        # Target achievement source of truth:
        # Keep the existing stored target field (sales_order_target_amount) so old
        # targets are not lost, but measure achievement from Route Visit POS
        # transaction values only.  This intentionally does not use
        # sale.order.amount_total.  Actual invoice/POS achievement comes from
        # ONLY settled sales.route.visit rows: pos_order_total_amount,
        # collections from pos_order_paid_amount, and amount due from
        # pos_order_due_amount.  This makes My Field Work and Manager Control
        # Panel target progress ignore draft / not-settled POS orders.
        visits = self.env['sales.route.visit'].sudo().search(self._settled_route_visit_domain()) if 'sales.route.visit' in self.env.registry else self.env['sales.route.visit']
        invoice_amount = sum(visits.mapped('pos_order_total_amount')) if visits and 'pos_order_total_amount' in visits._fields else 0.0
        collection_amount = sum(visits.mapped('pos_order_paid_amount')) if visits and 'pos_order_paid_amount' in visits._fields else 0.0
        if not collection_amount and visits and 'pos_order_payment_amount' in visits._fields:
            collection_amount = sum(visits.mapped('pos_order_payment_amount'))
        variance_amount = sum(visits.mapped('pos_order_due_amount')) if visits and 'pos_order_due_amount' in visits._fields else 0.0
        count = len(visits.filtered(lambda v: (v.pos_order_total_amount or 0.0) > 0)) if visits and 'pos_order_total_amount' in visits._fields else 0
        amount = invoice_amount
        sku_qty = 0.0
        if self.sku_target_line_ids and 'sales.route.sku.target.performance' in self.env.registry:
            try:
                Performance = self.env['sales.route.sku.target.performance'].sudo()
                Performance.recompute_for_targets(targets=self)
                perfs = Performance.search([('target_id', '=', self.id)])
                sku_qty = sum(perfs.mapped('sale_order_qty'))
            except Exception:
                sku_qty = 0.0
        sku_target_qty = sum(self.sku_target_line_ids.mapped('target_qty')) if self.sku_target_line_ids else 0.0
        sku_progress = (sku_qty / sku_target_qty * 100.0) if sku_target_qty else 0.0
        amount_target = self.sales_order_target_amount or 0.0
        count_target = self.sales_order_target_count or 0
        amount_progress = (amount / amount_target * 100.0) if amount_target else 0.0
        count_progress = (count / count_target * 100.0) if count_target else 0.0
        today = fields.Date.context_today(self)
        if today < self.date_start:
            state = 'not_started'
        elif (amount_target and amount >= amount_target) or (count_target and count >= count_target):
            state = 'achieved'
        elif today > self.date_end:
            state = 'expired'
        else:
            state = 'in_progress'
        return {
            'achieved_sales_amount': amount,
            'achieved_collection_amount': collection_amount,
            'achieved_variance_amount': variance_amount,
            'achieved_sales_count': count,
            'amount_progress': amount_progress,
            'count_progress': count_progress,
            'remaining_amount': max(amount_target - amount, 0.0),
            'remaining_count': max(count_target - count, 0),
            'achieved_sku_qty': sku_qty,
            'sku_progress': sku_progress,
            'state': state,
        }

    def _compute_achievement(self):
        for rec in self:
            vals = rec._get_achievement_values() if rec.date_start and rec.date_end else {}
            rec.achieved_sales_amount = vals.get('achieved_sales_amount', 0.0)
            rec.achieved_collection_amount = vals.get('achieved_collection_amount', 0.0)
            rec.achieved_variance_amount = vals.get('achieved_variance_amount', 0.0)
            rec.achieved_sales_count = vals.get('achieved_sales_count', 0)
            rec.amount_progress = vals.get('amount_progress', 0.0)
            rec.count_progress = vals.get('count_progress', 0.0)
            rec.remaining_amount = vals.get('remaining_amount', 0.0)
            rec.remaining_count = vals.get('remaining_count', 0)
            rec.achieved_sku_qty = vals.get('achieved_sku_qty', 0.0)
            rec.sku_progress = vals.get('sku_progress', 0.0)
            rec.state = vals.get('state', 'not_started')

    def action_view_sales_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Legacy Sales Orders (Reference Only)'),
            'res_model': 'sale.order',
            'view_mode': 'tree,form,pivot,graph',
            'domain': self._sale_order_domain(),
            'context': {'create': False},
        }

    def action_view_sku_sales_order_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Settled Route Visit SKU Sales Order Lines'),
            'res_model': 'sale.order.line',
            'view_mode': 'tree,form,pivot,graph',
            'domain': self._get_sku_target_order_lines_domain(),
            'context': {'create': False},
        }

    @api.model
    def fsrp_target_cards(self, user=None, route=None, limit=6):
        today = fields.Date.context_today(self)
        user = user or self.env.user
        domain = [('active', '=', True), ('date_start', '<=', today), ('date_end', '>=', today)]
        # My Field Work should only show targets that are explicitly assigned
        # to the current salesperson. Company-wide / route-group targets belong
        # on the Manager Control Panel only.
        personal_domain = domain + [
            ('target_scope', 'in', ['salesperson', 'route_salesperson']),
            ('user_id', '=', user.id),
        ]
        if route:
            personal_domain = personal_domain + ['|', ('route_id', '=', False), ('route_id', '=', route.id)]
        targets = self.sudo().search(personal_domain, order='date_end asc, id desc', limit=limit)

        # Manager panel cards: all company / route targets, not personal-only
        # salesperson targets. Route + Salesperson targets are included so
        # managers can see route-specific individual assignments too.
        group_targets = self.sudo().search(
            domain + [('target_scope', 'in', ['route', 'route_salesperson', 'all_routes'])],
            order='date_end asc, id desc',
            limit=limit,
        )

        def pack(targets):
            data=[]
            for t in targets:
                vals=t._get_achievement_values()
                progress=max(vals['amount_progress'], vals['count_progress'])
                data.append({
                    'id': t.id,
                    'name': t.name,
                    'scope': dict(t._fields['target_scope'].selection).get(t.target_scope),
                    'route': t.route_id.name or '',
                    'salesperson': t.user_id.name or '',
                    'period': '%s → %s' % (t.date_start, t.date_end),
                    'amount_target': t.sales_order_target_amount,
                    'amount_done': vals['achieved_sales_amount'],
                    'collection_done': vals.get('achieved_collection_amount', 0.0),
                    'variance_done': vals.get('achieved_variance_amount', 0.0),
                    'count_target': t.sales_order_target_count,
                    'count_done': vals['achieved_sales_count'],
                    'sku_target_qty': t.sku_target_qty_total,
                    'sku_done_qty': vals.get('achieved_sku_qty', 0.0),
                    'sku_progress': round(min(vals.get('sku_progress', 0.0), 100.0), 1),
                    'progress': round(min(max(progress, vals.get('sku_progress', 0.0)), 100.0), 1),
                    'raw_progress': round(progress, 1),
                    'state': vals['state'],
                })
            return data
        return {'personal_targets': pack(targets), 'group_targets': pack(group_targets)}

    def action_recompute_sku_target_performance(self):
        self.env['sales.route.sku.target.performance'].sudo().recompute_for_targets(targets=self)
        return {
            'type': 'ir.actions.act_window',
            'name': _('SKU Target Performance'),
            'res_model': 'sales.route.sku.target.performance',
            'view_mode': 'tree,kanban,pivot,graph',
            'domain': [('target_id', 'in', self.ids)],
            'context': {'create': False},
        }


class SalesRouteTargetSkuLine(models.Model):
    _name = 'sales.route.target.sku.line'
    _description = 'Sales Route SKU Target Line'
    _order = 'sequence, product_category_id, product_id, id'

    sequence = fields.Integer(default=10)
    target_id = fields.Many2one('sales.route.target', required=True, ondelete='cascade', index=True)
    product_category_id = fields.Many2one('product.category', string='Product Category', required=True, index=True)
    product_id = fields.Many2one('product.product', string='SKU / Product', domain="[('categ_id', 'child_of', product_category_id)]", index=True)
    target_qty = fields.Float(string='Target Qty', default=0.0)
    target_amount = fields.Monetary(string='Target Amount', currency_field='currency_id', default=0.0)
    currency_id = fields.Many2one(related='target_id.currency_id', store=True, readonly=True)
    achieved_qty = fields.Float(string='Achieved Qty', compute='_compute_sku_achievement')
    achieved_amount = fields.Monetary(string='Achieved Amount', currency_field='currency_id', compute='_compute_sku_achievement')
    progress = fields.Float(string='Progress %', compute='_compute_sku_achievement')
    note = fields.Char()

    @api.onchange('product_id')
    def _onchange_product_id_set_category(self):
        for rec in self:
            if rec.product_id and not rec.product_category_id:
                rec.product_category_id = rec.product_id.categ_id

    @api.depends('target_id.date_start', 'target_id.date_end', 'target_id.user_id', 'target_id.route_id', 'target_id.target_scope', 'product_id', 'product_category_id', 'target_qty', 'target_amount')
    def _compute_sku_achievement(self):
        Performance = self.env['sales.route.sku.target.performance'].sudo() if 'sales.route.sku.target.performance' in self.env.registry else False
        for rec in self:
            qty = amount = 0.0
            if rec.target_id and Performance:
                try:
                    Performance.recompute_for_targets(targets=rec.target_id)
                    perf = Performance.search([('target_line_id', '=', rec.id)], limit=1)
                    qty = perf.sale_order_qty if perf else 0.0
                    amount = perf.sale_order_amount if perf else 0.0
                except Exception:
                    qty = amount = 0.0
            rec.achieved_qty = qty
            rec.achieved_amount = amount
            denominator = rec.target_qty or 0.0
            rec.progress = (qty / denominator * 100.0) if denominator else 0.0

    @api.constrains('product_category_id', 'product_id')
    def _check_product_category_alignment(self):
        for rec in self:
            if rec.product_id and rec.product_category_id and rec.product_id.categ_id.id not in self.env['product.category'].search([('id', 'child_of', rec.product_category_id.id)]).ids:
                raise ValidationError(_('SKU must belong to the selected Product Category.'))
