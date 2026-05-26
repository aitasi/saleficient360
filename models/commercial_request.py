from odoo import api, fields, models, _
from odoo.tools import html_escape
from odoo.exceptions import UserError


class FieldSalesCommercialRequest(models.Model):
    _name = 'field.sales.commercial.request'
    _description = 'Field Sales Commercial Approval Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    name = fields.Char(string='Request Ref', default='New', copy=False, readonly=True, tracking=True)
    request_type = fields.Selection([
        ('extra_discount', 'Extra Discount'),
        ('special_pricing', 'Special Pricing'),
        ('free_goods', 'Free Goods / Bonus Qty'),
        ('credit_extension', 'Credit Extension'),
        ('payment_terms', 'Payment Terms Extension'),
        ('overdue_release', 'Overdue / Credit Hold Release'),
        ('stock_exception', 'Stock Exception'),
        ('urgent_delivery', 'Urgent Delivery'),
        ('complaint_escalation', 'Complaint Escalation'),
        ('management_intervention', 'Management Intervention'),
        ('vip_support', 'VIP Customer Support'),
        ('other', 'Other Request'),
    ], string='Request Type', required=True, default='extra_discount', tracking=True)
    title = fields.Char(string='Request Title', required=True, tracking=True)
    description = fields.Text(string='Request Details / Reason', required=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('clarification', 'Clarification Requested'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status', tracking=True, index=True)

    requested_by_id = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user, required=True, tracking=True)
    assigned_to_id = fields.Many2one('res.users', string='Send To / Approver', tracking=True, help='User who should approve or respond to this request.')
    approved_by_id = fields.Many2one('res.users', string='Actioned By', readonly=True, tracking=True)
    approved_date = fields.Datetime(string='Actioned On', readonly=True)

    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True, index=True)
    route_id = fields.Many2one('sales.route', string='Route', tracking=True, index=True)
    route_visit_id = fields.Many2one('sales.route.visit', string='Route Visit', ondelete='set null', tracking=True)
    sale_order_id = fields.Many2one('sale.order', string='Related Sales Order', ondelete='set null', tracking=True)
    plan_id = fields.Many2one('sales.route.plan', string='Route Plan', tracking=True)

    urgency = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ], default='normal', tracking=True)
    expected_value_impact = fields.Monetary(string='Expected Value Impact', currency_field='currency_id')
    requested_discount = fields.Monetary(string='Requested Discount Amount', currency_field='currency_id')
    current_discount = fields.Monetary(string='Current Discount Amount', currency_field='currency_id')
    approved_message = fields.Text(string='Approved / Response Message', help='Message shown to the salesperson after approval/rejection. This does not change the Sales Order automatically.')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)

    def _default_assigned_to(self):
        self.ensure_one()
        if self.route_visit_id and self.route_visit_id.plan_id and self.route_visit_id.plan_id.supervisor_id:
            return self.route_visit_id.plan_id.supervisor_id
        if self.plan_id and self.plan_id.supervisor_id:
            return self.plan_id.supervisor_id
        if self.route_id and getattr(self.route_id, 'supervisor_ids', False):
            return self.route_id.supervisor_ids[:1]
        group = self.env.ref('field_sales_route_plan.group_field_sales_manager', raise_if_not_found=False)
        return group.users[:1] if group and group.users else False

    @api.onchange('route_visit_id')
    def _onchange_route_visit_id(self):
        if self.route_visit_id:
            visit = self.route_visit_id
            self.partner_id = visit.partner_id
            self.route_id = visit.route_id
            self.plan_id = visit.plan_id
            if not self.assigned_to_id:
                self.assigned_to_id = self._default_assigned_to()

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        if self.sale_order_id:
            order = self.sale_order_id
            self.partner_id = order.partner_id
            self.route_id = order.route_id
            self.plan_id = order.route_plan_id
            if not self.expected_value_impact:
                self.expected_value_impact = order.amount_total
            if not self.assigned_to_id:
                self.assigned_to_id = self._default_assigned_to()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('field.sales.commercial.request') or 'CR/New'
        records = super().create(vals_list)
        for rec in records:
            if not rec.assigned_to_id:
                approver = rec._default_assigned_to()
                if approver:
                    rec.assigned_to_id = approver.id
        return records

    def _notify_users(self, users, subject, body):
        Mail = self.env['mail.mail'].sudo()
        for rec in self:
            partners = users.mapped('partner_id').filtered(lambda p: p.id)
            if partners:
                rec.message_post(body=body, subject=subject, partner_ids=partners.ids)
            seen = set()
            for user in users:
                email_to = user.email or user.partner_id.email
                if not email_to or email_to.lower() in seen:
                    continue
                seen.add(email_to.lower())
                Mail.create({
                    'subject': subject,
                    'email_to': email_to,
                    'body_html': '<p>%s</p>' % html_escape(body).replace('\n', '<br/>'),
                    'auto_delete': True,
                }).send()

    def action_submit(self):
        for rec in self:
            if rec.state not in ('draft', 'clarification'):
                raise UserError(_('Only draft or clarification requests can be submitted.'))
            if not rec.assigned_to_id:
                raise UserError(_('Please select the user who should approve/respond to this request.'))
            rec.state = 'pending'
            body = _('%(user)s submitted %(type)s request %(ref)s for client %(client)s.\n\n%(title)s\n%(description)s') % {
                'user': rec.requested_by_id.name,
                'type': dict(rec._fields['request_type'].selection).get(rec.request_type, rec.request_type),
                'ref': rec.name,
                'client': rec.partner_id.display_name,
                'title': rec.title,
                'description': rec.description or '',
            }
            rec._notify_users(rec.assigned_to_id, _('Commercial Request Submitted'), body)
        return True

    def action_approve(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be approved.'))
            rec.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            msg = rec.approved_message or _('Approved. Please proceed according to the approval message. No Sales Order values or discounts were changed automatically.')
            body = _('Your commercial request %(ref)s for %(client)s has been APPROVED by %(approver)s.\n\nMessage: %(msg)s') % {
                'ref': rec.name,
                'client': rec.partner_id.display_name,
                'approver': self.env.user.name,
                'msg': msg,
            }
            rec._notify_users(rec.requested_by_id, _('Commercial Request Approved'), body)
        return True

    def action_reject(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be rejected.'))
            rec.write({
                'state': 'rejected',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            msg = rec.approved_message or _('Rejected. No Sales Order values or discounts were changed.')
            body = _('Your commercial request %(ref)s for %(client)s has been REJECTED by %(approver)s.\n\nReason: %(msg)s') % {
                'ref': rec.name,
                'client': rec.partner_id.display_name,
                'approver': self.env.user.name,
                'msg': msg,
            }
            rec._notify_users(rec.requested_by_id, _('Commercial Request Rejected'), body)
        return True

    def action_request_clarification(self):
        for rec in self:
            if rec.state != 'pending':
                raise UserError(_('Only pending requests can be returned for clarification.'))
            rec.write({
                'state': 'clarification',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            msg = rec.approved_message or _('Please provide more information before approval can be granted.')
            body = _('Clarification is needed for commercial request %(ref)s for %(client)s.\n\nMessage: %(msg)s') % {
                'ref': rec.name,
                'client': rec.partner_id.display_name,
                'msg': msg,
            }
            rec._notify_users(rec.requested_by_id, _('Commercial Request Needs Clarification'), body)
        return True

    def action_cancel(self):
        self.write({'state': 'cancelled'})
        return True


class SalesRouteVisit(models.Model):
    _inherit = 'sales.route.visit'

    commercial_request_ids = fields.One2many('field.sales.commercial.request', 'route_visit_id', string='Requests')
    commercial_request_count = fields.Integer(string='Requests', compute='_compute_commercial_request_count')

    def _compute_commercial_request_count(self):
        for visit in self:
            visit.commercial_request_count = len(visit.commercial_request_ids)

    def action_create_commercial_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request'),
            'res_model': 'field.sales.commercial.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_route_visit_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_route_id': self.route_id.id,
                'default_plan_id': self.plan_id.id,
                'default_requested_by_id': self.env.user.id,
                'default_title': _('Request for %s') % (self.partner_id.display_name,),
                'default_expected_value_impact': self.sale_order_total_amount or self.pos_order_total_amount,
            },
        }

    def action_view_commercial_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requests'),
            'res_model': 'field.sales.commercial.request',
            'view_mode': 'tree,form',
            'domain': [('route_visit_id', '=', self.id)],
            'context': {'default_route_visit_id': self.id, 'default_partner_id': self.partner_id.id, 'default_route_id': self.route_id.id},
        }


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    commercial_request_ids = fields.One2many('field.sales.commercial.request', 'sale_order_id', string='Requests')
    commercial_request_count = fields.Integer(string='Requests', compute='_compute_commercial_request_count')

    def _compute_commercial_request_count(self):
        for order in self:
            order.commercial_request_count = len(order.commercial_request_ids)

    def action_create_commercial_request(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Request'),
            'res_model': 'field.sales.commercial.request',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_sale_order_id': self.id,
                'default_partner_id': self.partner_id.id,
                'default_route_id': self.route_id.id,
                'default_plan_id': self.route_plan_id.id,
                'default_requested_by_id': self.env.user.id,
                'default_title': _('Request on %s') % (self.name,),
                'default_expected_value_impact': self.amount_total,
            },
        }

    def action_view_commercial_requests(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Requests'),
            'res_model': 'field.sales.commercial.request',
            'view_mode': 'tree,form',
            'domain': [('sale_order_id', '=', self.id)],
            'context': {'default_sale_order_id': self.id, 'default_partner_id': self.partner_id.id, 'default_route_id': self.route_id.id},
        }
