from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = 'pos.order'

    route_id = fields.Many2one('sales.route', string='Market Route')
    route_plan_id = fields.Many2one('sales.route.plan', string='Daily Route Plan')
    route_plan_line_id = fields.Many2one('sales.route.plan.line', string='Route Plan Visit')

    def _order_fields(self, ui_order):
        vals = super()._order_fields(ui_order)
        # Allow future/mobile POS integrations to pass route context into the POS order JSON.
        if ui_order.get('route_plan_line_id'):
            line = self.env['sales.route.plan.line'].browse(ui_order['route_plan_line_id']).exists()
            if line:
                vals.update({
                    'route_plan_line_id': line.id,
                    'route_plan_id': line.plan_id.id,
                    'route_id': line.route_id.id,
                })
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_route_visit_from_sale_orders()
        orders._refresh_route_visit_pos_summary_cache()
        return orders

    def write(self, vals):
        before_visits = self._linked_route_visits_for_pos_orders()
        res = super().write(vals)
        if any(key in vals for key in ['sale_order_id', 'sale_order_ids', 'sale_order_origin_id', 'origin', 'state', 'amount_total', 'amount_paid', 'amount_return', 'payment_ids', 'pos_reference', 'name']):
            self._sync_route_visit_from_sale_orders()
            (before_visits | self._linked_route_visits_for_pos_orders())._compute_visit_orders()
        return res

    def _linked_route_visits_for_pos_orders(self):
        Visit = self.env['sales.route.visit'].sudo()
        visits = Visit.browse()
        for order in self.sudo():
            if 'route_plan_line_id' in order._fields and order.route_plan_line_id:
                visits |= Visit.search([('plan_line_id', '=', order.route_plan_line_id.id)])
            for sale_order in order._linked_route_sale_orders():
                if sale_order.route_plan_line_id:
                    visits |= Visit.search([('plan_line_id', '=', sale_order.route_plan_line_id.id)])
        return visits

    def _refresh_route_visit_pos_summary_cache(self):
        visits = self._linked_route_visits_for_pos_orders()
        if visits:
            visits._compute_visit_orders()
        return True

    def _linked_route_sale_orders(self):
        """Return route Sale Orders linked to this POS order.

        This is intentionally broad because different Odoo POS/Sale flows store
        the POS settlement relation in different places. It supports:
        - pos.order sale_order_id / sale_order_ids / sale_order_origin_id fields
        - pos.order.line links to sale.order or sale.order.line
        - textual fallbacks such as origin/note/name/pos_reference containing SO number
        """
        self.ensure_one()
        SaleOrder = self.env['sale.order'].sudo()
        orders = SaleOrder.browse()

        def add(value):
            nonlocal orders
            if value:
                orders |= value.exists().sudo()

        for field_name, field in self._fields.items():
            try:
                if getattr(field, 'comodel_name', False) == 'sale.order':
                    add(self[field_name])
            except Exception:
                pass

        # POS line links are the most reliable in many pos_sale deployments.
        if 'lines' in self._fields and self.lines:
            for line in self.lines:
                for field_name, field in line._fields.items():
                    try:
                        if getattr(field, 'comodel_name', False) == 'sale.order':
                            add(line[field_name])
                        elif getattr(field, 'comodel_name', False) == 'sale.order.line':
                            so_lines = line[field_name]
                            if so_lines:
                                add(so_lines.mapped('order_id'))
                    except Exception:
                        pass

        # Controlled text fallback for customizations that only keep SO number.
        text_values = []
        for field_name in ['origin', 'note', 'pos_reference', 'name']:
            if field_name in self._fields:
                try:
                    val = self[field_name]
                    if val and isinstance(val, str):
                        text_values.append(val)
                except Exception:
                    pass
        if text_values:
            route_orders = SaleOrder.search([('route_plan_line_id', '!=', False)])
            for so in route_orders:
                if so.name and any(so.name in txt for txt in text_values):
                    add(so)

        return orders.filtered(lambda so: so.route_plan_line_id)

    def _sync_route_visit_from_sale_orders(self):
        for order in self:
            if order.route_plan_line_id:
                continue
            sale_orders = order._linked_route_sale_orders()
            route_so = sale_orders[:1]
            if route_so:
                # Avoid re-entering write() sync logic. These fields are only
                # helper links used by field-route reports.
                super(PosOrder, order).write({
                    'route_plan_line_id': route_so.route_plan_line_id.id,
                    'route_plan_id': route_so.route_plan_id.id,
                    'route_id': route_so.route_id.id,
                })
