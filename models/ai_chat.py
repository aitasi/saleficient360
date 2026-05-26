from odoo import api, fields, models, _


class SalesRouteAIChat(models.Model):
    _name = 'sales.route.ai.chat'
    _description = 'Field Sales AI Chat Assistant'
    _inherit = ['mail.thread']
    _order = 'create_date desc, id desc'

    name = fields.Char(default='AI Chat', required=True)
    user_id = fields.Many2one('res.users', default=lambda self: self.env.user, index=True, required=True)
    partner_id = fields.Many2one('res.partner', string='Client')
    route_id = fields.Many2one('sales.route', string='Route')
    visit_id = fields.Many2one('sales.route.visit', string='Visit')
    question = fields.Text(required=True)
    answer = fields.Text(readonly=True)

    def action_ask(self):
        for rec in self:
            rec.answer = rec._build_answer()
            rec.message_post(body='<b>Question:</b><br/>%s<br/><br/><b>Assistant:</b><br/>%s' % ((rec.question or '').replace('\n', '<br/>'), (rec.answer or '').replace('\n', '<br/>')))
        return True

    def _build_answer(self):
        self.ensure_one()
        partner = self.partner_id or self.visit_id.partner_id
        route = self.route_id or self.visit_id.route_id
        q = (self.question or '').lower()
        lines = []
        if partner:
            sale_orders = self.env['sale.order'].search([('partner_id', '=', partner.id), ('state', 'in', ['sale', 'done'])], order='date_order desc', limit=10)
            last = sale_orders[:1]
            total = sum(sale_orders.mapped('amount_total'))
            lines.append(_('Client: %s') % partner.display_name)
            if last:
                lines.append(_('Last confirmed sale: %s, amount %.2f') % (last.name, last.amount_total))
                products = last.order_line.mapped('product_id.display_name')[:8]
                if products:
                    lines.append(_('Suggested reorder products: %s') % ', '.join(products))
            else:
                lines.append(_('No confirmed sales found for this client. Consider a marketing follow-up or introductory offer.'))
            if total:
                lines.append(_('Recent confirmed sales value checked: %.2f') % total)
        if route:
            today = fields.Date.context_today(self)
            plans = self.env['sales.route.plan'].search([('route_id', '=', route.id), ('date', '=', today)]) if 'date' in self.env['sales.route.plan']._fields else self.env['sales.route.plan']
            visits = self.env['sales.route.visit'].search([('route_id', '=', route.id), ('user_id', '=', self.user_id.id), ('check_in', '>=', str(today) + ' 00:00:00')])
            lines.append(_('Route: %s') % route.display_name)
            lines.append(_('Visits checked in today on this route: %s') % len(visits))
        if 'not buy' in q or 'no sale' in q or 'follow' in q:
            lines.append(_('Recommended action: create a follow-up activity, capture reason for no purchase, and schedule the client for the next route cycle.'))
        elif 'target' in q:
            lines.append(_('Recommended action: focus on clients with recent purchase history first, then visit dormant clients with a focused promotion.'))
        elif 'delivery' in q:
            lines.append(_('Recommended action: capture recipient name, delivery status, proof photo/signature, and shortage/damage notes before checkout.'))
        elif not lines:
            lines.append(_('Ask about a client, route, target, delivery, reorder, or follow-up.'))
        lines.append(_('Note: this is a rule-based assistant using Odoo data available to your user.'))
        return '\n'.join(lines)
