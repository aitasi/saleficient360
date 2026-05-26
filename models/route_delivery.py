from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class SalesRouteVisitDeliveryLine(models.Model):
    _name = 'sales.route.visit.delivery.line'
    _description = 'Field Sales Delivery Line'
    _order = 'visit_id, sequence, id'

    sequence = fields.Integer(default=10)
    visit_id = fields.Many2one('sales.route.visit', string='Delivery Visit', required=True, ondelete='cascade', index=True)
    partner_id = fields.Many2one(related='visit_id.partner_id', string='Client', store=True, readonly=True)
    route_id = fields.Many2one(related='visit_id.route_id', string='Route', store=True, readonly=True)
    user_id = fields.Many2one(related='visit_id.user_id', string='Delivered By', store=True, readonly=True)
    source_sale_order_id = fields.Many2one(related='visit_id.delivery_source_sale_order_id', string='Source Sales Order', store=True, readonly=True)
    sale_order_line_id = fields.Many2one('sale.order.line', string='Source Order Line', index=True, ondelete='set null')
    product_id = fields.Many2one('product.product', string='Product', required=True, index=True)
    product_uom_id = fields.Many2one('uom.uom', string='UoM')
    ordered_qty = fields.Float(string='Ordered Qty', digits='Product Unit of Measure', readonly=True)
    already_delivered_qty = fields.Float(string='Already Delivered', compute='_compute_quantities', digits='Product Unit of Measure')
    remaining_qty = fields.Float(string='Remaining Before This Delivery', compute='_compute_quantities', digits='Product Unit of Measure')
    deliver_now_qty = fields.Float(string='Deliver Now', digits='Product Unit of Measure')
    delivered_qty = fields.Float(string='Delivered Qty', digits='Product Unit of Measure', readonly=True, copy=False)
    balance_after_delivery = fields.Float(string='Balance After Delivery', compute='_compute_quantities', digits='Product Unit of Measure')
    line_status = fields.Selection([
        ('pending', 'Pending'),
        ('partial', 'Partial'),
        ('done', 'Delivered'),
        ('over', 'Over Delivery'),
    ], string='Status', compute='_compute_quantities')
    note = fields.Char(string='Notes')

    @api.depends('sale_order_line_id', 'ordered_qty', 'deliver_now_qty', 'delivered_qty', 'visit_id.delivery_status')
    def _compute_quantities(self):
        for line in self:
            already = line._get_already_delivered_qty()
            remaining = max((line.ordered_qty or 0.0) - already, 0.0)
            balance_after = remaining - (line.deliver_now_qty or 0.0)
            line.already_delivered_qty = already
            line.remaining_qty = remaining
            line.balance_after_delivery = balance_after
            if (line.deliver_now_qty or 0.0) > remaining and remaining >= 0:
                line.line_status = 'over'
            elif balance_after <= 0 and line.ordered_qty:
                line.line_status = 'done'
            elif (line.deliver_now_qty or 0.0) > 0:
                line.line_status = 'partial'
            else:
                line.line_status = 'pending'

    def _get_already_delivered_qty(self):
        self.ensure_one()
        if not self.sale_order_line_id:
            return 0.0
        domain = [
            ('sale_order_line_id', '=', self.sale_order_line_id.id),
            ('visit_id.delivery_status', 'in', ['delivered', 'partial']),
        ]
        if self.visit_id:
            domain.append(('visit_id', '!=', self.visit_id.id))
        lines = self.sudo().search(domain)
        return sum(lines.mapped('delivered_qty'))

    @api.constrains('deliver_now_qty')
    def _check_deliver_now_qty(self):
        for line in self:
            if line.deliver_now_qty < 0:
                raise ValidationError(_('Deliver Now quantity cannot be negative.'))

    def _validate_before_confirm(self):
        for line in self:
            if line.deliver_now_qty < 0:
                raise UserError(_('Deliver Now quantity cannot be negative for %s.') % line.product_id.display_name)
            if line.deliver_now_qty and line.deliver_now_qty > line.remaining_qty:
                raise UserError(_('%s: Deliver Now quantity %.2f cannot exceed remaining quantity %.2f.') % (
                    line.product_id.display_name, line.deliver_now_qty, line.remaining_qty
                ))
        return True
