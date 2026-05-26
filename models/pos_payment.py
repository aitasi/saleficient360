from odoo import api, models


class PosPayment(models.Model):
    _inherit = 'pos.payment'

    def _fsrp_refresh_route_visit_pos_summary(self):
        orders = self.mapped('pos_order_id') if 'pos_order_id' in self._fields else self.env['pos.order']
        if orders and hasattr(orders, '_refresh_route_visit_pos_summary_cache'):
            orders._sync_route_visit_from_sale_orders()
            orders._refresh_route_visit_pos_summary_cache()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        payments = super().create(vals_list)
        payments._fsrp_refresh_route_visit_pos_summary()
        return payments

    def write(self, vals):
        before_orders = self.mapped('pos_order_id') if 'pos_order_id' in self._fields else self.env['pos.order']
        res = super().write(vals)
        after_orders = self.mapped('pos_order_id') if 'pos_order_id' in self._fields else self.env['pos.order']
        orders = before_orders | after_orders
        if orders and hasattr(orders, '_refresh_route_visit_pos_summary_cache'):
            orders._sync_route_visit_from_sale_orders()
            orders._refresh_route_visit_pos_summary_cache()
        return res

    def unlink(self):
        orders = self.mapped('pos_order_id') if 'pos_order_id' in self._fields else self.env['pos.order']
        res = super().unlink()
        if orders and hasattr(orders, '_refresh_route_visit_pos_summary_cache'):
            orders._refresh_route_visit_pos_summary_cache()
        return res
