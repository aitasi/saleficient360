from math import radians, sin, cos, sqrt, atan2
import json
import logging
from urllib.parse import quote

import requests
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SalesRouteVisit(models.Model):
    _name = 'sales.route.visit'
    _description = 'Route Client Visit with GPS Check In/Out'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'check_in desc, id desc'

    name = fields.Char(compute='_compute_name', store=True)
    plan_id = fields.Many2one('sales.route.plan', string='Daily Plan')
    plan_line_id = fields.Many2one('sales.route.plan.line', string='Plan Line')
    route_id = fields.Many2one('sales.route', required=True)
    user_id = fields.Many2one('res.users', string='Salesperson', index=True, required=True, default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, index=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('checked_in', 'Checked In'),
        ('checked_out', 'Checked Out'),
    ], default='draft', tracking=True)
    check_in = fields.Datetime(readonly=True)
    check_out = fields.Datetime(readonly=True)
    checkin_latitude = fields.Float(digits=(16, 7), readonly=True)
    checkin_longitude = fields.Float(digits=(16, 7), readonly=True)
    checkout_latitude = fields.Float(digits=(16, 7), readonly=True)
    checkout_longitude = fields.Float(digits=(16, 7), readonly=True)
    checkin_place = fields.Char(readonly=True)
    checkout_place = fields.Char(readonly=True)
    checkin_address = fields.Text(string='Check In Address', readonly=True)
    checkout_address = fields.Text(string='Check Out Address', readonly=True)
    checkin_area = fields.Char(string='Check In Area/Town', readonly=True)
    checkout_area = fields.Char(string='Check Out Area/Town', readonly=True)
    checkin_geocode_json = fields.Text(string='Check In Geocode Raw Response', readonly=True)
    checkout_geocode_json = fields.Text(string='Check Out Geocode Raw Response', readonly=True)
    distance_from_client_m = fields.Float(compute='_compute_distance', store=True)
    allowed_radius_m = fields.Float(default=300.0, string='Allowed Radius (m)')
    within_allowed_radius = fields.Boolean(compute='_compute_distance', store=True)
    duration_minutes = fields.Float(compute='_compute_duration', store=True)
    suspicious_visit = fields.Boolean(compute='_compute_duration', store=True)
    sale_order_tag_ids = fields.Many2many('sale.order', compute='_compute_visit_orders', store=True, readonly=True, string='Sales Orders')
    sale_order_numbers = fields.Char(compute='_compute_visit_orders', store=True, readonly=True, string='Sales Orders')
    sale_order_total_amount = fields.Monetary(compute='_compute_visit_orders', store=True, readonly=True, string='Total Sales Order Amount', currency_field='currency_id')
    sale_order_product_names = fields.Text(compute='_compute_visit_orders', store=True, readonly=True, string='Product Category')
    sale_order_product_qtys = fields.Text(compute='_compute_visit_orders', store=True, readonly=True, string='Quantity')
    pos_order_ids = fields.Many2many('pos.order', compute='_compute_visit_orders', store=True, readonly=True, string='POS Orders')
    pos_order_receipt_numbers = fields.Char(compute='_compute_visit_orders', store=True, readonly=True, string='POS Receipt Number')
    pos_order_total_amount = fields.Monetary(compute='_compute_visit_orders', store=True, readonly=True, string='POS Order Amount', currency_field='currency_id')
    pos_order_paid_amount = fields.Monetary(compute='_compute_visit_orders', store=True, readonly=True, string='POS Paid Amount', currency_field='currency_id')
    pos_order_payment_amount = fields.Monetary(compute='_compute_visit_orders', store=True, readonly=True, string='POS Payment Amount', currency_field='currency_id')
    pos_order_due_amount = fields.Monetary(compute='_compute_visit_orders', store=True, readonly=True, string='POS Amount Due', currency_field='currency_id')
    pos_settlement_status = fields.Selection([
        ('not_settled', 'Not Settled'),
        ('settled', 'Settled'),
    ], string='POS Settled?', compute='_compute_visit_orders', store=True, readonly=True)
    currency_id = fields.Many2one('res.currency', related='plan_id.company_id.currency_id')
    shop_photo = fields.Binary(string='Shop Photo')
    shop_photo_filename = fields.Char()
    shelf_photo = fields.Binary(string='Shelf / Display Photo')
    shelf_photo_filename = fields.Char()
    competitor_photo = fields.Binary(string='Competitor Photo')
    competitor_photo_filename = fields.Char()
    delivery_status = fields.Selection([
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('partial', 'Partially Delivered'),
        ('failed', 'Failed'),
    ], string='Delivery Status', default='pending', tracking=True)
    delivery_recipient_name = fields.Char(string='Recipient Name')
    delivery_recipient_phone = fields.Char(string='Recipient Phone')
    delivery_reference = fields.Char(string='Delivery Reference')
    delivery_source_sale_order_id = fields.Many2one('sale.order', string='Source Sales Order', compute='_compute_delivery_source_order', store=True, readonly=False, help='Sales Order being delivered during this delivery visit. Auto-filled from earlier sales for this client.')
    delivery_source_order_number = fields.Char(string='Source SO Number', related='delivery_source_sale_order_id.name', store=True, readonly=True)
    delivery_done_count = fields.Integer(string='Deliveries Done for Client', compute='_compute_delivery_source_order', store=True)
    delivery_order_qty = fields.Float(string='Source Order Qty', compute='_compute_delivery_source_order', store=True)
    delivery_sequence = fields.Integer(string='Delivery # for Source Order', compute='_compute_delivery_totals', store=True)
    delivery_line_ids = fields.One2many('sales.route.visit.delivery.line', 'visit_id', string='Delivery Lines')
    delivery_line_count = fields.Integer(string='Delivery Lines', compute='_compute_delivery_totals', store=True)
    delivery_total_ordered_qty = fields.Float(string='Ordered Qty', compute='_compute_delivery_totals', store=True)
    delivery_total_already_delivered_qty = fields.Float(string='Already Delivered Qty', compute='_compute_delivery_totals', store=True)
    delivery_total_remaining_qty = fields.Float(string='Remaining Qty', compute='_compute_delivery_totals', store=True)
    delivery_total_deliver_now_qty = fields.Float(string='Deliver Now Qty', compute='_compute_delivery_totals', store=True)
    delivery_total_delivered_qty = fields.Float(string='Delivered Qty', compute='_compute_delivery_totals', store=True)
    delivery_completion_percent = fields.Float(string='Delivery Completion %', compute='_compute_delivery_totals', store=True)
    delivery_proof_photo = fields.Binary(string='Delivery Proof Photo')
    delivery_proof_photo_filename = fields.Char()
    delivery_signature = fields.Binary(string='Recipient Signature')
    delivery_signature_filename = fields.Char()
    delivery_notes = fields.Text(string='Delivery Notes')
    note = fields.Text()

    client_last_purchase_date = fields.Date(string='Last Purchase', compute='_compute_client_intelligence')
    client_total_spend = fields.Monetary(string='Client Total Spend', compute='_compute_client_intelligence', currency_field='currency_id')
    client_outstanding_amount = fields.Monetary(string='Outstanding Balance', compute='_compute_client_intelligence', currency_field='currency_id')
    client_favorite_products = fields.Char(string='Frequent Products', compute='_compute_client_intelligence')
    next_best_action = fields.Char(string='Next Best Action', compute='_compute_client_intelligence')
    smart_recommendation_text = fields.Text(string='Smart Client Recommendations', compute='_compute_client_intelligence')
    client_visit_history_timeline = fields.Text(string='Client Visit History Timeline', compute='_compute_client_history_timeline')
    merchandising_audit_ids = fields.One2many('sales.route.merchandising.audit', 'visit_id', string='Merchandising Audits')
    merchandising_audit_count = fields.Integer(string='Merchandising Audits', compute='_compute_merchandising_audit_count')
    smart_reminder_ids = fields.One2many('sales.route.smart.reminder', 'visit_id', string='Smart Reminders')

    visit_purpose = fields.Selection([
        ('marketing', 'Marketing'),
        ('sales', 'Sales'),
        ('delivery', 'Delivery'),
        ('merchandising', 'Merchandising'),
        ('retail_sales', 'Retail Sales Visit'),
        ('van_sales', 'Van Sales'),
        ('other', 'Other'),
    ], string='Visit Purpose Type', default='sales', tracking=True, required=True)
    visit_purpose_id = fields.Many2one('sales.route.visit.purpose', string='Visit Purpose', tracking=True, default=lambda self: self._default_visit_purpose_id())
    visit_purpose_category = fields.Selection(related='visit_purpose_id.category', string='Visit Purpose Category', readonly=True)
    program_issued = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Program / Catalogue Issued?', default='no')
    program_custom_count = fields.Integer(string='Other Program Count', default=0)
    program_count = fields.Integer(string='Program Count', compute='_compute_program_count', store=True)
    program_line_ids = fields.One2many('sales.route.visit.program.line', 'visit_id', string='Program / Catalogue Counts')
    program_line_summary = fields.Char(string='Program Counts', compute='_compute_program_line_summary')
    program_count_col_01 = fields.Integer(string='Program 1 Count', compute='_compute_program_count_columns')
    program_count_col_02 = fields.Integer(string='Program 2 Count', compute='_compute_program_count_columns')
    program_count_col_03 = fields.Integer(string='Program 3 Count', compute='_compute_program_count_columns')
    program_count_col_04 = fields.Integer(string='Program 4 Count', compute='_compute_program_count_columns')
    program_count_col_05 = fields.Integer(string='Program 5 Count', compute='_compute_program_count_columns')
    program_count_col_06 = fields.Integer(string='Program 6 Count', compute='_compute_program_count_columns')
    program_count_col_07 = fields.Integer(string='Program 7 Count', compute='_compute_program_count_columns')
    program_count_col_08 = fields.Integer(string='Program 8 Count', compute='_compute_program_count_columns')
    program_count_col_09 = fields.Integer(string='Program 9 Count', compute='_compute_program_count_columns')
    program_count_col_10 = fields.Integer(string='Program 10 Count', compute='_compute_program_count_columns')
    program_count_col_11 = fields.Integer(string='Program 11 Count', compute='_compute_program_count_columns')
    program_count_col_12 = fields.Integer(string='Program 12 Count', compute='_compute_program_count_columns')
    program_count_col_13 = fields.Integer(string='Program 13 Count', compute='_compute_program_count_columns')
    program_count_col_14 = fields.Integer(string='Program 14 Count', compute='_compute_program_count_columns')
    program_count_col_15 = fields.Integer(string='Program 15 Count', compute='_compute_program_count_columns')
    program_count_col_16 = fields.Integer(string='Program 16 Count', compute='_compute_program_count_columns')
    program_count_col_17 = fields.Integer(string='Program 17 Count', compute='_compute_program_count_columns')
    program_count_col_18 = fields.Integer(string='Program 18 Count', compute='_compute_program_count_columns')
    program_count_col_19 = fields.Integer(string='Program 19 Count', compute='_compute_program_count_columns')
    program_count_col_20 = fields.Integer(string='Program 20 Count', compute='_compute_program_count_columns')
    program_id = fields.Many2one('sales.route.marketing.program', string='Program / Catalogue Issued')
    program_ids = fields.Many2many('sales.route.marketing.program', 'sales_route_visit_program_rel', 'visit_id', 'program_id', string='Programs / Catalogues Issued')
    marketing_notes = fields.Text(string='Marketing Notes / Follow-up Information')
    marketing_activities_done = fields.Text(string='Activities Done at Client Place')
    contact_person_name = fields.Char(string='Contact Person Name')
    contact_person_phone = fields.Char(string='Contact Person Phone')
    contact_person_email = fields.Char(string='Contact Person Email')
    opportunity_ids = fields.One2many('crm.lead', 'route_visit_id', string='Opportunities')
    opportunity_count = fields.Integer(compute='_compute_opportunity_count', string='Opportunities')
    marketing_history_ids = fields.One2many(related='partner_id.marketing_history_ids', string='Previous Marketing History', readonly=True)
    client_sales_aging_bucket = fields.Selection(related='partner_id.route_age_bucket', string='Client Sales Aging', readonly=True)
    client_customer_classification = fields.Selection(related='partner_id.customer_classification', string='Client Class', readonly=True)
    client_route_sales_potential = fields.Float(related='partner_id.route_sales_potential', string='Sales Potential', readonly=True)
    client_days_since_last_purchase = fields.Integer(related='partner_id.days_since_last_purchase', string='Days Since Last Purchase', readonly=True)
    client_communication_summary = fields.Text(string='Client Communication Summary', compute='_compute_client_communication_summary')
    client_followup_summary = fields.Char(string='Follow-up Summary Text', compute='_compute_client_communication_summary')

    def _safe_client_text(self, value):
        return (value or '').strip()

    @api.depends('marketing_activities_done', 'marketing_notes', 'note', 'followup_summary', 'followup_note', 'visit_purpose_id', 'visit_purpose', 'pos_settlement_status', 'pos_order_total_amount', 'pos_order_paid_amount', 'pos_order_due_amount')
    def _compute_client_communication_summary(self):
        purpose_labels = dict(self._fields['visit_purpose'].selection)
        for visit in self:
            parts = []
            purpose = visit.visit_purpose_id.name or purpose_labels.get(visit.visit_purpose) or 'Visit'
            parts.append('Purpose: %s' % purpose)
            if visit.pos_settlement_status:
                parts.append('Settlement: %s' % dict(visit._fields['pos_settlement_status'].selection).get(visit.pos_settlement_status, visit.pos_settlement_status))
            if visit.pos_order_total_amount:
                parts.append('POS Order: %s' % visit.pos_order_total_amount)
            if visit.pos_order_paid_amount:
                parts.append('POS Paid: %s' % visit.pos_order_paid_amount)
            if visit.pos_order_due_amount:
                parts.append('Amount Due: %s' % visit.pos_order_due_amount)
            for text in [visit.marketing_activities_done, visit.marketing_notes, visit.note, visit.followup_note]:
                clean = visit._safe_client_text(text)
                if clean:
                    parts.append(clean)
            visit.client_communication_summary = '\n'.join(parts)
            visit.client_followup_summary = visit.followup_summary or visit.followup_note or ''
    followup_activity_type_id = fields.Many2one('mail.activity.type', string='Follow-up Activity Type')
    followup_date_deadline = fields.Date(string='Follow-up Due Date')
    followup_summary = fields.Char(string='Follow-up Summary')
    followup_note = fields.Text(string='Follow-up Note')


    @api.depends('partner_id', 'check_in', 'visit_purpose', 'visit_purpose_id', 'delivery_status')
    def _compute_delivery_source_order(self):
        SaleOrder = self.env['sale.order'].sudo()
        Visit = self.env['sales.route.visit'].sudo()
        for rec in self:
            rec.delivery_done_count = 0
            rec.delivery_order_qty = 0.0
            if rec.partner_id:
                rec.delivery_done_count = Visit.search_count([
                    ('partner_id', '=', rec.partner_id.id),
                    ('delivery_status', '=', 'delivered'),
                ])
            if not rec.partner_id:
                rec.delivery_source_sale_order_id = False
                continue
            # Keep a manually selected source order if it still belongs to the same client.
            if rec.delivery_source_sale_order_id and rec.delivery_source_sale_order_id.partner_id == rec.partner_id:
                source_order = rec.delivery_source_sale_order_id
            else:
                domain = [
                    ('partner_id', '=', rec.partner_id.id),
                    ('state', 'not in', ['cancel']),
                ]
                if rec.check_in:
                    domain.append(('date_order', '<=', rec.check_in))
                plan_line_db_id = rec.plan_line_id.id if rec.plan_line_id and isinstance(rec.plan_line_id.id, int) else False
                if plan_line_db_id:
                    domain.append(('route_plan_line_id', '!=', plan_line_db_id))
                source_order = SaleOrder.search(domain, order='date_order desc, id desc', limit=1)
                rec.delivery_source_sale_order_id = source_order
            rec.delivery_order_qty = sum(source_order.order_line.filtered(lambda l: not l.display_type).mapped('product_uom_qty')) if source_order else 0.0


    @api.depends(
        'delivery_source_sale_order_id',
        'delivery_line_ids.ordered_qty',
        'delivery_line_ids.already_delivered_qty',
        'delivery_line_ids.remaining_qty',
        'delivery_line_ids.deliver_now_qty',
        'delivery_line_ids.delivered_qty',
        'delivery_status',
    )
    def _compute_delivery_totals(self):
        Visit = self.env['sales.route.visit'].sudo()
        for rec in self:
            lines = rec.delivery_line_ids
            rec.delivery_line_count = len(lines)
            rec.delivery_total_ordered_qty = sum(lines.mapped('ordered_qty'))
            rec.delivery_total_already_delivered_qty = sum(lines.mapped('already_delivered_qty'))
            rec.delivery_total_remaining_qty = sum(lines.mapped('remaining_qty'))
            rec.delivery_total_deliver_now_qty = sum(lines.mapped('deliver_now_qty'))
            rec.delivery_total_delivered_qty = sum(lines.mapped('delivered_qty'))
            if rec.delivery_source_sale_order_id:
                domain = [
                    ('delivery_source_sale_order_id', '=', rec.delivery_source_sale_order_id.id),
                    ('delivery_status', 'in', ['delivered', 'partial']),
                ]
                # Unsaved records use Odoo NewId placeholders during onchange. Do not
                # send those placeholders to PostgreSQL as an integer id comparison.
                rec_db_id = rec._origin.id if rec._origin and isinstance(rec._origin.id, int) else False
                if rec_db_id:
                    domain.append(('id', '!=', rec_db_id))
                previous = Visit.search_count(domain)
                rec.delivery_sequence = previous + 1
            else:
                rec.delivery_sequence = 0
            ordered = rec.delivery_total_ordered_qty or rec.delivery_order_qty or 0.0
            rec.delivery_completion_percent = (rec.delivery_total_delivered_qty / ordered * 100.0) if ordered else 0.0

    @api.onchange('delivery_source_sale_order_id')
    def _onchange_delivery_source_sale_order_id(self):
        for rec in self:
            if rec.delivery_source_sale_order_id:
                rec._prepare_delivery_lines_from_source_order(onchange=True)

    def _prepare_delivery_lines_from_source_order(self, onchange=False):
        for rec in self:
            order = rec.delivery_source_sale_order_id
            if not order:
                if onchange:
                    rec.delivery_line_ids = [(5, 0, 0)]
                continue
            commands = [(5, 0, 0)]
            seq = 10
            for sol in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
                existing_helper = self.env['sales.route.visit.delivery.line'].new({
                    'visit_id': rec.id or False,
                    'sale_order_line_id': sol.id,
                    'product_id': sol.product_id.id,
                    'ordered_qty': sol.product_uom_qty,
                })
                already = existing_helper._get_already_delivered_qty() if rec.id else 0.0
                remaining = max((sol.product_uom_qty or 0.0) - already, 0.0)
                if remaining <= 0:
                    continue
                commands.append((0, 0, {
                    'sequence': seq,
                    'sale_order_line_id': sol.id,
                    'product_id': sol.product_id.id,
                    'product_uom_id': sol.product_uom.id,
                    'ordered_qty': sol.product_uom_qty,
                    'deliver_now_qty': remaining,
                }))
                seq += 10
            rec.delivery_line_ids = commands
        return True

    def action_load_delivery_lines(self):
        for rec in self:
            if not rec.delivery_source_sale_order_id:
                rec._compute_delivery_source_order()
            if not rec.delivery_source_sale_order_id:
                raise UserError(_('Select a Source Sales Order before loading delivery lines.'))
            rec._prepare_delivery_lines_from_source_order(onchange=False)
            rec.message_post(body=_('Delivery lines loaded from %s.') % rec.delivery_source_order_number)
        return True

    def _validate_delivery_confirmation(self):
        for rec in self:
            if rec.visit_purpose_category != 'delivery' and rec.visit_purpose != 'delivery':
                raise UserError(_('This action is only available for delivery visits.'))
            if not rec.delivery_source_sale_order_id:
                raise UserError(_('Select the Source Sales Order before confirming delivery.'))
            if not rec.delivery_line_ids:
                rec.action_load_delivery_lines()
            if not any(line.deliver_now_qty > 0 for line in rec.delivery_line_ids):
                raise UserError(_('Enter at least one Deliver Now quantity.'))
            rec.delivery_line_ids._validate_before_confirm()
            if not rec.check_in or not rec.checkin_latitude or not rec.checkin_longitude:
                raise UserError(_('GPS check-in is required before confirming a delivery.'))
        return True

    def action_mark_delivery_done(self):
        for rec in self:
            rec._validate_delivery_confirmation()
            for line in rec.delivery_line_ids:
                line.delivered_qty = line.deliver_now_qty
            remaining_after = 0.0
            for line in rec.delivery_line_ids:
                remaining_after += max((line.remaining_qty or 0.0) - (line.deliver_now_qty or 0.0), 0.0)
            rec.delivery_status = 'delivered' if remaining_after <= 0 else 'partial'
            rec.message_post(body=_('Delivery %s recorded against Source Sales Order %s. Delivered Qty: %.2f. Remaining Qty: %.2f.') % (
                dict(rec._fields['delivery_status'].selection).get(rec.delivery_status),
                rec.delivery_source_order_number or _('Not found'),
                rec.delivery_total_deliver_now_qty,
                remaining_after,
            ))
        return True

    def action_mark_delivery_failed(self):
        for rec in self:
            rec.delivery_status = 'failed'
            rec.message_post(body=_('Delivery marked as failed.'))
        return True

    @api.model
    def _default_visit_purpose_id(self):
        purpose = self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False)
        return purpose.id if purpose else False

    @api.onchange('visit_purpose_id')
    def _onchange_visit_purpose_id(self):
        for visit in self:
            if visit.visit_purpose_id:
                visit.visit_purpose = visit.visit_purpose_id.category or 'other'

    @api.onchange('visit_purpose')
    def _onchange_visit_purpose(self):
        for visit in self:
            if visit.visit_purpose and not visit.visit_purpose_id:
                purpose = self.env['sales.route.visit.purpose'].search([('category', '=', visit.visit_purpose)], limit=1)
                visit.visit_purpose_id = purpose

    @api.model_create_multi
    def create(self, vals_list):
        self.env['sales.route.license'].check_access_or_raise()
        purpose_model = self.env['sales.route.visit.purpose']
        for vals in vals_list:
            purpose_id = vals.get('visit_purpose_id')
            if purpose_id:
                purpose = purpose_model.browse(purpose_id)
                vals['visit_purpose'] = purpose.category or vals.get('visit_purpose') or 'other'
            elif vals.get('visit_purpose'):
                purpose = purpose_model.search([('category', '=', vals.get('visit_purpose'))], limit=1)
                if purpose:
                    vals['visit_purpose_id'] = purpose.id
            else:
                purpose = self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False)
                if purpose:
                    vals['visit_purpose_id'] = purpose.id
                    vals['visit_purpose'] = purpose.category
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('visit_purpose_id'):
            purpose = self.env['sales.route.visit.purpose'].browse(vals['visit_purpose_id'])
            vals = dict(vals, visit_purpose=purpose.category or 'other')
        return super().write(vals)

    @api.depends('partner_id', 'check_in')
    def _compute_name(self):
        for visit in self:
            visit.name = '%s - %s' % (visit.partner_id.display_name or 'Visit', visit.check_in or '')

    @api.depends(
        'plan_line_id',
        'plan_line_id.sale_order_ids',
        'plan_line_id.sale_order_ids.name',
        'plan_line_id.sale_order_ids.amount_total',
        'plan_line_id.sale_order_ids.order_line.product_id',
        'plan_line_id.sale_order_ids.order_line.product_uom_qty',
        'plan_line_id.sale_order_ids.order_line.price_total',
    )
    def _compute_visit_orders(self):
        for visit in self:
            line = visit.plan_line_id
            orders = line.sale_order_ids.sorted('id') if line else self.env['sale.order']
            # Start from each Sales Order and verify POS settlement there. This
            # mirrors the user workflow: Sales Order -> POS > Quotations/Orders
            # -> Transfer/settle to POS -> POS receipt.
            pos_orders = self.env['pos.order']
            for order in orders:
                if hasattr(order, '_fsrp_find_pos_orders_from_sale_order'):
                    pos_orders |= order._fsrp_find_pos_orders_from_sale_order()
            # Keep older/fallback route-context detection for databases that pass
            # route_plan_line_id directly to pos.order.
            pos_orders |= visit._find_pos_orders_for_sale_orders(orders, line=line) if orders or line else self.env['pos.order']

            visit.sale_order_tag_ids = orders
            visit.sale_order_numbers = ', '.join(orders.mapped('name'))
            visit.sale_order_total_amount = sum(orders.mapped('amount_total'))

            visit.pos_order_ids = pos_orders.sorted('id')
            visit.pos_order_receipt_numbers = ', '.join([
                po.pos_reference or po.name or '' for po in visit.pos_order_ids if po.pos_reference or po.name
            ])
            visit.pos_order_total_amount = sum(visit.pos_order_ids.mapped('amount_total'))
            visit.pos_order_paid_amount = visit._fsrp_sum_pos_paid_amount(visit.pos_order_ids)
            visit.pos_order_payment_amount = visit.pos_order_paid_amount
            visit.pos_order_due_amount = max((visit.pos_order_total_amount or 0.0) - (visit.pos_order_paid_amount or 0.0), 0.0)
            visit.pos_settlement_status = 'settled' if visit._all_sale_orders_processed_in_pos(orders, visit.pos_order_ids) else 'not_settled'

            category_lines, qty_lines = visit._fsrp_get_sale_order_pos_category_summary(orders)
            visit.sale_order_product_names = '\n'.join(category_lines)
            visit.sale_order_product_qtys = '\n'.join(qty_lines)

    def _fsrp_find_phantom_bom_for_product(self, product):
        """Return the phantom/kit BOM for a product, if MRP is installed.

        Kept defensive so the route module does not require the MRP app.
        """
        if not product or 'mrp.bom' not in self.env:
            return False
        Bom = self.env['mrp.bom'].sudo()
        domain = [
            ('type', '=', 'phantom'),
            '|',
            ('product_id', '=', product.id),
            '&', ('product_id', '=', False), ('product_tmpl_id', '=', product.product_tmpl_id.id),
        ]
        return Bom.search(domain, limit=1)

    def _fsrp_find_kit_parent_for_component(self, product, order=False):
        """Return a kit product that contains this component, if detectable.

        This handles cases where the order/report has exploded kit component
        products. In that case, the Route Visits list should show the kit name
        instead of the underlying component name.
        """
        if not product or 'mrp.bom.line' not in self.env:
            return False, False
        BomLine = self.env['mrp.bom.line'].sudo()
        domain = [
            ('product_id', '=', product.id),
            ('bom_id.type', '=', 'phantom'),
        ]
        if order and order.company_id:
            domain = ['|', ('bom_id.company_id', '=', False), ('bom_id.company_id', '=', order.company_id.id)] + domain
        bom_line = BomLine.search(domain, limit=1)
        if not bom_line:
            return False, False
        bom = bom_line.bom_id
        kit_product = bom.product_id or bom.product_tmpl_id.product_variant_id
        return kit_product, bom_line

    def _fsrp_get_product_pos_category_name(self, product):
        """Return the POS product category name for a product.

        Uses the POS category configured on the product template when the
        Point of Sale app is installed. Falls back to product category so the
        report remains usable even if POS category is empty.
        """
        if not product:
            return _('Uncategorized')
        tmpl = product.product_tmpl_id
        pos_category = False
        if 'pos_categ_id' in tmpl._fields:
            pos_category = tmpl.pos_categ_id
        elif 'pos_categ_id' in product._fields:
            pos_category = product.pos_categ_id
        if pos_category:
            return pos_category.display_name or pos_category.name
        if product.categ_id:
            return product.categ_id.display_name or product.categ_id.name
        return _('Uncategorized')

    def _fsrp_get_sale_order_pos_category_summary(self, orders):
        """Build POS product category and quantity columns for Route Visits.

        The Route Visits list should not display individual product/order-line
        names. It groups sales order lines by their POS product category and
        totals quantities per category. If a kit is detected, the category is
        taken from the kit/parent product, not from its component products.
        """
        category_lines = []
        qty_lines = []
        for order in orders:
            summary = {}
            sequence = []
            lines = order.order_line.filtered(lambda l: not l.display_type and l.product_id)

            parent_kit_boms = {}
            for sol in lines:
                bom = self._fsrp_find_phantom_bom_for_product(sol.product_id)
                if bom:
                    parent_kit_boms[bom.id] = sol.product_id

            for sol in lines:
                product = sol.product_id
                qty = sol.product_uom_qty

                bom = self._fsrp_find_phantom_bom_for_product(product)
                if bom:
                    effective_product = product
                else:
                    kit_product, bom_line = self._fsrp_find_kit_parent_for_component(product, order=order)
                    if kit_product and bom_line:
                        if bom_line.bom_id.id in parent_kit_boms:
                            continue
                        effective_product = kit_product
                        if bom_line.product_qty:
                            qty = qty / bom_line.product_qty
                    else:
                        effective_product = product

                category_name = self._fsrp_get_product_pos_category_name(effective_product)
                key = category_name
                if key not in summary:
                    summary[key] = 0.0
                    sequence.append(key)
                summary[key] += qty

            for category_name in sequence:
                qty = summary[category_name]
                category_lines.append('%s: %s' % (order.name, category_name))
                qty_lines.append(str(qty))
        return category_lines, qty_lines


    def _fsrp_sum_pos_paid_amount(self, pos_orders):
        """Return actual amount paid on linked POS receipts.

        Standard Odoo POS stores paid total in amount_paid. Some custom POS
        deployments only expose payment_ids, so this method defensively falls
        back to summing payment amounts when amount_paid is unavailable.
        """
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
                # If the POS order is processed but no payment field is exposed,
                # assume the visible receipt total was paid.
                total += po.amount_total or 0.0
        return total

    def _find_pos_orders_for_sale_orders(self, sale_orders, line=False):
        """Return settled POS orders created from the visit's Sales Orders.

        The source of truth is the Sales Order lookup helper, because it mirrors
        the Odoo POS Quotations/Orders settlement flow. Route-plan context is
        used only as an additional fallback.
        """
        PosOrder = self.env['pos.order'].sudo()
        pos_orders = PosOrder.browse()
        sale_orders = sale_orders.exists()

        for sale_order in sale_orders:
            if hasattr(sale_order, '_fsrp_find_pos_orders_from_sale_order'):
                try:
                    pos_orders |= sale_order._fsrp_find_pos_orders_from_sale_order()
                except Exception:
                    pass

        if line and 'route_plan_line_id' in PosOrder._fields:
            try:
                extra = PosOrder.search([('route_plan_line_id', '=', line.id)])
                if 'state' in PosOrder._fields:
                    # Include draft/new POS orders too so supervisors can see
                    # orders transferred to POS before payment is completed.
                    visible_states = ['draft', 'new', 'quotation', 'open', 'partial', 'paid', 'done', 'invoiced']
                    extra = extra.filtered(lambda po: not po.state or po.state in visible_states)
                pos_orders |= extra
            except Exception:
                pass

        return pos_orders.sorted('id')

    def _pos_order_links_sale_order(self, pos_order, sale_order):
        if hasattr(sale_order, '_fsrp_find_pos_orders_from_sale_order'):
            try:
                return pos_order in sale_order._fsrp_find_pos_orders_from_sale_order()
            except Exception:
                pass
        if 'sale_order_id' in pos_order._fields and pos_order.sale_order_id == sale_order:
            return True
        if 'sale_order_ids' in pos_order._fields and sale_order in pos_order.sale_order_ids:
            return True
        if 'sale_order_origin_id' in pos_order._fields and pos_order.sale_order_origin_id == sale_order:
            return True
        if 'route_plan_line_id' in pos_order._fields and sale_order.route_plan_line_id and pos_order.route_plan_line_id == sale_order.route_plan_line_id:
            return True
        if 'origin' in pos_order._fields and pos_order.origin == sale_order.name:
            return True
        if 'note' in pos_order._fields and pos_order.note and sale_order.name and sale_order.name in pos_order.note:
            return True
        return False

    def _all_sale_orders_processed_in_pos(self, sale_orders, pos_orders):
        sale_orders = sale_orders.exists()
        if not sale_orders or not pos_orders:
            return False
        settled_states = ['paid', 'done', 'invoiced']
        for sale_order in sale_orders:
            linked = pos_orders.filtered(lambda po: self._pos_order_links_sale_order(po, sale_order))
            if not linked:
                return False
            if 'state' in linked._fields and not any((not po.state or po.state in settled_states) for po in linked):
                return False
        return True

    def action_refresh_order_pos_cache(self):
        """Manually refresh stored Sale/POS summary columns for selected visits.

        Route Visits list values are stored for faster loading. Use this action
        when historical POS orders were created before this version was installed
        or after custom POS imports.
        """
        self._compute_visit_orders()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Route Visit Summary Refreshed'),
                'message': _('Sales and POS summary columns have been refreshed.'),
                'type': 'success',
                'sticky': False,
            }
        }

    @api.model
    def refresh_all_route_visit_order_pos_cache(self, limit=500):
        visits = self.search([], limit=limit, order='id desc')
        visits._compute_visit_orders()
        return True

    @api.depends('check_in', 'check_out')
    def _compute_duration(self):
        for visit in self:
            if visit.check_in and visit.check_out:
                delta = visit.check_out - visit.check_in
                visit.duration_minutes = delta.total_seconds() / 60.0
            else:
                visit.duration_minutes = 0.0
            visit.suspicious_visit = bool(visit.duration_minutes and visit.duration_minutes < 2)

    @api.depends('checkin_latitude', 'checkin_longitude', 'partner_id.customer_latitude', 'partner_id.customer_longitude', 'allowed_radius_m')
    def _compute_distance(self):
        for visit in self:
            coords = visit.partner_id.get_route_map_coordinates() if visit.partner_id else {'latitude': 0.0, 'longitude': 0.0, 'has_location': False}
            client_lat = coords.get('latitude') or 0.0
            client_lon = coords.get('longitude') or 0.0
            if all([visit.checkin_latitude, visit.checkin_longitude, client_lat, client_lon]):
                visit.distance_from_client_m = visit._haversine_m(
                    visit.checkin_latitude, visit.checkin_longitude,
                    client_lat, client_lon
                )
                visit.within_allowed_radius = visit.distance_from_client_m <= visit.allowed_radius_m
            else:
                visit.distance_from_client_m = 0.0
                visit.within_allowed_radius = False

    def _haversine_m(self, lat1, lon1, lat2, lon2):
        radius = 6371000.0
        dlat = radians(lat2 - lat1)
        dlon = radians(lon2 - lon1)
        a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return radius * c

    def _resolve_place(self, latitude, longitude):
        """Reverse-geocode GPS coordinates into readable place details.

        Uses OpenStreetMap Nominatim by default. You may override by setting:
        - field_sales_route_plan.geocoder_provider = none|nominatim
        - field_sales_route_plan.nominatim_user_agent = your-app-or-domain

        Returns a dict so check-in/check-out can store both short place and full
        address. If internet/API access is unavailable, it safely falls back to
        the raw coordinates.
        """
        try:
            lat = float(latitude or 0.0)
            lon = float(longitude or 0.0)
        except (TypeError, ValueError):
            lat = lon = 0.0
        if not lat or not lon:
            return {
                'place': False,
                'address': False,
                'area': False,
                'raw': False,
            }

        coords = '%.7f, %.7f' % (lat, lon)
        provider = (self.env['ir.config_parameter'].sudo().get_param(
            'field_sales_route_plan.geocoder_provider', 'nominatim'
        ) or 'nominatim').lower()
        if provider in ('none', 'disabled', 'false'):
            return {'place': coords, 'address': coords, 'area': False, 'raw': False}

        google_key = self.env['ir.config_parameter'].sudo().get_param('field_sales_route_plan.google_geocode_api_key')
        if provider == 'google' and google_key:
            try:
                response = requests.get(
                    'https://maps.googleapis.com/maps/api/geocode/json',
                    params={'latlng': '%s,%s' % (lat, lon), 'key': google_key},
                    timeout=8,
                )
                response.raise_for_status()
                data = response.json() or {}
                results = data.get('results') or []
                first = results[0] if results else {}
                address = first.get('formatted_address') or coords
                comps = first.get('address_components') or []
                area = False
                for comp in comps:
                    types = comp.get('types') or []
                    if any(t in types for t in ['sublocality', 'locality', 'administrative_area_level_2', 'administrative_area_level_1']):
                        area = comp.get('long_name')
                        break
                return {'place': area or address, 'address': address, 'area': area, 'raw': json.dumps(data, ensure_ascii=False)}
            except Exception as error:
                _logger.warning('Google reverse-geocode failed %.7f, %.7f: %s', lat, lon, error)
                # Continue to Nominatim fallback below.

        user_agent = self.env['ir.config_parameter'].sudo().get_param(
            'field_sales_route_plan.nominatim_user_agent',
            'field_sales_route_plan_odoo16'
        )
        try:
            response = requests.get(
                'https://nominatim.openstreetmap.org/reverse',
                params={
                    'format': 'jsonv2',
                    'lat': lat,
                    'lon': lon,
                    'addressdetails': 1,
                    'zoom': 18,
                },
                headers={'User-Agent': user_agent},
                timeout=6,
            )
            response.raise_for_status()
            data = response.json() or {}
            address = data.get('display_name') or coords
            parts = data.get('address') or {}
            area = (
                parts.get('suburb') or parts.get('neighbourhood') or parts.get('village') or
                parts.get('town') or parts.get('city') or parts.get('county') or parts.get('state')
            )
            place = data.get('name') or area or address
            return {
                'place': place,
                'address': address,
                'area': area,
                'raw': json.dumps(data, ensure_ascii=False),
            }
        except Exception as error:
            _logger.warning('Could not reverse-geocode GPS %.7f, %.7f: %s', lat, lon, error)
            return {
                'place': coords,
                'address': coords,
                'area': False,
                'raw': json.dumps({'error': str(error), 'latitude': lat, 'longitude': lon}),
            }


    def _compute_opportunity_count(self):
        for visit in self:
            visit.opportunity_count = len(visit.opportunity_ids)

    @api.depends('program_issued', 'program_custom_count', 'program_line_ids.count', 'program_line_ids.response', 'program_line_ids.program_id')
    def _compute_program_count(self):
        for visit in self:
            if visit.program_line_ids:
                total = 0
                for line in visit.program_line_ids.filtered(lambda l: l.program_id):
                    total += 1 if line.response == 'yes' else int(line.count or 0)
                visit.program_count = total
            elif visit.program_issued == 'yes':
                visit.program_count = 1
            else:
                visit.program_count = 0

    @api.depends('program_line_ids.program_id', 'program_line_ids.count', 'program_line_ids.response', 'program_ids', 'program_issued')
    def _compute_program_line_summary(self):
        for visit in self:
            parts = []
            for line in visit.program_line_ids.filtered(lambda l: l.program_id):
                count = 1 if line.response == 'yes' else int(line.count or 0)
                parts.append('%s: %s' % (line.program_id.display_name, count))
            if not parts and visit.program_ids:
                parts = ['%s: %s' % (program.display_name, 1 if visit.program_issued == 'yes' else 0) for program in visit.program_ids]
            visit.program_line_summary = ', '.join(parts)

    def _get_active_programs_for_columns(self):
        return self.env['sales.route.marketing.program'].search([('active', '=', True)], order='name, id', limit=20)

    @api.depends('program_line_ids.program_id', 'program_line_ids.count', 'program_line_ids.response')
    def _compute_program_count_columns(self):
        programs = self._get_active_programs_for_columns()
        program_ids = programs.ids
        for visit in self:
            counts = {}
            for line in visit.program_line_ids.filtered(lambda l: l.program_id):
                counts[line.program_id.id] = counts.get(line.program_id.id, 0) + (1 if line.response == 'yes' else int(line.count or 0))
            for idx in range(1, 21):
                field_name = 'program_count_col_%02d' % idx
                program_id = program_ids[idx - 1] if idx <= len(program_ids) else False
                visit[field_name] = counts.get(program_id, 0) if program_id else 0

    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        res = super().get_view(view_id=view_id, view_type=view_type, **options)
        if view_type in ('tree', 'list'):
            try:
                from lxml import etree
                doc = etree.fromstring(res['arch'])
                programs = self._get_active_programs_for_columns()
                # Remove existing dynamic program columns from inherited/cached arch.
                for node in doc.xpath("//field[starts-with(@name, 'program_count_col_')]"):
                    parent = node.getparent()
                    if parent is not None:
                        parent.remove(node)
                anchor = doc.xpath("//field[@name='visit_purpose_id']")
                parent = anchor[0].getparent() if anchor else doc
                insert_index = parent.index(anchor[0]) + 1 if anchor else len(parent)
                for idx, program in enumerate(programs, start=1):
                    node = etree.Element('field', name='program_count_col_%02d' % idx, string=program.display_name)
                    parent.insert(insert_index, node)
                    insert_index += 1
                res['arch'] = etree.tostring(doc, encoding='unicode')
            except Exception as exc:
                _logger.warning('Could not build dynamic program columns on route visit tree: %s', exc)
        return res


    def action_open_marketing_quick_popup(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Marketing Visit Quick Capture'),
            'res_model': 'sales.route.marketing.quick.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_visit_id': self.id},
        }

    def action_open_visit_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client Visit'),
            'res_model': 'sales.route.visit',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'default_plan_line_id': self.plan_line_id.id},
        }

    def _prepare_marketing_history_vals(self, opportunity=False):
        self.ensure_one()
        title = '%s - %s' % (self.partner_id.display_name, dict(self._fields['visit_purpose'].selection).get(self.visit_purpose))
        return {
            'name': title,
            'partner_id': self.partner_id.id,
            'visit_id': self.id,
            'plan_id': self.plan_id.id,
            'route_id': self.route_id.id,
            'user_id': self.user_id.id,
            'visit_date': self.check_in or fields.Datetime.now(),
            'program_issued': self.program_issued,
            'program_count': self.program_count,
            'program_custom_count': self.program_custom_count,
            'program_id': self.program_id.id,
            'program_ids': [(6, 0, self.program_ids.ids)],
            'contact_person_name': self.contact_person_name,
            'contact_person_phone': self.contact_person_phone,
            'contact_person_email': self.contact_person_email,
            'opportunity_id': opportunity.id if opportunity else False,
            'activity_summary': self.followup_summary,
            'activity_date_deadline': self.followup_date_deadline,
            'notes': '\n\n'.join([x for x in [self.marketing_activities_done, self.marketing_notes or self.note] if x]),
        }

    def action_save_marketing_history(self):
        for visit in self:
            if not visit.partner_id:
                raise UserError(_('Please select a client first.'))
            self.env['sales.route.marketing.history'].create(visit._prepare_marketing_history_vals())
        return True

    def action_create_partner_contact(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a client first.'))
        if not self.contact_person_name:
            raise UserError(_('Please enter the contact person name.'))
        existing = self.env['res.partner'].search([
            ('parent_id', '=', self.partner_id.id),
            ('name', '=', self.contact_person_name),
        ], limit=1)
        vals = {
            'name': self.contact_person_name,
            'parent_id': self.partner_id.id,
            'type': 'contact',
            'phone': self.contact_person_phone,
            'mobile': self.contact_person_phone,
            'email': self.contact_person_email,
            'customer_rank': 0,
        }
        if existing:
            existing.write({k: v for k, v in vals.items() if v})
            contact = existing
        else:
            contact = self.env['res.partner'].create(vals)
        self.message_post(body=_('Contact person added/updated: %s') % contact.display_name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Client Contact'),
            'res_model': 'res.partner',
            'view_mode': 'form',
            'res_id': contact.id,
            'target': 'current',
        }

    def action_create_followup_activity(self):
        self.ensure_one()
        if not self.followup_activity_type_id:
            raise UserError(_('Please select a follow-up activity type.'))
        if not self.followup_date_deadline:
            raise UserError(_('Please select a follow-up due date.'))
        self.partner_id.activity_schedule(
            activity_type_id=self.followup_activity_type_id.id,
            date_deadline=self.followup_date_deadline,
            summary=self.followup_summary or _('Route visit follow-up'),
            note=self.followup_note or self.marketing_notes or self.note or '',
            user_id=self.user_id.id,
        )
        self.env['sales.route.marketing.history'].create(self._prepare_marketing_history_vals())
        self.message_post(body=_('Follow-up activity created on client: %s') % (self.followup_summary or _('Route visit follow-up')))
        return True

    def action_create_opportunity(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a client first.'))
        lead = self.env['crm.lead'].create({
            'name': self.followup_summary or _('Opportunity - %s') % self.partner_id.display_name,
            'partner_id': self.partner_id.id,
            'contact_name': self.contact_person_name,
            'phone': self.contact_person_phone or self.partner_id.phone,
            'email_from': self.contact_person_email or self.partner_id.email,
            'user_id': self.user_id.id,
            'team_id': self.route_id.team_id.id if self.route_id.team_id else False,
            'type': 'opportunity',
            'description': self.marketing_notes or self.note,
            'route_visit_id': self.id,
            'route_id': self.route_id.id,
            'route_plan_id': self.plan_id.id,
        })
        self.env['sales.route.marketing.history'].create(self._prepare_marketing_history_vals(opportunity=lead))
        self.message_post(body=_('Opportunity created: %s') % lead.display_name)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Opportunity'),
            'res_model': 'crm.lead',
            'view_mode': 'form',
            'res_id': lead.id,
            'target': 'current',
        }

    def action_view_opportunities(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Opportunities'),
            'res_model': 'crm.lead',
            'view_mode': 'tree,form',
            'domain': [('route_visit_id', '=', self.id)],
            'context': {'default_partner_id': self.partner_id.id, 'default_route_visit_id': self.id},
        }

    def action_check_in(self, latitude=False, longitude=False):
        for visit in self:
            if visit.state != 'draft':
                raise UserError(_('Only draft visits can be checked in.'))
            lat = latitude or self.env.context.get('gps_latitude')
            lon = longitude or self.env.context.get('gps_longitude')
            if lat is None or lon is None or lat is False or lon is False:
                raise UserError(_('GPS coordinates are required. Please use the GPS Check In button and allow location access on the device.'))
            place = visit._resolve_place(lat, lon)
            visit.write({
                'state': 'checked_in',
                'check_in': fields.Datetime.now(),
                'checkin_latitude': lat,
                'checkin_longitude': lon,
                'checkin_place': place.get('place'),
                'checkin_address': place.get('address'),
                'checkin_area': place.get('area'),
                'checkin_geocode_json': place.get('raw'),
            })
            if visit.plan_line_id:
                visit.plan_line_id.status = 'checked_in'

    def action_check_out(self, latitude=False, longitude=False):
        for visit in self:
            if visit.state != 'checked_in':
                raise UserError(_('Only checked-in visits can be checked out.'))
            lat = latitude or self.env.context.get('gps_latitude')
            lon = longitude or self.env.context.get('gps_longitude')
            if lat is None or lon is None or lat is False or lon is False:
                raise UserError(_('GPS coordinates are required. Please use the GPS Check Out button and allow location access on the device.'))
            place = visit._resolve_place(lat, lon)
            visit.write({
                'state': 'checked_out',
                'check_out': fields.Datetime.now(),
                'checkout_latitude': lat,
                'checkout_longitude': lon,
                'checkout_place': place.get('place'),
                'checkout_address': place.get('address'),
                'checkout_area': place.get('area'),
                'checkout_geocode_json': place.get('raw'),
            })
            if visit.plan_line_id and visit.plan_line_id.status == 'checked_in':
                visit.plan_line_id.status = 'checked_out'

    def action_open_gps_checkin(self):
        self.ensure_one()
        # Primary path: visit_inline_gps.js intercepts this button and captures GPS on the
        # same form. Fallback path: if the DOM interception is not available, open the
        # lightweight GPS client action which captures GPS and returns to this visit.
        return {
            'type': 'ir.actions.client',
            'tag': 'field_sales_route_plan.gps_capture',
            'target': 'current',
            'context': {
                'visit_id': self.id,
                'gps_mode': 'checkin',
                'auto_back_to_visit': True,
            },
        }

    def action_open_gps_checkout(self):
        self.ensure_one()
        # Primary path: visit_inline_gps.js intercepts this button and captures GPS on the
        # same form. Fallback path: if the DOM interception is not available, open the
        # lightweight GPS client action which captures GPS and returns to this visit.
        return {
            'type': 'ir.actions.client',
            'tag': 'field_sales_route_plan.gps_capture',
            'target': 'current',
            'context': {
                'visit_id': self.id,
                'gps_mode': 'checkout',
                'auto_back_to_visit': True,
            },
        }


    def action_set_as_client_location(self):
        for visit in self:
            if not visit.partner_id:
                raise UserError(_('Please select a client first.'))
            if not (visit.checkin_latitude and visit.checkin_longitude):
                raise UserError(_('Please capture GPS check-in coordinates first.'))
            vals = {
                'customer_latitude': visit.checkin_latitude,
                'customer_longitude': visit.checkin_longitude,
            }
            # Also update Odoo's native geolocation fields when the database has them.
            if 'partner_latitude' in visit.partner_id._fields and 'partner_longitude' in visit.partner_id._fields:
                vals.update({
                    'partner_latitude': visit.checkin_latitude,
                    'partner_longitude': visit.checkin_longitude,
                })
            visit.partner_id.sudo().write(vals)
        return True


    @api.depends('partner_id')
    def _compute_client_intelligence(self):
        SaleOrder = self.env['sale.order'].sudo()
        Move = self.env['account.move'].sudo() if 'account.move' in self.env.registry else False
        for visit in self:
            partner = visit.partner_id.commercial_partner_id or visit.partner_id
            visit.client_last_purchase_date = False
            visit.client_total_spend = 0.0
            visit.client_outstanding_amount = 0.0
            visit.client_favorite_products = False
            visit.next_best_action = False
            visit.smart_recommendation_text = False
            if not partner:
                continue
            orders = SaleOrder.search([('partner_id', 'child_of', partner.id), ('state', 'in', ['sale', 'done'])], order='date_order desc', limit=20)
            if orders:
                visit.client_last_purchase_date = fields.Date.to_date(orders[0].date_order)
                visit.client_total_spend = sum(orders.mapped('amount_total'))
                product_counts = {}
                for line in orders.mapped('order_line'):
                    if line.product_id and not getattr(line, 'display_type', False):
                        product_counts[line.product_id.display_name] = product_counts.get(line.product_id.display_name, 0.0) + (line.product_uom_qty or 0.0)
                top = sorted(product_counts.items(), key=lambda item: item[1], reverse=True)[:3]
                visit.client_favorite_products = ', '.join([name for name, qty in top])
                if top:
                    visit.smart_recommendation_text = _('Suggested reorder: %s') % ', '.join(['%s (%.0f)' % (name, qty) for name, qty in top])
            if Move:
                invoices = Move.search([('partner_id', 'child_of', partner.id), ('move_type', 'in', ['out_invoice', 'out_refund']), ('state', '=', 'posted')])
                visit.client_outstanding_amount = sum(invoices.mapped('amount_residual'))
            if visit.client_outstanding_amount:
                visit.next_best_action = _('Collect outstanding balance before new credit sale.')
            elif visit.client_last_purchase_date:
                days = (fields.Date.context_today(visit) - visit.client_last_purchase_date).days
                if days >= 14:
                    visit.next_best_action = _('Client has not bought for %s days. Suggest reorder/follow-up.') % days
                else:
                    visit.next_best_action = _('Review frequent products and grow basket size.')
            else:
                visit.next_best_action = _('New/no purchase history. Introduce key products and capture contact details.')
                visit.smart_recommendation_text = _('Introduce fast-moving products, capture buyer contact details, and schedule a follow-up reminder.')

    @api.depends('partner_id')
    def _compute_client_history_timeline(self):
        Visit = self.env['sales.route.visit'].sudo()
        SaleOrder = self.env['sale.order'].sudo()
        for visit in self:
            partner = visit.partner_id.commercial_partner_id or visit.partner_id
            if not partner:
                visit.client_visit_history_timeline = False
                continue
            lines = []
            # When the visit form is still unsaved, Odoo uses a temporary NewId.
            # Never pass that NewId into a SQL domain, otherwise PostgreSQL tries
            # to compare an integer id with a string like 'NewId_0x...' and crashes.
            domain = [('partner_id', 'child_of', partner.id)]
            if isinstance(visit.id, int):
                domain.append(('id', '!=', visit.id))
            prev_visits = Visit.search(domain, order='check_in desc', limit=5)
            for v in prev_visits:
                lines.append('%s | Visit | %s | %s' % (v.check_in or '', v.user_id.name or '', v.visit_purpose_id.name or v.visit_purpose or ''))
            orders = SaleOrder.search([('partner_id', 'child_of', partner.id)], order='date_order desc', limit=5)
            for so in orders:
                lines.append('%s | Order | %s | %.2f' % (so.date_order or '', so.name or '', so.amount_total or 0.0))
            visit.client_visit_history_timeline = '\n'.join(lines[:12]) or _('No previous history found for this client.')

    @api.depends('merchandising_audit_ids')
    def _compute_merchandising_audit_count(self):
        for visit in self:
            visit.merchandising_audit_count = len(visit.merchandising_audit_ids)

    def action_create_smart_reminder(self):
        self.ensure_one()
        reminder = self.env['sales.route.smart.reminder'].create_from_visit(self, reminder_type='revisit', days=7, note=self.next_best_action)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Smart Reminder'),
            'res_model': 'sales.route.smart.reminder',
            'res_id': reminder.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_merchandising_audits(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Merchandising Audits'),
            'res_model': 'sales.route.merchandising.audit',
            'view_mode': 'tree,form',
            'domain': [('visit_id', '=', self.id)],
            'context': {'default_visit_id': self.id},
        }

    def _get_partner_navigation_coordinates(self):
        self.ensure_one()
        partner = self.partner_id
        lat = lon = 0.0
        if partner:
            lat = getattr(partner, 'partner_latitude', 0.0) or getattr(partner, 'customer_latitude', 0.0) or 0.0
            lon = getattr(partner, 'partner_longitude', 0.0) or getattr(partner, 'customer_longitude', 0.0) or 0.0
        return lat, lon

    def action_navigate_google_maps(self):
        self.ensure_one()
        lat, lon = self._get_partner_navigation_coordinates()
        if lat and lon:
            url = 'https://www.google.com/maps/dir/?api=1&destination=%s,%s' % (lat, lon)
        elif self.partner_id:
            partner = self.partner_id
            address_parts = [
                partner.street,
                partner.street2,
                partner.city,
                partner.state_id.name if partner.state_id else False,
                partner.country_id.name if partner.country_id else False,
            ]
            query = ', '.join([part for part in address_parts if part]) or partner.display_name
            url = 'https://www.google.com/maps/search/?api=1&query=%s' % quote(query)
        else:
            raise UserError(_('No client is selected for navigation.'))
        return {'type': 'ir.actions.act_url', 'url': url, 'target': 'new'}

    def action_next_client(self):
        self.ensure_one()
        if not self.plan_id or not self.plan_line_id:
            raise UserError(_('This visit is not linked to a daily route plan.'))
        next_line = self.plan_id.line_ids.filtered(lambda l: l.sequence > self.plan_line_id.sequence and l.status in ['pending', 'checked_in']).sorted('sequence')[:1]
        if not next_line:
            next_line = self.plan_id.line_ids.filtered(lambda l: l.status == 'pending').sorted('sequence')[:1]
        if not next_line:
            raise UserError(_('There is no pending next client on this route plan.'))
        return next_line.action_start_visit()

    def action_quick_reorder_last_purchase(self):
        self.ensure_one()
        if not self.partner_id:
            raise UserError(_('Please select a client first.'))
        last_order = self.env['sale.order'].sudo().search([
            ('partner_id', 'child_of', self.partner_id.commercial_partner_id.id or self.partner_id.id),
            ('state', 'in', ['sale', 'done']),
            ('order_line.product_id', '!=', False),
        ], order='date_order desc', limit=1)
        if not last_order:
            raise UserError(_('No previous confirmed sales order was found for this client.'))
        new_order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'route_id': self.route_id.id,
            'route_plan_id': self.plan_id.id,
            'route_plan_line_id': self.plan_line_id.id,
            'origin': _('Quick reorder from %s') % last_order.name,
        })
        for line in last_order.order_line.filtered(lambda l: l.product_id and not l.display_type):
            self.env['sale.order.line'].create({
                'order_id': new_order.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.product_uom_qty,
                'price_unit': line.price_unit,
                'name': line.name,
            })
        self.action_refresh_order_pos_cache()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Quick Reorder'),
            'res_model': 'sale.order',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'res_id': new_order.id,
            'target': 'current',
        }

    def action_create_sale_order(self):
        self.ensure_one()
        if not self.plan_line_id:
            raise UserError(_('This visit is not linked to a planned client visit.'))
        return self.plan_line_id.action_create_sale_order()

    def action_view_sale_orders(self):
        self.ensure_one()
        if not self.plan_line_id:
            raise UserError(_('This visit is not linked to a planned client visit.'))
        return self.plan_line_id.action_view_sale_orders()
