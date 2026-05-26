from odoo import api, fields, models, _
from odoo.exceptions import UserError


class RouteSaleTerminalWizard(models.TransientModel):
    _name = 'route.sale.terminal.wizard'
    _description = 'Route Sale POS Style Terminal'

    plan_line_id = fields.Many2one('sales.route.plan.line', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, readonly=True)
    route_id = fields.Many2one('sales.route', readonly=True)
    user_id = fields.Many2one('res.users', string='Salesperson', readonly=True)
    sale_order_id = fields.Many2one('sale.order', string='Sales Order', readonly=True)
    line_ids = fields.One2many('route.sale.terminal.line', 'wizard_id', string='Products')
    total_amount = fields.Monetary(compute='_compute_total_amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)

    @api.depends('line_ids.qty', 'line_ids.price_unit')
    def _compute_total_amount(self):
        for wizard in self:
            wizard.total_amount = sum(wizard.line_ids.mapped('subtotal'))


    @api.model
    def _get_pos_saleable_products(self):
        """Return products that can be sold and are enabled for Point of Sale.

        Odoo versions / localizations may expose POS categories on either
        product.product or product.template, and older custom databases may not
        have the POS fields until point_of_sale is installed. The manifest now
        depends on point_of_sale, but this defensive code keeps upgrades safer.
        """
        Product = self.env['product.product']
        domain = [('sale_ok', '=', True), ('active', '=', True)]
        if 'available_in_pos' in Product._fields:
            domain.append(('available_in_pos', '=', True))
        elif 'available_in_pos' in self.env['product.template']._fields:
            domain.append(('product_tmpl_id.available_in_pos', '=', True))
        return Product.search(domain, order='name')

    @api.model
    def _product_category_ids(self, product):
        """Return the default Odoo product categories for terminal filtering.

        This uses Product Categories (product.category / product.categ_id),
        not POS Product Categories (pos.category). It also includes parent
        categories so selecting a parent category shows products from its
        child categories.
        """
        category = product.categ_id if 'categ_id' in product._fields else product.product_tmpl_id.categ_id
        category_ids = []
        while category:
            category_ids.append(category.id)
            category = category.parent_id
        return category_ids

    @api.model
    def _sale_order_form_action(self, order):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sales Order'),
            'res_model': 'sale.order',
            'res_id': order.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {'create': False},
        }

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        plan_line = self.env['sales.route.plan.line'].browse(self.env.context.get('default_plan_line_id'))
        if plan_line:
            if not plan_line.partner_id:
                raise UserError(_('Please select a client before creating an order.'))
            res.update({
                'plan_line_id': plan_line.id,
                'partner_id': plan_line.partner_id.id,
                'route_id': plan_line.route_id.id,
                'user_id': plan_line.user_id.id,
                'sale_order_id': plan_line.sale_order_id.id,
                'currency_id': self.env.company.currency_id.id,
            })
        return res

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        Product = self.env['product.product']
        for wizard in records:
            products = self._get_pos_saleable_products()
            lines = []
            for product in products:
                price = product.lst_price
                try:
                    price = product.with_context(pricelist=wizard.partner_id.property_product_pricelist.id).price
                except Exception:
                    price = product.lst_price
                lines.append((0, 0, {
                    'product_id': product.id,
                    'default_code': product.default_code,
                    'price_unit': price,
                    'uom_id': product.uom_id.id,
                }))
            wizard.line_ids = lines
        return records



    @api.model
    def _prepare_cart_from_sale_order(self, order):
        cart = []
        for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
            cart.append({
                'product_id': line.product_id.id,
                'name': line.product_id.display_name,
                'qty': line.product_uom_qty,
                'price_unit': line.price_unit,
            })
        return cart

    @api.model
    def _format_recreatable_orders(self, orders):
        values = []
        for order in orders:
            values.append({
                'id': order.id,
                'name': order.name,
                'date_order': fields.Datetime.to_string(order.date_order) if order.date_order else '',
                'state': order.state,
                'amount_total': order.amount_total,
                'amount_display': '%s %.2f' % (order.currency_id.symbol or order.currency_id.name, order.amount_total),
                'partner_name': order.partner_id.display_name,
            })
        return values

    @api.model
    def _get_recreatable_orders(self, plan_line, limit=25):
        """Return previous orders for the current route client that can be re-opened
        in the route POS terminal without creating a new order number.
        """
        domain = [
            ('partner_id', '=', plan_line.partner_id.id),
            ('state', 'not in', ['cancel']),
        ]
        orders = self.env['sale.order'].sudo().search(domain, order='date_order desc, id desc', limit=limit)
        return self._format_recreatable_orders(orders)

    @api.model
    def search_recreatable_orders(self, plan_line_id=False, query='', limit=50, partner_id=False):
        domain = [('state', 'not in', ['cancel'])]
        if plan_line_id:
            plan_line = self.env['sales.route.plan.line'].browse(plan_line_id).exists()
            if not plan_line:
                raise UserError(_('Route plan line was not found.'))
            domain.append(('partner_id', '=', plan_line.partner_id.id))
        else:
            self._check_quick_sale_unrestricted()
            if partner_id:
                domain.append(('partner_id', '=', int(partner_id)))
            else:
                # Quick mode without a customer selected: search by order number across all clients.
                pass
        query = (query or '').strip()
        if query:
            domain += ['|', ('name', 'ilike', query), ('client_order_ref', 'ilike', query)]
        elif not partner_id and not plan_line_id:
            return []
        orders = self.env['sale.order'].sudo().search(domain, order='date_order desc, id desc', limit=limit)
        return self._format_recreatable_orders(orders)

    @api.model
    def _check_quick_sale_unrestricted(self):
        if not self.env.user.has_group('field_sales_route_plan.group_field_sales_quick_sale_unrestricted'):
            raise UserError(_('You are not allowed to use Quick Sales Order without a route plan. Please contact your system administrator.'))

    @api.model
    def search_quick_sale_customers(self, query='', limit=30):
        self._check_quick_sale_unrestricted()
        query = (query or '').strip()
        domain = [('customer_rank', '>', 0)]
        if query:
            domain += ['|', '|', ('name', 'ilike', query), ('phone', 'ilike', query), ('mobile', 'ilike', query)]
        partners = self.env['res.partner'].sudo().search(domain, order='name', limit=limit)
        values = []
        for partner in partners:
            route = partner.route_id if 'route_id' in partner._fields else self.env['sales.route']
            values.append({
                'id': partner.id,
                'name': partner.display_name,
                'route_id': route.id if route else False,
                'route_name': route.display_name if route else '',
                'phone': partner.phone or partner.mobile or '',
            })
        return values

    @api.model
    def get_quick_sale_customer_context(self, partner_id):
        self._check_quick_sale_unrestricted()
        partner = self.env['res.partner'].sudo().browse(int(partner_id or 0)).exists()
        if not partner:
            raise UserError(_('Please select a valid client.'))
        route = partner.route_id if 'route_id' in partner._fields else self.env['sales.route']
        return {
            'partner_id': partner.id,
            'partner_name': partner.display_name,
            'route_id': route.id if route else False,
            'route_name': route.display_name if route else '',
        }


    @api.model
    def search_quick_sale_salespersons(self, query='', limit=30):
        self._check_quick_sale_unrestricted()
        query = (query or '').strip()
        domain = [('share', '=', False), ('active', '=', True)]
        if query:
            domain += ['|', ('name', 'ilike', query), ('login', 'ilike', query)]
        users = self.env['res.users'].sudo().search(domain, order='name', limit=limit)
        return [{'id': user.id, 'name': user.name or user.login, 'login': user.login or ''} for user in users]

    @api.model
    def create_quick_sale_customer(self, name, phone='', route_id=False):
        self._check_quick_sale_unrestricted()
        name = (name or '').strip()
        phone = (phone or '').strip()
        if not name:
            raise UserError(_('Please enter the new client name.'))
        vals = {
            'name': name,
            'customer_rank': 1,
        }
        if phone:
            vals['phone'] = phone
        if route_id and 'route_id' in self.env['res.partner']._fields:
            vals['route_id'] = int(route_id)
        partner = self.env['res.partner'].sudo().create(vals)
        route = partner.route_id if 'route_id' in partner._fields else self.env['sales.route']
        return {
            'id': partner.id,
            'name': partner.display_name,
            'route_id': route.id if route else False,
            'route_name': route.display_name if route else '',
            'phone': partner.phone or partner.mobile or '',
        }

    @api.model
    def get_recreate_order_lines(self, plan_line_id, order_id, partner_id=False):
        plan_line = self.env['sales.route.plan.line'].browse(plan_line_id).exists() if plan_line_id else self.env['sales.route.plan.line']
        if not plan_line_id:
            self._check_quick_sale_unrestricted()
        elif not plan_line:
            raise UserError(_('Route plan line was not found.'))
        order = self.env['sale.order'].sudo().browse(order_id).exists()
        if not order:
            raise UserError(_('The selected previous sales order was not found.'))
        if plan_line and order.partner_id != plan_line.partner_id:
            raise UserError(_('You can only re-create orders for the same route client.'))
        if partner_id and order.partner_id.id != int(partner_id):
            raise UserError(_('The selected order belongs to a different customer.'))
        if order.state == 'cancel':
            raise UserError(_('Cancelled orders cannot be re-created.'))
        route = order.route_id if 'route_id' in order._fields else self.env['sales.route']
        return {
            'sale_order_id': order.id,
            'sale_order_name': order.name,
            'partner_id': order.partner_id.id,
            'partner_name': order.partner_id.display_name,
            'route_id': route.id if route else False,
            'route_name': route.display_name if route else '',
            'cart': self._prepare_cart_from_sale_order(order),
            'message': _('Loaded previous Sales Order %s. Modify the cart and resubmit to keep the same order number.') % order.name,
        }

    @api.model
    def get_terminal_data(self, plan_line_id=False):
        quick_mode = not bool(plan_line_id)
        if quick_mode:
            self._check_quick_sale_unrestricted()
            plan_line = self.env['sales.route.plan.line']
        else:
            plan_line = self.env['sales.route.plan.line'].browse(plan_line_id).exists()
            if not plan_line:
                raise UserError(_('Route plan line was not found.'))
            if not plan_line.partner_id:
                raise UserError(_('Please select a client before creating an order.'))

        currency = self.env.company.currency_id
        categories_by_id = {}
        products_data = []
        products = self._get_pos_saleable_products()
        for product in products:
            price = product.lst_price
            pricelist = plan_line.partner_id.property_product_pricelist if plan_line and plan_line.partner_id else self.env['product.pricelist']
            if pricelist:
                try:
                    price = pricelist._get_product_price(product, 1.0, plan_line.partner_id)
                except Exception:
                    price = product.lst_price
            category_ids = self._product_category_ids(product)
            for categ in self.env['product.category'].browse(category_ids).exists():
                categories_by_id[categ.id] = categ.display_name
            products_data.append({
                'id': product.id,
                'name': product.display_name,
                'default_code': product.default_code or '',
                'price_unit': price,
                'price_display': '%s %.2f' % (currency.symbol or currency.name, price),
                'category_ids': category_ids,
                'image_url': '/web/image/product.product/%s/image_128' % product.id,
            })

        # Start each terminal session empty, but expose previous orders for controlled re-create/edit.
        cart = []
        order = plan_line.sale_order_id if plan_line else self.env['sale.order']
        previous_orders = self._get_recreatable_orders(plan_line) if plan_line else []

        return {
            'quick_mode': quick_mode,
            'can_quick_sale_unrestricted': self.env.user.has_group('field_sales_route_plan.group_field_sales_quick_sale_unrestricted'),
            'plan_line_id': plan_line.id if plan_line else False,
            'plan_id': plan_line.plan_id.id if plan_line else False,
            'visit_id': plan_line.visit_id.id if plan_line and plan_line.visit_id else False,
            'partner_id': plan_line.partner_id.id if plan_line else False,
            'partner_name': plan_line.partner_id.display_name if plan_line else '',
            'route_id': plan_line.route_id.id if plan_line else False,
            'route_name': plan_line.route_id.display_name if plan_line else '',
            'sale_order_id': order.id if order else False,
            'sale_order_name': order.name if order else '',
            'currency_symbol': currency.symbol or currency.name,
            'categories': [{'id': cid, 'name': name} for cid, name in sorted(categories_by_id.items(), key=lambda item: item[1])],
            'products': products_data,
            'cart': cart,
            'previous_orders': previous_orders,
            'editing_order_id': False,
            'editing_order_name': '',
            'selected_sales_user_id': self.env.user.id,
            'selected_sales_user_name': self.env.user.name or self.env.user.login,
        }


    @api.model
    def _get_or_create_quick_sale_plan_line(self, partner, route, sales_user, order=False):
        """Create/find today's route plan line for an unrestricted Quick Sale.

        Quick Sale orders are route-independent at entry time, but performance,
        targets, and the Route Visits list are driven by route plan lines/visits.
        This helper assigns the order to the selected salesperson's route plan for
        today, even when the cashier/user creating the order is on another route.
        """
        if not partner or not sales_user:
            raise UserError(_('Select both the client and the salesperson before saving the quick sales order.'))
        if not route:
            route = partner.route_id if 'route_id' in partner._fields and partner.route_id else self.env['sales.route'].sudo().search([], limit=1)
        if not route:
            raise UserError(_('No route was found. Please create a route or assign the customer to a route before using Quick Sales.'))

        today = fields.Date.context_today(self)
        Plan = self.env['sales.route.plan'].sudo()
        Line = self.env['sales.route.plan.line'].sudo()
        Visit = self.env['sales.route.visit'].sudo()

        plan = Plan.search([
            ('plan_date', '=', today),
            ('user_id', '=', sales_user.id),
            ('route_id', '=', route.id),
        ], limit=1)
        if not plan:
            plan_vals = {
                'plan_date': today,
                'user_id': sales_user.id,
                'route_id': route.id,
                'planned_productive_calls': 1,
                'planned_unproductive_calls': 0,
                'state': 'in_progress',
            }
            hierarchy = self.env['sales.route.team.hierarchy'].sudo().search([('salesperson_id', '=', sales_user.id)], limit=1)
            if hierarchy and 'supervisor_id' in Plan._fields:
                plan_vals['supervisor_id'] = hierarchy.supervisor_id.id
            plan = Plan.create(plan_vals)

        line = Line.search([
            ('plan_id', '=', plan.id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if not line:
            purpose = self.env.ref('field_sales_route_plan.visit_purpose_van_sales', raise_if_not_found=False) or self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False)
            line = Line.create({
                'plan_id': plan.id,
                'partner_id': partner.id,
                'expected_call_type': 'productive',
                'expected_visit_purpose': 'van_sales',
                'expected_visit_purpose_id': purpose.id if purpose else False,
                'is_ad_hoc': True,
                'status': 'productive',
                'note': _('Auto-created from Van Sales terminal.'),
            })
        else:
            purpose = self.env.ref('field_sales_route_plan.visit_purpose_van_sales', raise_if_not_found=False)
            line.write({'status': 'productive', 'is_ad_hoc': True, 'expected_visit_purpose': 'van_sales', 'expected_visit_purpose_id': purpose.id if purpose else line.expected_visit_purpose_id.id})

        visit = line.visit_id or Visit.search([('plan_line_id', '=', line.id)], limit=1)
        # Quick Sales must be visible immediately in Route Visits, dashboards,
        # and My Field Work.  Those screens count visits by the assigned
        # salesperson plus today's check-in/check-out timestamps, so a quick
        # sale creates/updates a completed sales visit for the selected user
        # without changing the customer's permanent market route.
        quick_visit_time = fields.Datetime.now()
        if not visit:
            purpose = line.expected_visit_purpose_id or self.env.ref('field_sales_route_plan.visit_purpose_van_sales', raise_if_not_found=False) or self.env.ref('field_sales_route_plan.visit_purpose_sales', raise_if_not_found=False)
            visit = Visit.create({
                'plan_id': plan.id,
                'plan_line_id': line.id,
                'route_id': route.id,
                'partner_id': partner.id,
                'user_id': sales_user.id,
                'visit_purpose': 'van_sales',
                'visit_purpose_id': purpose.id if purpose else False,
                'state': 'checked_out',
                'check_in': quick_visit_time,
                'check_out': quick_visit_time,
                'note': _('Auto-created from Quick Sales Order %s.') % (order.name if order else ''),
            })
            line.write({'visit_id': visit.id})
        else:
            visit_vals = {
                'plan_id': plan.id,
                'plan_line_id': line.id,
                'route_id': route.id,
                'partner_id': partner.id,
                'user_id': sales_user.id,
            }
            if not visit.check_in:
                visit_vals['check_in'] = quick_visit_time
            if not visit.check_out:
                visit_vals['check_out'] = quick_visit_time
            if visit.state == 'draft':
                visit_vals['state'] = 'checked_out'
            visit.write(visit_vals)
            line.write({'visit_id': visit.id})

        # Keep the generated quick-sale route plan active so it is picked by
        # My Field Work and user dashboards after the order is saved.
        if plan.state in ('draft', 'submitted', 'approved'):
            plan.sudo().write({'state': 'in_progress'})
        return plan, line, visit

    @api.model
    def confirm_terminal_order(self, plan_line_id, cart_lines, sale_order_id=False, partner_id=False, route_id=False, sales_user_id=False):
        quick_mode = not bool(plan_line_id)
        if quick_mode:
            self._check_quick_sale_unrestricted()
            plan_line = self.env['sales.route.plan.line']
            partner = self.env['res.partner'].sudo().browse(int(partner_id or 0)).exists()
            if not partner:
                raise UserError(_('Please select a client before creating the quick sales order.'))
            route = self.env['sales.route'].sudo().browse(int(route_id or 0)).exists() if route_id else (partner.route_id if 'route_id' in partner._fields else self.env['sales.route'])
            order = self.env['sale.order'].sudo().browse(sale_order_id).exists() if sale_order_id else self.env['sale.order']
            # Always award Quick Sales Order visits to the salesperson selected in the terminal.
            # If an existing/re-created order is being edited and no salesperson was sent by the UI,
            # keep that order's salesperson instead of falling back to the logged-in cashier/user.
            assigned_user_id = int(sales_user_id or 0) or (order.user_id.id if order and order.user_id else self.env.user.id)
            sales_user = self.env['res.users'].sudo().browse(assigned_user_id).exists() or self.env.user
        else:
            plan_line = self.env['sales.route.plan.line'].browse(plan_line_id).exists()
            if not plan_line:
                raise UserError(_('Route plan line was not found.'))
            if not plan_line.partner_id:
                raise UserError(_('Please select a client before creating an order.'))
            partner = plan_line.partner_id
            route = plan_line.route_id
            sales_user = plan_line.user_id or self.env.user
        valid_lines = [line for line in (cart_lines or []) if line.get('product_id') and float(line.get('qty') or 0) > 0]
        if not valid_lines:
            raise UserError(_('Please add at least one product to the cart.'))

        if not quick_mode:
            order = self.env['sale.order'].sudo().browse(sale_order_id).exists() if sale_order_id else self.env['sale.order']
        is_recreated = bool(order)
        order_vals = {
            'partner_id': partner.id,
            'user_id': sales_user.id,
        }
        if 'route_id' in self.env['sale.order']._fields and route:
            order_vals['route_id'] = route.id
        quick_plan = self.env['sales.route.plan']
        quick_plan_line = self.env['sales.route.plan.line']
        quick_visit = self.env['sales.route.visit']
        if quick_mode:
            quick_plan, quick_plan_line, quick_visit = self._get_or_create_quick_sale_plan_line(partner, route, sales_user, order=order if order else False)
            route = quick_plan.route_id
            if 'route_plan_id' in self.env['sale.order']._fields:
                order_vals['route_plan_id'] = quick_plan.id
            if 'route_plan_line_id' in self.env['sale.order']._fields:
                order_vals['route_plan_line_id'] = quick_plan_line.id
        else:
            if 'route_plan_id' in self.env['sale.order']._fields:
                order_vals['route_plan_id'] = plan_line.plan_id.id
            if 'route_plan_line_id' in self.env['sale.order']._fields:
                order_vals['route_plan_line_id'] = plan_line.id
        if order:
            if order.partner_id != partner:
                raise UserError(_('The selected order belongs to a different customer.'))
            if order.state == 'cancel':
                raise UserError(_('Cancelled orders cannot be re-created.'))
            if any(line.qty_invoiced for line in order.order_line):
                raise UserError(_('This order already has invoiced quantities. Please create a new order instead.'))
            order.write(order_vals)
            order.order_line.filtered(lambda l: not l.display_type).unlink()
        else:
            order = self.env['sale.order'].sudo().create(order_vals)
        if plan_line:
            plan_line.sale_order_id = order.id

        for line in valid_lines:
            product = self.env['product.product'].browse(line['product_id']).exists()
            if not product:
                continue
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': product.id,
                'product_uom_qty': float(line.get('qty') or 0),
                'product_uom': product.uom_id.id,
                'price_unit': float(line.get('price_unit') or product.lst_price),
            })

        if quick_mode:
            # Link the Sales Order to the generated line and force the generated
            # visit/plan summaries to refresh immediately. This is what feeds
            # My Field Work and Manager Control Panel dashboards.
            quick_plan_line.write({'sale_order_id': order.id, 'status': 'productive'})
            if hasattr(order, '_refresh_route_visit_order_summary_cache'):
                order._refresh_route_visit_order_summary_cache()
            if quick_visit:
                quick_visit._compute_visit_orders()
            if quick_plan:
                quick_plan._compute_kpis()
        elif plan_line:
            plan_line.status = 'productive'
            if hasattr(order, '_refresh_route_visit_order_summary_cache'):
                order._refresh_route_visit_order_summary_cache()
        return {
            'type': 'success',
            'sale_order_id': order.id,
            'sale_order_name': order.name,
            'recreated': is_recreated,
            'assigned_sales_user_id': sales_user.id,
            'assigned_sales_user_name': sales_user.name or sales_user.login,
            'route_visit_id': (quick_visit.id if quick_mode and quick_visit else (plan_line.visit_id.id if plan_line and plan_line.visit_id else False)),
            'message': (_('Sales Order %s updated successfully and awarded to %s without changing the order number.') if is_recreated else _('Sales Order %s saved successfully and awarded to %s.')) % (order.name, sales_user.name or sales_user.login),
        }


    @api.model
    def action_print_pos_receipt(self, sale_order_id):
        order = self.env['sale.order'].sudo().browse(int(sale_order_id or 0)).exists()
        if not order:
            raise UserError(_('Sales Order was not found.'))
        # Route based users can only print orders for their own terminal customer unless they have quick sales rights.
        if not self.env.user.has_group('field_sales_route_plan.group_field_sales_quick_sale_unrestricted'):
            plan_lines = self.env['sales.route.plan.line'].sudo().search([('sale_order_id', '=', order.id)], limit=1)
            if plan_lines and plan_lines.user_id and plan_lines.user_id != self.env.user:
                raise UserError(_('You are not allowed to print this sales order receipt.'))
        return self.env.ref('field_sales_route_plan.action_report_field_sales_pos_receipt_80mm').report_action(order)

    def action_confirm_order(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.qty > 0)
        if not selected_lines:
            raise UserError(_('Enter quantity for at least one product.'))

        order = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'user_id': self.user_id.id,
            'route_id': self.route_id.id,
            'route_plan_id': self.plan_line_id.plan_id.id,
            'route_plan_line_id': self.plan_line_id.id,
        })
        self.plan_line_id.sale_order_id = order.id

        for line in selected_lines:
            self.env['sale.order.line'].create({
                'order_id': order.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': line.uom_id.id,
                'price_unit': line.price_unit,
            })

        self.plan_line_id.status = 'productive'
        return self._sale_order_form_action(order)


class RouteSaleTerminalLine(models.TransientModel):
    _name = 'route.sale.terminal.line'
    _description = 'Route Sale Terminal Product Line'

    wizard_id = fields.Many2one('route.sale.terminal.wizard', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True, readonly=True)
    default_code = fields.Char(string='Code', readonly=True)
    uom_id = fields.Many2one('uom.uom', string='UoM', readonly=True)
    qty = fields.Float(string='Qty')
    price_unit = fields.Float(string='Price')
    subtotal = fields.Monetary(compute='_compute_subtotal', currency_field='currency_id')
    currency_id = fields.Many2one(related='wizard_id.currency_id')

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit
