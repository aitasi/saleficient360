from datetime import datetime, time, timedelta
import pytz

from odoo import fields, http
from odoo.http import request


class FieldSalesGPSController(http.Controller):
    """JSON endpoints for mobile/web clients that can send browser GPS.

    Example JSON payload:
    {
      "plan_line_id": 12,
      "latitude": 0.347596,
      "longitude": 32.582520
    }
    """

    def _fsrp_fmcg_period_metrics(self, user_ids=None, route_ids=None, date_from=None, date_to=None):
        """Return FMCG retail/merchandising counts scoped to user/route/date."""
        bounds = self._local_dt_bounds(date_from=date_from, date_to=date_to) if hasattr(self, '_local_dt_bounds') else {}
        selected_from = bounds.get('selected_from') or fields.Date.context_today(request.env.user)
        selected_to = bounds.get('selected_to') or selected_from
        metrics = {
            'merch_visits': 0,
            'merch_submitted': 0,
            'merch_approved': 0,
            'retail_visits': 0,
            'retail_done': 0,
            'market_impact_activities': 0,
        }
        user_ids = user_ids or []
        route_ids = route_ids or []
        if 'fmcg.merch.visit' in request.env.registry:
            domain = [('date', '>=', selected_from), ('date', '<=', selected_to)]
            if user_ids:
                domain.append(('user_id', 'in', user_ids))
            if route_ids:
                domain.append(('route_id', 'in', route_ids))
            merch = request.env['fmcg.merch.visit'].sudo().search(domain)
            metrics.update({
                'merch_visits': len(merch),
                'merch_submitted': len(merch.filtered(lambda r: r.state in ('submitted', 'approved'))),
                'merch_approved': len(merch.filtered(lambda r: r.state == 'approved')),
                'merch_sku_score': round(sum(merch.mapped('sku_availability_score')) / len(merch), 1) if merch else 0.0,
                'merch_shelf_score': round(sum(merch.mapped('shelf_score')) / len(merch), 1) if merch else 0.0,
            })
        if 'fmcg.retail.execution.visit' in request.env.registry:
            domain = [('date', '>=', selected_from), ('date', '<=', selected_to)]
            if user_ids:
                domain.append(('user_id', 'in', user_ids))
            if route_ids:
                domain.append(('route_id', 'in', route_ids))
            retail = request.env['fmcg.retail.execution.visit'].sudo().search(domain)
            metrics.update({
                'retail_visits': len(retail),
                'retail_done': len(retail.filtered(lambda r: r.state == 'done')),
                'retail_compliance_score': round(sum(retail.mapped('compliance_score')) / len(retail), 1) if retail else 0.0,
            })
        if 'fmcg.market.impact.activity' in request.env.registry:
            domain = [('date', '>=', selected_from), ('date', '<=', selected_to)]
            if route_ids:
                domain.append(('route_id', 'in', route_ids))
            impact = request.env['fmcg.market.impact.activity'].sudo().search(domain)
            metrics['market_impact_activities'] = len(impact)
        return metrics


    @http.route('/field_sales/plan_line/checkin', type='json', auth='user', methods=['POST'])
    def checkin_plan_line(self, plan_line_id, latitude=None, longitude=None):
        line = request.env['sales.route.plan.line'].browse(int(plan_line_id)).exists()
        if not line:
            return {'ok': False, 'error': 'Plan line not found'}
        line.with_context(gps_latitude=latitude, gps_longitude=longitude).action_check_in()
        return {'ok': True, 'visit_id': line.visit_id.id, 'status': line.status}

    @http.route('/field_sales/plan_line/checkout', type='json', auth='user', methods=['POST'])
    def checkout_plan_line(self, plan_line_id, latitude=None, longitude=None):
        line = request.env['sales.route.plan.line'].browse(int(plan_line_id)).exists()
        if not line:
            return {'ok': False, 'error': 'Plan line not found'}
        line.with_context(gps_latitude=latitude, gps_longitude=longitude).action_check_out()
        return {'ok': True, 'visit_id': line.visit_id.id, 'status': line.status}

    @http.route('/field_sales/visit/checkin', type='json', auth='user', methods=['POST'])
    def checkin_visit(self, visit_id, latitude=None, longitude=None, place=None, address=None, area=None, geocode_raw=None):
        visit = request.env['sales.route.visit'].browse(int(visit_id)).exists()
        if not visit:
            return {'ok': False, 'error': 'Visit not found'}
        try:
            visit.with_context(gps_latitude=latitude, gps_longitude=longitude).action_check_in()
            # Prefer browser-resolved place details when provided because it keeps the user on the
            # same page and still works when the Odoo server cannot reach the geocoder.
            inline_vals = {}
            if place:
                inline_vals['checkin_place'] = place
            if address:
                inline_vals['checkin_address'] = address
            if area:
                inline_vals['checkin_area'] = area
            if geocode_raw:
                inline_vals['checkin_geocode_json'] = geocode_raw
            if inline_vals:
                visit.sudo().write(inline_vals)
            return {
                'ok': True,
                'visit_id': visit.id,
                'state': visit.state,
                'place': visit.checkin_place,
                'address': visit.checkin_address,
                'area': visit.checkin_area,
                'latitude': visit.checkin_latitude,
                'longitude': visit.checkin_longitude,
            }
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    @http.route('/field_sales/visit/checkout', type='json', auth='user', methods=['POST'])
    def checkout_visit(self, visit_id, latitude=None, longitude=None, place=None, address=None, area=None, geocode_raw=None):
        visit = request.env['sales.route.visit'].browse(int(visit_id)).exists()
        if not visit:
            return {'ok': False, 'error': 'Visit not found'}
        try:
            visit.with_context(gps_latitude=latitude, gps_longitude=longitude).action_check_out()
            # Prefer browser-resolved place details when provided because it keeps the user on the
            # same page and still works when the Odoo server cannot reach the geocoder.
            inline_vals = {}
            if place:
                inline_vals['checkout_place'] = place
            if address:
                inline_vals['checkout_address'] = address
            if area:
                inline_vals['checkout_area'] = area
            if geocode_raw:
                inline_vals['checkout_geocode_json'] = geocode_raw
            if inline_vals:
                visit.sudo().write(inline_vals)
            return {
                'ok': True,
                'visit_id': visit.id,
                'state': visit.state,
                'place': visit.checkout_place,
                'address': visit.checkout_address,
                'area': visit.checkout_area,
                'latitude': visit.checkout_latitude,
                'longitude': visit.checkout_longitude,
            }
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    @http.route('/field_sales/client_map/data', type='json', auth='user', methods=['POST'])
    def client_map_data(self, route_id=None, mode='today', date_from=None, date_to=None):
        """Return clients for the Client Map.

        Default mode intentionally loads only today's planned clients and clients
        visited today, so the map opens quickly and focuses the field manager on
        today's execution. Users can switch mode='all' from the filter to view
        every route client, including those not visited.
        """
        route_id = int(route_id or 0)
        mode = mode or 'today'
        today = fields.Date.context_today(request.env.user)
        try:
            start_date = fields.Date.from_string(date_from) if date_from else today
        except Exception:
            start_date = today
        try:
            end_date = fields.Date.from_string(date_to) if date_to else start_date
        except Exception:
            end_date = start_date
        if end_date < start_date:
            start_date, end_date = end_date, start_date
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)

        route_domain = []
        is_supervisor = request.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') or request.env.user.has_group('sales_team.group_sale_manager')
        if route_id:
            route_domain.append(('route_id', '=', route_id))
        if not is_supervisor:
            # Field users only see their assigned route/client map data.
            route_domain.append(('user_id', '=', request.env.user.id))

        planned_lines = request.env['sales.route.plan.line'].sudo().search(
            [('plan_date', '>=', start_date), ('plan_date', '<=', end_date), ('partner_id', '!=', False)] + route_domain,
            order='plan_date, sequence, id'
        )
        planned_partner_ids = set(planned_lines.mapped('partner_id').ids)
        planned_sequence_map = {}
        for idx, line in enumerate(planned_lines, start=1):
            if line.partner_id.id not in planned_sequence_map:
                planned_sequence_map[line.partner_id.id] = {
                    'sequence': line.sequence or idx,
                    'order': idx,
                    'plan_line_id': line.id,
                }

        visited_domain = [
            ('partner_id', '!=', False),
            '|',
                '&', ('check_in', '>=', fields.Datetime.to_string(start_dt)), ('check_in', '<=', fields.Datetime.to_string(end_dt)),
                '&', ('check_out', '>=', fields.Datetime.to_string(start_dt)), ('check_out', '<=', fields.Datetime.to_string(end_dt)),
        ] + route_domain
        visited_today = request.env['sales.route.visit'].sudo().search(visited_domain)
        visited_partner_ids = set(visited_today.mapped('partner_id').ids)

        # Clients who purchased today: confirmed/quotation sale orders plus POS receipts.
        # This supports the map filter requested by managers for same-day buying activity.
        sale_orders_today = request.env['sale.order'].sudo().search([
            ('partner_id', '!=', False),
            ('date_order', '>=', fields.Datetime.to_string(start_dt)),
            ('date_order', '<=', fields.Datetime.to_string(end_dt)),
            ('state', '!=', 'cancel'),
        ])
        purchased_partner_ids = set(sale_orders_today.mapped('partner_id').ids)
        if route_id and purchased_partner_ids:
            route_partners = request.env['res.partner'].sudo().browse(list(purchased_partner_ids)).filtered(lambda p: p.route_id.id == route_id)
            purchased_partner_ids = set(route_partners.ids)

        if mode == 'all':
            domain = [('customer_rank', '>', 0), ('route_id', '!=', False)]
            if route_id:
                domain.append(('route_id', '=', route_id))
            partners = request.env['res.partner'].sudo().search(domain, order='route_id,name', limit=1500)
        elif mode == 'today_planned':
            partners = request.env['res.partner'].sudo().browse(list(planned_partner_ids)).exists().sorted(lambda p: (p.route_id.name or '', p.name or ''))
        elif mode == 'today_visited':
            partners = request.env['res.partner'].sudo().browse(list(visited_partner_ids)).exists().sorted(lambda p: (p.route_id.name or '', p.name or ''))
        elif mode == 'purchased_today':
            partners = request.env['res.partner'].sudo().browse(list(purchased_partner_ids)).exists().sorted(lambda p: (p.route_id.name or '', p.name or ''))
        elif mode == 'dormant':
            domain = [('customer_rank', '>', 0), ('route_id', '!=', False), ('route_age_bucket', 'in', ['30_days', 'never_bought'])]
            if route_id:
                domain.append(('route_id', '=', route_id))
            partners = request.env['res.partner'].sudo().search(domain, order='route_id,name', limit=1000)
        elif mode == 'overdue_14':
            domain = [('customer_rank', '>', 0), ('route_id', '!=', False), ('days_since_last_purchase', '>=', 14)]
            if route_id:
                domain.append(('route_id', '=', route_id))
            partners = request.env['res.partner'].sudo().search(domain, order='route_id,name', limit=1000)
        elif mode == 'high_value':
            domain = [('customer_rank', '>', 0), ('route_id', '!=', False), ('customer_classification', 'in', ['key_account', 'wholesale'])]
            if route_id:
                domain.append(('route_id', '=', route_id))
            partners = request.env['res.partner'].sudo().search(domain, order='route_id,name', limit=1000)
        else:
            # Default: today's clients first - planned today or visited today.
            partners = request.env['res.partner'].sudo().browse(list(planned_partner_ids | visited_partner_ids)).exists().sorted(lambda p: (p.route_id.name or '', p.name or ''))

        clients = []
        for p in partners:
            is_planned = p.id in planned_partner_ids
            is_visited = p.id in visited_partner_ids
            is_purchased = p.id in purchased_partner_ids
            if is_planned and is_visited:
                map_status = 'planned_visited'
                status_label = 'Planned & Visited'
            elif is_purchased:
                map_status = 'purchased'
                status_label = 'Purchased'
            elif is_planned:
                map_status = 'planned'
                status_label = 'Planned'
            elif is_visited:
                map_status = 'visited'
                status_label = 'Visited'
            else:
                map_status = 'other'
                status_label = 'Route Client'
            address = ', '.join([x for x in [p.street, p.street2, p.city, p.state_id.name, p.country_id.name] if x])
            coords = p.get_route_map_coordinates()
            source_labels = {
                'client_assigned': 'Assigned Client Coordinates',
                'partner_geolocation': 'Partner Geolocation',
                'last_visit_gps': 'Last Visit GPS',
                'none': 'No Coordinates',
            }
            clients.append({
                'id': p.id,
                'name': p.display_name,
                'route': p.route_id.name if p.route_id else '',
                'route_id': p.route_id.id if p.route_id else False,
                'latitude': coords.get('latitude') or 0.0,
                'longitude': coords.get('longitude') or 0.0,
                'has_location': coords.get('has_location'),
                'coordinate_source': coords.get('source'),
                'coordinate_source_label': source_labels.get(coords.get('source'), 'No Coordinates'),
                'address': address,
                'classification': p.customer_classification or '',
                'age_bucket': p.route_age_bucket or '',
                'days_since_last_purchase': p.days_since_last_purchase,
                'map_status': map_status,
                'status_label': status_label,
                'planned_today': is_planned,
                'visited_today': is_visited,
                'purchased_today': is_purchased,
                'planned_sequence': planned_sequence_map.get(p.id, {}).get('sequence', 0),
                'planned_order': planned_sequence_map.get(p.id, {}).get('order', 0),
                'plan_line_id': planned_sequence_map.get(p.id, {}).get('plan_line_id', False),
                'sales_amount_today': sum(sale_orders_today.filtered(lambda so: so.partner_id.id == p.id).mapped('amount_total')),
                'heat_weight': max(1, min(8, int((sum(sale_orders_today.filtered(lambda so: so.partner_id.id == p.id).mapped('amount_total')) or 0) / 100000) + 1)),
            })
        return {
            'clients': clients,
            'summary': {
                'mode': mode,
                'total': len(clients),
                'planned_today': len(planned_partner_ids),
                'visited_today': len(visited_partner_ids),
                'purchased_today': len(purchased_partner_ids),
                'date_from': fields.Date.to_string(start_date),
                'date_to': fields.Date.to_string(end_date),
            },
        }


    def _is_field_sales_manager(self):
        user = request.env.user
        return user.has_group('field_sales_route_plan.group_field_sales_manager') or user.has_group('sales_team.group_sale_manager')

    def _is_field_sales_supervisor(self):
        return request.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor')

    def _assigned_supervisor_route_ids(self, user=None):
        user = user or request.env.user
        Route = request.env['sales.route'].sudo()
        if 'supervisor_ids' not in Route._fields:
            return []
        return Route.search([('supervisor_ids', 'in', [user.id])]).ids

    def _visible_field_user_ids(self):
        """Scope data by the new hierarchy.

        Sales Manager: sees all configured field users and all route users.
        Supervisor: sees self, assigned sales persons and users on routes they supervise.
        Sales Person: sees self only.
        """
        Hierarchy = request.env['sales.route.team.hierarchy'].sudo() if 'sales.route.team.hierarchy' in request.env.registry else False
        Route = request.env['sales.route'].sudo()
        user_ids = {request.env.user.id}
        if self._is_field_sales_manager():
            if Hierarchy:
                rows = Hierarchy.search([('active', '=', True)])
                user_ids.update(rows.mapped('manager_id').ids)
                user_ids.update(rows.mapped('supervisor_id').ids)
                user_ids.update(rows.mapped('salesperson_id').ids)
            user_ids.update(Route.search([]).mapped('user_id').ids)
            if 'user_ids' in Route._fields:
                user_ids.update(Route.search([]).mapped('user_ids').ids)
            if 'supervisor_ids' in Route._fields:
                user_ids.update(Route.search([]).mapped('supervisor_ids').ids)
            return list(user_ids)
        if Hierarchy:
            ids = Hierarchy.get_visible_user_ids(request.env.user)
            user_ids.update(ids or [])
        route_ids = self._assigned_supervisor_route_ids(request.env.user)
        if route_ids:
            routes = Route.browse(route_ids)
            user_ids.update(routes.mapped('user_id').ids)
            if 'user_ids' in Route._fields:
                user_ids.update(routes.mapped('user_ids').ids)
        return list(user_ids)

    def _visible_route_ids(self):
        """Routes that should feed dashboards/control panels.

        Do not let manager KPIs fall back to the whole company.  The manager
        control panel must only count configured market routes and the users
        assigned on those routes.
        """
        Route = request.env['sales.route'].sudo()
        user = request.env.user
        route_ids = set()
        if self._is_field_sales_manager():
            Hierarchy = request.env['sales.route.team.hierarchy'].sudo() if 'sales.route.team.hierarchy' in request.env.registry else False
            hierarchy_user_ids = set([user.id])
            if Hierarchy:
                rows = Hierarchy.search([('active', '=', True), ('manager_id', '=', user.id)])
                hierarchy_user_ids.update(rows.mapped('supervisor_id').ids)
                hierarchy_user_ids.update(rows.mapped('salesperson_id').ids)
            domain = ['|', '|',
                ('supervisor_ids', 'in', list(hierarchy_user_ids)),
                ('user_id', 'in', list(hierarchy_user_ids)),
                ('user_ids', 'in', list(hierarchy_user_ids)),
            ]
            route_ids.update(Route.search(domain).ids)
            # Compatibility fallback: older installations often have sales/history
            # but no new Team Hierarchy or multi-user route assignments yet. In that
            # case a manager must still see company historical metrics instead of a
            # blank dashboard.
            if not route_ids:
                route_ids.update(Route.search([]).ids)
            return list(route_ids)
        route_ids.update(self._assigned_supervisor_route_ids(user))
        if route_ids:
            return list(route_ids)
        return []

    def _users_for_route_ids(self, route_ids):
        Route = request.env['sales.route'].sudo()
        users = request.env['res.users'].sudo().browse()
        routes = Route.browse([int(r) for r in (route_ids or []) if r]).exists()
        if routes:
            users |= routes.mapped('user_id')
            if 'user_ids' in Route._fields:
                users |= routes.mapped('user_ids')
        # Manager compatibility fallback: if no users are linked on routes yet,
        # include historic sales users so old Sale Orders/POS Orders can feed the
        # control panel immediately after upgrade.
        if not users and self._is_field_sales_manager():
            SaleOrder = request.env['sale.order'].sudo()
            if 'user_id' in SaleOrder._fields:
                users |= SaleOrder.search([('state', 'not in', ['cancel', 'cancelled']), ('user_id', '!=', False)]).mapped('user_id')
            if 'pos.order' in request.env.registry:
                PosOrder = request.env['pos.order'].sudo()
                if 'user_id' in PosOrder._fields:
                    users |= PosOrder.search([('state', 'not in', ['cancel', 'cancelled']), ('user_id', '!=', False)]).mapped('user_id')
            users |= request.env['res.users'].sudo().search([('share', '=', False), ('active', '=', True)])
        return users.ids

    def _performance_row(self, name, role, user_ids=None, route_ids=None):
        user_ids = [int(x) for x in (user_ids or []) if x]
        route_ids = [int(x) for x in (route_ids or []) if x]
        today = fields.Date.context_today(request.env.user)
        plan_domain = [('plan_date', '=', today)]
        visit_domain = []
        if user_ids:
            plan_domain.append(('user_id', 'in', user_ids))
            visit_domain.append(('user_id', 'in', user_ids))
        if route_ids:
            plan_domain.append(('route_id', 'in', route_ids))
            visit_domain.append(('route_id', 'in', route_ids))
        plans = request.env['sales.route.plan'].sudo().search(plan_domain)
        visits = request.env['sales.route.visit'].sudo().search(visit_domain + [('check_in', '!=', False)])
        period = self._kpi_period_values(user_ids=user_ids, route_ids=route_ids) if user_ids else self._kpi_period_values(user_ids=[], route_ids=route_ids)
        return {
            'name': name,
            'role': role,
            'users': len(set(user_ids)),
            'routes': len(set(route_ids)),
            'planned': sum(plans.mapped('total_planned_calls')),
            'visited': sum(plans.mapped('checked_in_calls')),
            'productive': sum(plans.mapped('productive_calls')),
            'sales': sum(plans.mapped('total_sales_amount')),
            'today_sales_fmt': period.get('today_sales_fmt'),
            'mtd_sales_fmt': period.get('mtd_sales_fmt'),
            'ytd_sales_fmt': period.get('ytd_sales_fmt'),
            'today_pos_order_total_fmt': period.get('today_pos_order_total_fmt'),
            'mtd_pos_order_total_fmt': period.get('mtd_pos_order_total_fmt'),
            'ytd_pos_order_total_fmt': period.get('ytd_pos_order_total_fmt'),
            'today_pos_payments_fmt': period.get('today_pos_payments_fmt'),
            'mtd_pos_payments_fmt': period.get('mtd_pos_payments_fmt'),
            'ytd_pos_payments_fmt': period.get('ytd_pos_payments_fmt'),
            'today_amount_due_fmt': period.get('today_amount_due_fmt'),
            'mtd_amount_due_fmt': period.get('mtd_amount_due_fmt'),
            'ytd_amount_due_fmt': period.get('ytd_amount_due_fmt'),
            # Legacy keys retained so old custom views do not crash; values now show POS Order totals, not Van Sales cards.
            'today_van_sales_fmt': period.get('today_pos_order_total_fmt'),
            'mtd_van_sales_fmt': period.get('mtd_pos_order_total_fmt'),
            'ytd_van_sales_fmt': period.get('ytd_pos_order_total_fmt'),
            'today_orders': period.get('today_orders'),
            'mtd_orders': period.get('mtd_orders'),
            'ytd_orders': period.get('ytd_orders'),
        }

    def _management_performance_sections(self):
        user = request.env.user
        Hierarchy = request.env['sales.route.team.hierarchy'].sudo() if 'sales.route.team.hierarchy' in request.env.registry else False
        Route = request.env['sales.route'].sudo()
        manager_rows, supervisor_rows, salesperson_rows = [], [], []
        assigned_routes = []
        if self._is_field_sales_manager():
            rows = Hierarchy.search([('active', '=', True), ('manager_id', '=', user.id)]) if Hierarchy else request.env['sales.route.team.hierarchy']
            supervisors = rows.mapped('supervisor_id') if Hierarchy else request.env['res.users']
            if not supervisors and self._is_field_sales_manager():
                supervisors = request.env['res.users'].sudo().search([('groups_id', 'in', [request.env.ref('field_sales_route_plan.group_field_sales_supervisor').id])])
            for sup in supervisors:
                sup_rows = rows.filtered(lambda r, sup=sup: r.supervisor_id == sup) if Hierarchy else rows
                route_ids = Route.search([('supervisor_ids', 'in', [sup.id])]).ids if 'supervisor_ids' in Route._fields else []
                member_ids = set([sup.id])
                if sup_rows:
                    member_ids.update(sup_rows.mapped('salesperson_id').ids)
                if route_ids:
                    routes = Route.browse(route_ids)
                    member_ids.update(routes.mapped('user_id').ids)
                    if 'user_ids' in Route._fields:
                        member_ids.update(routes.mapped('user_ids').ids)
                supervisor_rows.append(self._performance_row(sup.name, 'Supervisor', list(member_ids), route_ids))
        elif self._is_field_sales_supervisor():
            rows = Hierarchy.search([('active', '=', True), ('supervisor_id', '=', user.id)]) if Hierarchy else request.env['sales.route.team.hierarchy']
            managers = rows.mapped('manager_id') if Hierarchy else request.env['res.users']
            for mgr in managers:
                manager_rows.append(self._performance_row(mgr.name, 'Sales Manager', [mgr.id], []))
            route_ids = self._assigned_supervisor_route_ids(user)
            for r in Route.browse(route_ids):
                assigned_routes.append({'id': r.id, 'name': r.name, 'code': r.code or '', 'salespersons': ', '.join(r.user_ids.mapped('name')) if 'user_ids' in Route._fields else (r.user_id.name or '')})
            salespersons = rows.mapped('salesperson_id') if Hierarchy else request.env['res.users']
            if route_ids:
                routes = Route.browse(route_ids)
                salespersons |= routes.mapped('user_id')
                if 'user_ids' in Route._fields:
                    salespersons |= routes.mapped('user_ids')
            for sp in salespersons:
                sp_route_ids = Route.search(['|', ('user_id', '=', sp.id), ('user_ids', 'in', [sp.id])]).ids if 'user_ids' in Route._fields else Route.search([('user_id', '=', sp.id)]).ids
                salesperson_rows.append(self._performance_row(sp.name, 'Sales Person', [sp.id], sp_route_ids))
        return {
            'manager_performance': manager_rows,
            'supervisor_performance': supervisor_rows,
            'salesperson_performance': salesperson_rows,
            'assigned_routes': assigned_routes,
        }

    def _money_fmt(self, value):
        return '{:,.2f}'.format(value or 0.0)

    def _sum_visit_money(self, domain, field_name):
        Visit = request.env['sales.route.visit'].sudo()
        if field_name not in Visit._fields:
            return 0.0
        return sum(Visit.search(domain).mapped(field_name))

    def _local_dt_bounds(self, date_from=None, date_to=None):
        """Return local Today/MTD/YTD and selected-period boundaries converted to UTC strings."""
        now_local = fields.Datetime.context_timestamp(request.env.user, fields.Datetime.now())
        today = now_local.date()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)
        tomorrow = today + timedelta(days=1)

        def parse_local_date(value, fallback):
            if not value:
                return fallback
            try:
                return fields.Date.from_string(value)
            except Exception:
                return fallback

        selected_from = parse_local_date(date_from, today)
        selected_to = parse_local_date(date_to, selected_from)
        if selected_to < selected_from:
            selected_from, selected_to = selected_to, selected_from
        selected_to_exclusive = selected_to + timedelta(days=1)

        def to_utc_string(local_date):
            local_naive = datetime.combine(local_date, time.min)
            tz = pytz.timezone(request.env.user.tz or 'UTC')
            local_aware = tz.localize(local_naive)
            utc_naive = local_aware.astimezone(pytz.utc).replace(tzinfo=None)
            return fields.Datetime.to_string(utc_naive)

        return {
            'today': today,
            'today_start': to_utc_string(today),
            'month_start': to_utc_string(month_start),
            'year_start': to_utc_string(year_start),
            'tomorrow_start': to_utc_string(tomorrow),
            'selected_from': selected_from,
            'selected_to': selected_to,
            'selected_start': to_utc_string(selected_from),
            'selected_end': to_utc_string(selected_to_exclusive),
            'selected_label': str(selected_from) if selected_from == selected_to else '%s to %s' % (selected_from, selected_to),
        }


    def _fsrp_amount_field(self, Model):
        """Best amount field for historical POS/order sales in dashboards."""
        for field_name in ('amount_total', 'amount_paid', 'amount_tax'):
            if field_name in Model._fields:
                return field_name
        return False

    def _fsrp_user_route_domains(self, Model, user_ids=None, route_ids=None):
        """Build domains that include legacy sales not linked to new route plans.

        Older orders often have only sale.order.user_id and/or the customer's
        assigned route fields.  Newer orders may also have route_id populated.
        The manager panel should count both.
        """
        domains = []
        ids = [int(x) for x in (user_ids or []) if x]
        if user_ids is not None:
            if ids:
                user_parts = []
                if 'user_id' in Model._fields:
                    user_parts.append([('user_id', 'in', ids)])
                # Legacy route assignment kept on the customer.
                user_parts.append([('partner_id.route_user_id', 'in', ids)])
                if len(user_parts) == 1:
                    domains += user_parts[0]
                else:
                    domains += ['|'] + user_parts[0] + user_parts[1]
            else:
                domains.append(('id', '=', 0))
        rids = [int(x) for x in (route_ids or []) if x]
        if route_ids is not None:
            if rids:
                route_parts = []
                if 'route_id' in Model._fields:
                    route_parts.append([('route_id', 'in', rids)])
                route_parts.append([('partner_id.route_id', 'in', rids)])
                if len(route_parts) == 1:
                    domains += route_parts[0]
                else:
                    domains += ['|'] + route_parts[0] + route_parts[1]
            else:
                domains.append(('id', '=', 0))
        return domains

    def _fsrp_order_domain(self, Model, start, end, user_ids=None, route_ids=None):
        domain = []
        if 'date_order' in Model._fields:
            domain += [('date_order', '>=', start), ('date_order', '<', end)]
        elif 'date' in Model._fields:
            domain += [('date', '>=', start), ('date', '<', end)]
        elif 'create_date' in Model._fields:
            domain += [('create_date', '>=', start), ('create_date', '<', end)]
        if 'state' in Model._fields:
            domain.append(('state', 'not in', ['cancel', 'cancelled']))
        domain += self._fsrp_user_route_domains(Model, user_ids=user_ids, route_ids=route_ids)
        return domain

    def _fsrp_sum_orders(self, Model, domain):
        amount_field = self._fsrp_amount_field(Model)
        if not amount_field:
            return 0.0, 0
        records = Model.search(domain)
        return sum(records.mapped(amount_field)), len(records)

    def _sum_visit_money(self, domain, field_name):
        Visit = request.env['sales.route.visit'].sudo()
        if field_name not in Visit._fields:
            return 0.0
        return sum(Visit.search(domain).mapped(field_name))

    def _van_sales_amounts(self, visit_base, bounds, user_ids=None, route_ids=None):
        """Return Today/MTD/YTD Van Sales using visits plus historical POS fallback."""
        Visit = request.env['sales.route.visit'].sudo()
        van_base = list(visit_base) + ['|', ('visit_purpose', '=', 'van_sales'), ('visit_purpose_category', '=', 'van_sales')]
        def sum_for(start_key):
            domain = van_base + [('check_in', '>=', bounds[start_key]), ('check_in', '<', bounds['tomorrow_start'])]
            visits = Visit.search(domain)
            return sum((visits.mapped('sale_order_total_amount') or [])) + sum((visits.mapped('pos_order_total_amount') or []))
        today = sum_for('today_start')
        mtd = sum_for('month_start')
        ytd = sum_for('year_start')
        # If visit-based van sales are empty, include historical POS orders so old
        # figures still appear on manager dashboards after upgrading the module.
        if 'pos.order' in request.env.registry:
            Pos = request.env['pos.order'].sudo()
            amount_field = self._fsrp_amount_field(Pos)
            if amount_field:
                t, _ = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['today_start'], bounds['tomorrow_start'], user_ids=user_ids, route_ids=route_ids))
                m, _ = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['month_start'], bounds['tomorrow_start'], user_ids=user_ids, route_ids=route_ids))
                y, _ = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['year_start'], bounds['tomorrow_start'], user_ids=user_ids, route_ids=route_ids))
                today = today or t
                mtd = mtd or m
                ytd = ytd or y
        return {
            'today_van_sales': today,
            'mtd_van_sales': mtd,
            'ytd_van_sales': ytd,
            'today_van_sales_fmt': self._money_fmt(today),
            'mtd_van_sales_fmt': self._money_fmt(mtd),
            'ytd_van_sales_fmt': self._money_fmt(ytd),
        }

    def _kpi_period_values(self, user=None, user_ids=None, route_ids=None, date_from=None, date_to=None):
        """Return Today/MTD/YTD KPIs using both new route data and legacy sales.

        This is intentionally historical-data friendly.  It counts:
        - new route visits / route linked orders,
        - old sale orders by salesperson,
        - old sale orders through customer route assignment,
        - POS receipts where available.
        """
        bounds = self._local_dt_bounds(date_from=date_from, date_to=date_to)
        today = bounds['today']
        visit_base = [('check_in', '!=', False), ('state', 'in', ['checked_in', 'checked_out', 'done'])]
        if user_ids is not None:
            ids = [int(x) for x in user_ids if x]
            if ids:
                visit_base.append(('user_id', 'in', ids))
            else:
                visit_base.append(('id', '=', 0))
        elif user:
            ids = [user.id]
            visit_base.append(('user_id', '=', user.id))
        else:
            ids = None
        if route_ids is not None:
            rids = [int(x) for x in route_ids if x]
            if rids:
                visit_base.append(('route_id', 'in', rids))
            else:
                visit_base.append(('id', '=', 0))
        else:
            rids = None
        Visit = request.env['sales.route.visit'].sudo()
        SaleOrder = request.env['sale.order'].sudo()
        today_visit_domain = visit_base + [('check_in', '>=', bounds['today_start']), ('check_in', '<', bounds['tomorrow_start'])]
        mtd_visit_domain = visit_base + [('check_in', '>=', bounds['month_start']), ('check_in', '<', bounds['tomorrow_start'])]
        ytd_visit_domain = visit_base + [('check_in', '>=', bounds['year_start']), ('check_in', '<', bounds['tomorrow_start'])]
        selected_visit_domain = visit_base + [('check_in', '>=', bounds['selected_start']), ('check_in', '<', bounds['selected_end'])]

        today_order_domain = self._fsrp_order_domain(SaleOrder, bounds['today_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None)
        mtd_order_domain = self._fsrp_order_domain(SaleOrder, bounds['month_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None)
        ytd_order_domain = self._fsrp_order_domain(SaleOrder, bounds['year_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None)
        selected_order_domain = self._fsrp_order_domain(SaleOrder, bounds['selected_start'], bounds['selected_end'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None)

        today_sales, today_orders_count = self._fsrp_sum_orders(SaleOrder, today_order_domain)
        mtd_sales, mtd_orders_count = self._fsrp_sum_orders(SaleOrder, mtd_order_domain)
        ytd_sales, ytd_orders_count = self._fsrp_sum_orders(SaleOrder, ytd_order_domain)
        selected_sales, selected_orders_count = self._fsrp_sum_orders(SaleOrder, selected_order_domain)

        pos_today = pos_mtd = pos_ytd = pos_selected = 0.0
        pos_today_count = pos_mtd_count = pos_ytd_count = pos_selected_count = 0
        if 'pos.order' in request.env.registry:
            Pos = request.env['pos.order'].sudo()
            pos_today, pos_today_count = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['today_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None))
            pos_mtd, pos_mtd_count = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['month_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None))
            pos_ytd, pos_ytd_count = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['year_start'], bounds['tomorrow_start'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None))
            pos_selected, pos_selected_count = self._fsrp_sum_orders(Pos, self._fsrp_order_domain(Pos, bounds['selected_start'], bounds['selected_end'], user_ids=ids if user_ids is not None or user else None, route_ids=rids if route_ids is not None else None))

        # POS Payments must come only from the amount actually paid on the POS
        # order generated from the Sales Order, as stored on Route Visits.
        # Do not use the full POS order total as payment.
        today_pos_payments = self._sum_visit_money(today_visit_domain, 'pos_order_paid_amount')
        mtd_pos_payments = self._sum_visit_money(mtd_visit_domain, 'pos_order_paid_amount')
        ytd_pos_payments = self._sum_visit_money(ytd_visit_domain, 'pos_order_paid_amount')
        selected_pos_payments = self._sum_visit_money(selected_visit_domain, 'pos_order_paid_amount')
        if not today_pos_payments:
            today_pos_payments = self._sum_visit_money(today_visit_domain, 'pos_order_payment_amount')
        if not mtd_pos_payments:
            mtd_pos_payments = self._sum_visit_money(mtd_visit_domain, 'pos_order_payment_amount')
        if not ytd_pos_payments:
            ytd_pos_payments = self._sum_visit_money(ytd_visit_domain, 'pos_order_payment_amount')
        if not selected_pos_payments:
            selected_pos_payments = self._sum_visit_money(selected_visit_domain, 'pos_order_payment_amount')
        today_pos_due = self._sum_visit_money(today_visit_domain, 'pos_order_due_amount')
        mtd_pos_due = self._sum_visit_money(mtd_visit_domain, 'pos_order_due_amount')
        ytd_pos_due = self._sum_visit_money(ytd_visit_domain, 'pos_order_due_amount')
        selected_pos_due = self._sum_visit_money(selected_visit_domain, 'pos_order_due_amount')

        # POS Order totals come from Route Visits and represent the total POS
        # order amount generated from the Sales Order.
        visit_pos_today = self._sum_visit_money(today_visit_domain, 'pos_order_total_amount')
        visit_pos_mtd = self._sum_visit_money(mtd_visit_domain, 'pos_order_total_amount')
        visit_pos_ytd = self._sum_visit_money(ytd_visit_domain, 'pos_order_total_amount')
        visit_pos_selected = self._sum_visit_money(selected_visit_domain, 'pos_order_total_amount')

        # Sales cards must represent Sales Order value only. POS Order, POS
        # Payment, and POS Amount Due are reported as separate cards.
        today_sales_total = today_sales
        mtd_sales_total = mtd_sales
        ytd_sales_total = ytd_sales
        selected_sales_total = selected_sales

        # Compatibility aliases retained for older widgets/custom code only.
        today_invoices_total = today_sales_total
        mtd_invoices_total = mtd_sales_total
        ytd_invoices_total = ytd_sales_total
        selected_invoices_total = selected_sales_total
        today_collections_total = today_pos_payments
        mtd_collections_total = mtd_pos_payments
        ytd_collections_total = ytd_pos_payments
        today_variance_total = today_pos_due
        mtd_variance_total = mtd_pos_due
        ytd_variance_total = ytd_pos_due

        return {
            'panel_title': 'Manager Control Panel' if self._is_field_sales_manager() else 'Supervisor Control Panel',
            'today': str(today),
            'selected_from': str(bounds['selected_from']),
            'selected_to': str(bounds['selected_to']),
            'selected_label': bounds['selected_label'],
            'selected_visits': Visit.search_count(selected_visit_domain),
            'selected_orders': selected_orders_count,
            'selected_sales': selected_sales_total,
            'selected_sales_fmt': self._money_fmt(selected_sales_total),
            'selected_pos_order_total': visit_pos_selected,
            'selected_pos_order_total_fmt': self._money_fmt(visit_pos_selected),
            'selected_invoices': selected_invoices_total,
            'selected_invoices_fmt': self._money_fmt(selected_invoices_total),
            'selected_pos_payments': selected_pos_payments,
            'selected_pos_payments_fmt': self._money_fmt(selected_pos_payments),
            'selected_collections': selected_pos_payments,
            'selected_collections_fmt': self._money_fmt(selected_pos_payments),
            'selected_amount_due': selected_pos_due,
            'selected_amount_due_fmt': self._money_fmt(selected_pos_due),
            'selected_variance': selected_pos_due,
            'selected_variance_fmt': self._money_fmt(selected_pos_due),
            'today_visits': Visit.search_count(today_visit_domain),
            'mtd_visits': Visit.search_count(mtd_visit_domain),
            'ytd_visits': Visit.search_count(ytd_visit_domain),
            'today_orders': today_orders_count,
            'mtd_orders': mtd_orders_count,
            'ytd_orders': ytd_orders_count,
            'today_sales': today_sales_total,
            'mtd_sales': mtd_sales_total,
            'ytd_sales': ytd_sales_total,
            'today_sales_fmt': self._money_fmt(today_sales_total),
            'mtd_sales_fmt': self._money_fmt(mtd_sales_total),
            'ytd_sales_fmt': self._money_fmt(ytd_sales_total),
            'today_pos_order_total': visit_pos_today,
            'mtd_pos_order_total': visit_pos_mtd,
            'ytd_pos_order_total': visit_pos_ytd,
            'today_pos_order_total_fmt': self._money_fmt(visit_pos_today),
            'mtd_pos_order_total_fmt': self._money_fmt(visit_pos_mtd),
            'ytd_pos_order_total_fmt': self._money_fmt(visit_pos_ytd),
            'today_invoices': today_invoices_total,
            'mtd_invoices': mtd_invoices_total,
            'ytd_invoices': ytd_invoices_total,
            'today_invoices_fmt': self._money_fmt(today_invoices_total),
            'mtd_invoices_fmt': self._money_fmt(mtd_invoices_total),
            'ytd_invoices_fmt': self._money_fmt(ytd_invoices_total),
            'today_collections': today_collections_total,
            'mtd_collections': mtd_collections_total,
            'ytd_collections': ytd_collections_total,
            'today_collections_fmt': self._money_fmt(today_collections_total),
            'mtd_collections_fmt': self._money_fmt(mtd_collections_total),
            'ytd_collections_fmt': self._money_fmt(ytd_collections_total),
            'today_variance': today_variance_total,
            'mtd_variance': mtd_variance_total,
            'ytd_variance': ytd_variance_total,
            'today_variance_fmt': self._money_fmt(today_variance_total),
            'mtd_variance_fmt': self._money_fmt(mtd_variance_total),
            'ytd_variance_fmt': self._money_fmt(ytd_variance_total),
            'today_pos_payments': today_pos_payments,
            'mtd_pos_payments': mtd_pos_payments,
            'ytd_pos_payments': ytd_pos_payments,
            'today_pos_payments_fmt': self._money_fmt(today_pos_payments),
            'mtd_pos_payments_fmt': self._money_fmt(mtd_pos_payments),
            'ytd_pos_payments_fmt': self._money_fmt(ytd_pos_payments),
            'today_amount_due': today_pos_due,
            'mtd_amount_due': mtd_pos_due,
            'ytd_amount_due': ytd_pos_due,
            **self._van_sales_amounts(visit_base, bounds, user_ids=ids if ids is not None else None, route_ids=rids if route_ids is not None else None),
            'today_amount_due_fmt': self._money_fmt(today_pos_due),
            'mtd_amount_due_fmt': self._money_fmt(mtd_pos_due),
            'ytd_amount_due_fmt': self._money_fmt(ytd_pos_due),
            'legacy_sales_enabled': True,
        }

    @http.route('/field_sales/simple_mode/data', type='json', auth='user', methods=['POST'])
    def simple_mode_data(self, date_from=None, date_to=None):
        license_info = request.env['sales.route.license'].sudo().get_license_info()
        if license_info.get('is_blocked'):
            return {'license': license_info, 'blocked': True, 'smart_alerts': [{'level': 'danger', 'message': license_info.get('message')}] }
        today = fields.Date.context_today(request.env.user)
        Plan = request.env['sales.route.plan'].sudo()
        plans = Plan.search([('plan_date', '=', today), ('user_id', '=', request.env.user.id)], order='id desc', limit=5)
        current_plan = plans[:1]
        next_line = current_plan._get_next_actionable_line() if current_plan else request.env['sales.route.plan.line']
        target_cards = request.env['sales.route.target'].sudo().fsrp_target_cards(
            user=request.env.user,
            route=current_plan.route_id if current_plan and current_plan.route_id else False,
            limit=6,
        ) if 'sales.route.target' in request.env.registry else {'personal_targets': [], 'group_targets': []}
        # SKU target summary must always be initialized. Some databases may not
        # have SKU targets or cached performance rows yet; the salesperson
        # dashboard should still load instead of raising NameError.
        sku_target_summary = {}
        if 'sales.route.sku.target.performance' in request.env.registry:
            try:
                selected_from = fields.Date.from_string(date_from) if date_from else today
                selected_to = fields.Date.from_string(date_to) if date_to else today
                request.env['sales.route.sku.target.performance'].sudo().recompute_for_targets(
                    date_from=selected_from, date_to=selected_to, user_ids=[request.env.user.id], limit=30
                )
                sku_target_summary = request.env['sales.route.sku.target.performance'].sudo().dashboard_summary(
                    user_ids=[request.env.user.id], route_ids=[current_plan.route_id.id] if current_plan and current_plan.route_id else [],
                    date_from=selected_from, date_to=selected_to, limit=6
                )
            except Exception:
                sku_target_summary = {}
        # Route coverage metrics for field staff and managers.
        # They compare today's actual execution against the full assigned route customer base,
        # not only the clients selected on today's plan.
        route = current_plan.route_id if current_plan and current_plan.route_id else False
        route_client_domain = [('customer_rank', '>', 0), ('route_id', '=', route.id)] if route else [('id', '=', 0)]
        route_clients = request.env['res.partner'].sudo().search(route_client_domain)
        route_client_total = len(route_clients)
        start_dt = datetime.combine(today, time.min)
        end_dt = start_dt + timedelta(days=1)
        visit_domain = [
            ('partner_id', 'in', route_clients.ids or [0]),
            '|',
                '&', ('check_in', '>=', fields.Datetime.to_string(start_dt)), ('check_in', '<', fields.Datetime.to_string(end_dt)),
                '&', ('check_out', '>=', fields.Datetime.to_string(start_dt)), ('check_out', '<', fields.Datetime.to_string(end_dt)),
        ]
        if current_plan and current_plan.user_id:
            visit_domain.append(('user_id', '=', current_plan.user_id.id))
        visited_partner_ids = set(request.env['sales.route.visit'].sudo().search(visit_domain).mapped('partner_id').ids)
        sale_domain = [
            ('partner_id', 'in', route_clients.ids or [0]),
            ('date_order', '>=', fields.Datetime.to_string(start_dt)),
            ('date_order', '<', fields.Datetime.to_string(end_dt)),
            ('state', '!=', 'cancel'),
        ]
        if current_plan and current_plan.user_id:
            sale_domain.append(('user_id', '=', current_plan.user_id.id))
        purchased_partner_ids = set(request.env['sale.order'].sudo().search(sale_domain).mapped('partner_id').ids)
        visited_route_clients = len(visited_partner_ids)
        purchased_route_clients = len(purchased_partner_ids)

        # v8.4 Modern Experience: lightweight sales intelligence for the next client.
        suggested_products = []
        client_health = 'No client selected'
        client_health_level = 'neutral'
        next_best_actions = []
        if next_line and next_line.partner_id:
            partner = next_line.partner_id
            last_orders = request.env['sale.order'].sudo().search([
                ('partner_id', '=', partner.id), ('state', '!=', 'cancel')
            ], order='date_order desc', limit=5)
            product_counter = {}
            for order in last_orders:
                for sol in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
                    product_counter[sol.product_id.display_name] = product_counter.get(sol.product_id.display_name, 0.0) + sol.product_uom_qty
            suggested_products = [
                {'name': name, 'qty': qty} for name, qty in sorted(product_counter.items(), key=lambda x: x[1], reverse=True)[:5]
            ]
            days = partner.days_since_last_purchase or 0
            if not last_orders:
                client_health = 'New / never bought'
                client_health_level = 'warning'
                next_best_actions.append('Introduce the catalogue/program and capture decision-maker contact.')
            elif days >= 30:
                client_health = 'Dormant customer'
                client_health_level = 'danger'
                next_best_actions.append('Ask why they stopped buying and offer a reorder from previous purchases.')
            elif days >= 14:
                client_health = 'At risk'
                client_health_level = 'warning'
                next_best_actions.append('Follow up on reorder opportunity before competitor supply.')
            else:
                client_health = 'Active buyer'
                client_health_level = 'success'
                next_best_actions.append('Confirm stock levels and suggest replenishment.')
            if suggested_products:
                next_best_actions.append('Suggested reorder: ' + ', '.join([p['name'] for p in suggested_products[:3]]))
            if partner.credit and partner.credit > 0:
                next_best_actions.append('Check outstanding balance before extending more credit.')

        # v8.6 Smart Alerts: concise, user-facing alerts for field users.
        smart_alerts = []
        if not current_plan:
            smart_alerts.append({'level': 'warning', 'message': 'No route plan for today. Create or auto-plan your day.'})
        elif current_plan.state in ('draft',):
            smart_alerts.append({'level': 'warning', 'message': 'Route plan is still draft. Submit it for approval.'})
        elif current_plan.total_planned_calls and current_plan.checked_in_calls < current_plan.total_planned_calls:
            remaining = current_plan.total_planned_calls - current_plan.checked_in_calls
            smart_alerts.append({'level': 'info', 'message': '%s planned client(s) still pending today.' % remaining})
        if purchased_route_clients < visited_route_clients and visited_route_clients:
            smart_alerts.append({'level': 'warning', 'message': '%s visited client(s) have not purchased yet.' % (visited_route_clients - purchased_route_clients)})
        if target_cards.get('personal_targets'):
            worst = min(target_cards.get('personal_targets'), key=lambda t: t.get('progress', 0))
            if worst.get('progress', 0) < 50:
                smart_alerts.append({'level': 'warning', 'message': 'Target progress is below 50 percent for %s.' % (worst.get('name') or 'current target')})

        # Scope My Field Work KPIs to the logged-in salesperson only.
        # Quick Sales Orders are assigned to sale.order.user_id and the generated
        # sales.route.visit.user_id, so this must use the logged-in salesperson
        # directly instead of a plan-only variable.
        visible_user_ids = [request.env.user.id]
        period_kpis = self._kpi_period_values(user_ids=visible_user_ids, date_from=date_from, date_to=date_to)
        fmcg_metrics = self._fsrp_fmcg_period_metrics(user_ids=visible_user_ids, date_from=date_from, date_to=date_to)

        # Lightweight Daily Morning Briefing AI for My Field Work.
        # This uses already-computed dashboard values and small indexed counts so
        # the salesperson dashboard opens quickly and defaults to today.
        yesterday = today - timedelta(days=1)
        missed_yesterday = 0
        if 'sales.route.plan.line' in request.env.registry:
            try:
                missed_yesterday = request.env['sales.route.plan.line'].sudo().search_count([
                    ('user_id', '=', request.env.user.id),
                    ('plan_date', '=', yesterday),
                    ('status', 'in', ['pending', 'missed']),
                ])
            except Exception:
                missed_yesterday = 0

        target_gap = 0.0
        sku_gap = 0.0
        try:
            personal = target_cards.get('personal_targets', []) or []
            if personal:
                best_progress = max([float(t.get('progress') or 0.0) for t in personal] or [0.0])
                target_gap = max(0.0, round(100.0 - best_progress, 1))
        except Exception:
            target_gap = 0.0
        try:
            sku_rows = sku_target_summary.get('rows') or sku_target_summary.get('items') or []
            if sku_rows:
                avg_sku = sum([float(r.get('achievement') or r.get('achievement_percent') or r.get('progress') or 0.0) for r in sku_rows]) / max(len(sku_rows), 1)
                sku_gap = max(0.0, round(100.0 - avg_sku, 1))
        except Exception:
            sku_gap = 0.0

        briefing_points = []
        if current_plan:
            briefing_points.append('%s clients planned for today on %s.' % (current_plan.total_planned_calls or 0, route.name if route else 'your route'))
        else:
            briefing_points.append('No approved route plan is active today. Create your route plan early.')
        if missed_yesterday:
            briefing_points.append('%s client(s) were missed yesterday and need recovery.' % missed_yesterday)
        if target_gap:
            briefing_points.append('Target gap is %s%% for the active target period.' % target_gap)
        if sku_gap:
            briefing_points.append('SKU/category target gap is about %s%%.' % sku_gap)
        if (period_kpis or {}).get('today_amount_due'):
            briefing_points.append('Follow up today amount due: %s.' % ((period_kpis or {}).get('today_amount_due_fmt') or period_kpis.get('today_amount_due')))
        if not briefing_points:
            briefing_points.append('Start early, cover assigned clients, and prioritize productive calls.')

        if missed_yesterday or target_gap >= 50 or sku_gap >= 50:
            briefing_tone = 'warning'
            briefing_recommendation = 'Recover missed clients first, focus high-value outlets, and push weak product categories.'
        elif current_plan and current_plan.total_planned_calls:
            briefing_tone = 'success'
            briefing_recommendation = 'Follow today’s route sequence and keep every visit productive and settled.'
        else:
            briefing_tone = 'info'
            briefing_recommendation = 'Create your route plan, then start visits from the highest priority customers.'

        morning_briefing = {
            'title': 'Good Morning %s' % (request.env.user.name or 'Salesperson'),
            'subtitle': 'Today’s AI field briefing',
            'tone': briefing_tone,
            'route': route.name if route else 'No route selected',
            'planned_clients': current_plan.total_planned_calls if current_plan else 0,
            'missed_yesterday': missed_yesterday,
            'target_gap': target_gap,
            'sku_gap': sku_gap,
            'points': briefing_points[:5],
            'recommendation': briefing_recommendation,
        }

        employee = request.env['hr.employee'].sudo().search([('user_id', '=', request.env.user.id)], limit=1) if 'hr.employee' in request.env.registry else request.env['hr.employee']
        employee_photo_url = '/web/image/hr.employee/%s/image_128' % employee.id if employee else '/web/image/res.users/%s/avatar_128' % request.env.user.id

        license_info = request.env['sales.route.license'].sudo().get_license_info()
        return {
            'user': {'id': request.env.user.id, 'name': request.env.user.name, 'employee_id': employee.id if employee else False, 'photo_url': employee_photo_url},
            'today': str(today),
            'login_datetime': fields.Datetime.context_timestamp(request.env.user, request.env.user.login_date or fields.Datetime.now()).strftime('%d %b %Y %I:%M %p'),
            'license': license_info,
            'can_quick_sale_unrestricted': request.env.user.has_group('field_sales_route_plan.group_field_sales_quick_sale_unrestricted'),
            'plan_id': current_plan.id if current_plan else False,
            'plan_name': current_plan.name if current_plan else '',
            'auto_assigned': bool(current_plan.auto_assigned) if current_plan else False,
            'accepted_by_salesperson': bool(current_plan.accepted_by_salesperson) if current_plan else False,
            'assignment_reason': current_plan.assignment_reason if current_plan else '',
            'route': route.name if route else '',
            'planned': current_plan.total_planned_calls if current_plan else 0,
            'visited': current_plan.checked_in_calls if current_plan else 0,
            'productive': current_plan.productive_calls if current_plan else 0,
            # Route & Device Overview shows today's Route Visit POS Order total,
            # not Sales Order value, so it matches field POS conversion output.
            'sales': period_kpis.get('today_pos_order_total_fmt') or self._money_fmt(0.0),
            'today_pos_order_total_fmt': period_kpis.get('today_pos_order_total_fmt') or self._money_fmt(0.0),
            'route_client_total': route_client_total,
            'visited_route_clients': visited_route_clients,
            'visited_route_percent': round((visited_route_clients / route_client_total * 100.0) if route_client_total else 0.0, 1),
            'purchased_route_clients': purchased_route_clients,
            'purchased_route_percent': round((purchased_route_clients / route_client_total * 100.0) if route_client_total else 0.0, 1),
            'next_client': next_line.partner_id.display_name if next_line else '',
            'next_line_id': next_line.id if next_line else False,
            'next_partner_id': next_line.partner_id.id if next_line and next_line.partner_id else False,
            'next_status': next_line.status if next_line else '',
            'client_health': client_health,
            'client_health_level': client_health_level,
            'suggested_products': suggested_products,
            'next_best_actions': next_best_actions,
            'smart_alerts': smart_alerts,
            'live_kpis': {
                'visit_percent': round((current_plan.checked_in_calls / current_plan.total_planned_calls * 100.0) if current_plan and current_plan.total_planned_calls else 0.0, 1),
                'productive_percent': round(current_plan.kpi_achievement if current_plan else 0.0, 1),
                'target_percent': max([t.get('progress', 0) for t in target_cards.get('personal_targets', [])] or [0]),
                'pos_settled_percent': round(((request.env['sales.route.visit'].sudo().search_count([('plan_id','=',current_plan.id), ('pos_settlement_status','=','settled')]) / max(current_plan.checked_in_calls, 1)) * 100.0) if current_plan else 0.0, 1),
            },
            'personal_targets': target_cards.get('personal_targets', []),
            'period_kpis': period_kpis,
            'fmcg_metrics': fmcg_metrics,
            'sku_target_summary': sku_target_summary,
            'morning_briefing': morning_briefing,
        }

    @http.route('/field_sales/simple_mode/auto_plan', type='json', auth='user', methods=['POST'])
    def simple_mode_auto_plan(self, max_clients=15):
        return {'ok': False, 'error': 'Auto route generation has been disabled. Please create a route plan manually.'}

    @http.route('/field_sales/simple_mode/accept_auto_route', type='json', auth='user', methods=['POST'])
    def simple_mode_accept_auto_route(self, plan_id=None):
        today = fields.Date.context_today(request.env.user)
        domain = [('plan_date', '=', today), ('user_id', '=', request.env.user.id), ('auto_assigned', '=', True), ('state', '!=', 'cancelled')]
        plan = request.env['sales.route.plan'].browse(int(plan_id)).exists() if plan_id else request.env['sales.route.plan']
        if not plan:
            plan = request.env['sales.route.plan'].search(domain, order='id desc', limit=1)
        if not plan or plan.user_id.id != request.env.user.id:
            return {'ok': False, 'error': 'No auto generated route plan found for you today.'}
        try:
            plan.action_accept_auto_route()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        return {
            'ok': True,
            'message': "You have accepted today's auto generated route plan.",
            'action': plan.action_start_my_day(),
        }

    @http.route('/field_sales/simple_mode/create_own_route', type='json', auth='user', methods=['POST'])
    def simple_mode_create_own_route(self, plan_id=None):
        today = fields.Date.context_today(request.env.user)
        plan = request.env['sales.route.plan'].browse(int(plan_id)).exists() if plan_id else request.env['sales.route.plan']
        if not plan:
            plan = request.env['sales.route.plan'].search([('plan_date', '=', today), ('user_id', '=', request.env.user.id), ('auto_assigned', '=', True), ('state', '!=', 'cancelled')], order='id desc', limit=1)
        if not plan or plan.user_id.id != request.env.user.id:
            return {'ok': False, 'error': 'No auto generated route plan found for you today.'}
        try:
            action = plan.action_create_own_route_instead()
        except Exception as e:
            return {'ok': False, 'error': str(e)}
        return {'ok': True, 'action': action}

    @http.route('/field_sales/simple_mode/start', type='json', auth='user', methods=['POST'])
    def simple_mode_start(self, plan_id=None):
        today = fields.Date.context_today(request.env.user)
        Plan = request.env['sales.route.plan']
        plan = Plan.browse(int(plan_id)).exists() if plan_id else Plan.search([('plan_date', '=', today), ('user_id', '=', request.env.user.id)], order='id desc', limit=1)
        if not plan:
            return {'ok': False, 'error': 'No route plan found for today.'}
        return {'ok': True, 'action': plan.action_start_my_day()}

    @http.route('/field_sales/simple_mode/next', type='json', auth='user', methods=['POST'])
    def simple_mode_next(self, plan_id=None):
        return self.simple_mode_start(plan_id=plan_id)

    def _route_productive_usage_values(self, user_ids=None, route_ids=None, date_from=None, date_to=None):
        """Selected-period route usage by salesperson.

        Counts route achievement by unique clients with at least one successful
        productive call in the selected period.  Repeat productive calls to the
        same client remain visible as attempts but do not inflate the achieved
        client count.
        """
        bounds = self._local_dt_bounds(date_from=date_from, date_to=date_to)
        start_dt = bounds['selected_start']
        end_dt = bounds['selected_end']
        Route = request.env['sales.route'].sudo()
        Partner = request.env['res.partner'].sudo()
        Visit = request.env['sales.route.visit'].sudo()
        domain = [('active', '=', True)]
        if route_ids:
            domain.append(('id', 'in', route_ids))
        routes = Route.search(domain, order='name')
        allowed_user_ids = set(user_ids or []) if user_ids else None
        rows_by_key = {}
        route_client_counts = {}
        for route in routes:
            route_client_counts[route.id] = Partner.search_count([('route_id', '=', route.id), ('active', '=', True)])
            users = route.user_ids | route.user_id
            for user in users:
                if not user:
                    continue
                if allowed_user_ids is not None and user.id not in allowed_user_ids:
                    continue
                key = (route.id, user.id)
                rows_by_key[key] = {
                    'route': route.name,
                    'salesperson': user.name,
                    'route_clients': route_client_counts[route.id],
                    'productive_clients': 0,
                    'productive_attempts': 0,
                    'achievement': 0.0,
                    'performance': '0/%s' % route_client_counts[route.id],
                    'period': bounds['selected_label'],
                }
        visit_domain = [
            ('check_in', '>=', start_dt),
            ('check_in', '<', end_dt),
            ('check_in', '!=', False),
            ('partner_id', '!=', False),
            '|', ('sale_order_total_amount', '>', 0), ('pos_order_total_amount', '>', 0),
        ]
        if route_ids:
            visit_domain.append(('route_id', 'in', route_ids))
        elif routes:
            visit_domain.append(('route_id', 'in', routes.ids))
        if user_ids:
            visit_domain.append(('user_id', 'in', user_ids))
        clients_by_key = {}
        attempts_by_key = {}
        for visit in Visit.search(visit_domain, order='check_in asc, id asc'):
            key = (visit.route_id.id, visit.user_id.id)
            if key not in rows_by_key:
                route_clients = route_client_counts.get(visit.route_id.id) or Partner.search_count([('route_id', '=', visit.route_id.id), ('active', '=', True)])
                rows_by_key[key] = {
                    'route': visit.route_id.name,
                    'salesperson': visit.user_id.name,
                    'route_clients': route_clients,
                    'productive_clients': 0,
                    'productive_attempts': 0,
                    'achievement': 0.0,
                    'performance': '0/%s' % route_clients,
                    'period': bounds['selected_label'],
                }
            clients_by_key.setdefault(key, set()).add(visit.partner_id.id)
            attempts_by_key[key] = attempts_by_key.get(key, 0) + 1
        for key, row in rows_by_key.items():
            unique_clients = len(clients_by_key.get(key, set()))
            route_clients = row.get('route_clients') or 0
            row['productive_clients'] = unique_clients
            row['productive_attempts'] = attempts_by_key.get(key, 0)
            row['achievement'] = round((unique_clients / route_clients) * 100.0, 2) if route_clients else 0.0
            row['performance'] = '%s/%s' % (unique_clients, route_clients)
        return sorted(rows_by_key.values(), key=lambda r: (r['route'], r['salesperson']))

    @http.route('/field_sales/manager_panel/data', type='json', auth='user', methods=['POST'])
    def manager_panel_data(self, route_id=None, date_from=None, date_to=None):
        bounds = self._local_dt_bounds(date_from=date_from, date_to=date_to)
        today = bounds['today']
        selected_from = bounds['selected_from']
        selected_to = bounds['selected_to']
        start_dt = datetime.combine(selected_from, time.min)
        end_dt = datetime.combine(selected_to + timedelta(days=1), time.min)
        route_id = int(route_id or 0)
        visible_route_ids = self._visible_route_ids()
        scoped_route_ids = [route_id] if route_id else visible_route_ids
        # For managers on upgraded databases, do not force an empty route/user
        # scope. Old figures may exist in Sale Orders/POS Orders before route links
        # were introduced. Supervisors remain restricted to their assigned routes.
        if scoped_route_ids:
            route_domain = [('route_id', 'in', scoped_route_ids)]
        elif self._is_field_sales_manager():
            route_domain = []
            scoped_route_ids = None
        else:
            route_domain = [('id', '=', 0)]
        visible_user_ids = self._users_for_route_ids(scoped_route_ids or [])
        if visible_user_ids:
            user_domain = [('user_id', 'in', visible_user_ids)]
            kpi_user_ids = visible_user_ids
        elif self._is_field_sales_manager():
            user_domain = []
            kpi_user_ids = None
        else:
            user_domain = [('id', '=', 0)]
            kpi_user_ids = []
        plans = request.env['sales.route.plan'].sudo().search([('plan_date', '>=', selected_from), ('plan_date', '<=', selected_to)] + route_domain + user_domain)
        visits = request.env['sales.route.visit'].sudo().search([
            '|', '&', ('check_in', '>=', fields.Datetime.to_string(start_dt)), ('check_in', '<', fields.Datetime.to_string(end_dt)),
                 '&', ('check_out', '>=', fields.Datetime.to_string(start_dt)), ('check_out', '<', fields.Datetime.to_string(end_dt)),
        ] + route_domain + user_domain)
        sales_total = sum(plans.mapped('total_sales_amount'))
        active = visits.filtered(lambda v: v.state == 'checked_in')
        settled = visits.filtered(lambda v: v.pos_settlement_status == 'settled')
        reps = []
        # Include users from both plans and actual visits so Quick Sales-only
        # activity is visible in the Manager Control Panel immediately.
        for user in (plans.mapped('user_id') | visits.mapped('user_id')):
            ups = plans.filtered(lambda p: p.user_id == user)
            uvisits = visits.filtered(lambda v: v.user_id == user)
            sales_value = sum(uvisits.mapped('sale_order_total_amount')) or sum(ups.mapped('total_sales_amount'))
            pos_order_total = sum(uvisits.mapped('pos_order_total_amount'))
            pos_paid = sum(uvisits.mapped('pos_order_paid_amount'))
            if not pos_paid:
                pos_paid = sum(uvisits.mapped('pos_order_payment_amount'))
            pos_due = sum(uvisits.mapped('pos_order_due_amount'))
            reps.append({
                'user': user.name,
                'route': ', '.join((ups.mapped('route_id') | uvisits.mapped('route_id')).mapped('name')),
                'planned': sum(ups.mapped('total_planned_calls')),
                'visited': len(uvisits),
                'productive': len(uvisits.filtered(lambda v: v.sale_order_total_amount or v.pos_order_total_amount or v.state in ('checked_out', 'done'))),
                'sales': sales_value,
                'sales_fmt': self._money_fmt(sales_value),
                'pos_order_total': pos_order_total,
                'pos_order_total_fmt': self._money_fmt(pos_order_total),
                'pos_paid': pos_paid,
                'pos_paid_fmt': self._money_fmt(pos_paid),
                'pos_due': pos_due,
                'pos_due_fmt': self._money_fmt(pos_due),
            })
        target_cards = request.env['sales.route.target'].sudo().fsrp_target_cards(
            user=request.env.user,
            route=False,
            limit=12,
        ) if 'sales.route.target' in request.env.registry else {'group_targets': []}
        device_records = request.env['sales.route.device.status'].sudo().search([], order='alert_level desc, last_seen desc', limit=50) if 'sales.route.device.status' in request.env.registry else request.env['res.users'].browse([])
        device_alerts = []
        for ds in device_records.filtered(lambda r: r.alert_level != '0_ok')[:10]:
            device_alerts.append({
                'user': ds.user_id.name,
                'route': ds.route_id.name or '',
                'level': ds.alert_level,
                'message': ds.alert_message or '',
                'battery': ds.battery_level,
                'network': ds.network_status,
                'last_seen': str(ds.last_seen or ''),
                'ack': ds.alert_acknowledged,
            })
        period_kpis = self._kpi_period_values(user_ids=kpi_user_ids, route_ids=scoped_route_ids, date_from=date_from, date_to=date_to)
        fmcg_metrics = self._fsrp_fmcg_period_metrics(user_ids=kpi_user_ids, route_ids=scoped_route_ids or [], date_from=date_from, date_to=date_to)
        sku_target_summary = {}
        if 'sales.route.sku.target.performance' in request.env.registry:
            # Fast dashboard: read cached SKU target snapshots. Refresh only active selected-period targets,
            # which keeps the default Today panel quick while still allowing period analysis.
            try:
                request.env['sales.route.sku.target.performance'].sudo().recompute_for_targets(date_from=selected_from, date_to=selected_to, limit=120)
            except Exception:
                pass
            sku_target_summary = request.env['sales.route.sku.target.performance'].sudo().dashboard_summary(
                user_ids=kpi_user_ids, route_ids=scoped_route_ids, date_from=selected_from, date_to=selected_to, limit=10
            )
        license_info = request.env['sales.route.license'].sudo().get_license_info()
        performance_sections = self._management_performance_sections()
        return {
            'panel_title': 'Manager Control Panel' if self._is_field_sales_manager() else 'Supervisor Control Panel',
            'today': str(today),
            'selected_from': str(selected_from),
            'selected_to': str(selected_to),
            'selected_label': bounds['selected_label'],
            # Count selected-period live visit/order activity directly so Quick Sales
            # Orders show immediately, even before full route-plan KPI recompute.
            'planned': sum(plans.mapped('total_planned_calls')),
            'visited': len(visits),
            'productive': len(visits.filtered(lambda v: v.sale_order_total_amount or v.pos_order_total_amount or v.state in ('checked_out', 'done'))),
            'sales': period_kpis.get('selected_sales', sales_total),
            'active_count': len(active),
            'settled_count': len(settled),
            'not_settled_count': len(visits) - len(settled),
            'device_critical_count': len(device_records.filtered(lambda r: r.alert_level == '2_critical')) if 'sales.route.device.status' in request.env.registry else 0,
            'device_warning_count': len(device_records.filtered(lambda r: r.alert_level == '1_warning')) if 'sales.route.device.status' in request.env.registry else 0,
            'device_alerts': device_alerts,
            'active_visits': [{'client': v.partner_id.display_name, 'salesperson': v.user_id.name, 'route': v.route_id.name, 'check_in': str(v.check_in or '')} for v in active[:20]],
            'reps': reps,
            'group_targets': target_cards.get('group_targets', []),
            'period_kpis': period_kpis,
            'fmcg_metrics': fmcg_metrics,
            'sku_target_summary': sku_target_summary,
            'license': license_info,
            'manager_performance': performance_sections.get('manager_performance', []),
            'supervisor_performance': performance_sections.get('supervisor_performance', []),
            'salesperson_performance': performance_sections.get('salesperson_performance', []),
            'assigned_routes': performance_sections.get('assigned_routes', []),
            'route_productive_usage': self._route_productive_usage_values(user_ids=kpi_user_ids, route_ids=scoped_route_ids, date_from=date_from, date_to=date_to),
        }


    @http.route('/field_sales/sales_assistant/context', type='json', auth='user', methods=['POST'])
    def sales_assistant_context(self, partner_id=None, visit_id=None):
        """Rule-based AI-like sales assistant context.

        This is intentionally local and fast: it uses Odoo sales history,
        ageing, outstanding balance and route context without external APIs.
        """
        partner = request.env['res.partner'].sudo().browse(int(partner_id or 0)).exists() if partner_id else request.env['res.partner']
        visit = request.env['sales.route.visit'].sudo().browse(int(visit_id or 0)).exists() if visit_id else request.env['sales.route.visit']
        if not partner and visit:
            partner = visit.partner_id
        if not partner:
            return {'ok': False, 'error': 'No client selected.'}
        orders = request.env['sale.order'].sudo().search([('partner_id', '=', partner.id), ('state', '!=', 'cancel')], order='date_order desc', limit=8)
        product_counter = {}
        total_spend = 0.0
        for order in orders:
            total_spend += order.amount_total
            for line in order.order_line.filtered(lambda l: not l.display_type and l.product_id):
                key = line.product_id.display_name
                product_counter[key] = product_counter.get(key, 0.0) + line.product_uom_qty
        top_products = [{'name': k, 'qty': round(v, 2)} for k, v in sorted(product_counter.items(), key=lambda i: i[1], reverse=True)[:6]]
        days = partner.days_since_last_purchase or 0
        messages = []
        if not orders:
            messages.append('New or never-bought client: focus on catalogue/program introduction and decision-maker capture.')
        elif days >= 30:
            messages.append('Dormant client: ask why they stopped buying and offer a reorder from previous products.')
        elif days >= 14:
            messages.append('At-risk client: follow up before competitor replenishment.')
        else:
            messages.append('Active buyer: confirm stock levels and propose top-up order.')
        if top_products:
            messages.append('Suggested reorder products: %s.' % ', '.join([p['name'] for p in top_products[:3]]))
        if partner.credit and partner.credit > 0:
            messages.append('Outstanding balance exists: confirm payment or credit approval before large order.')
        return {
            'ok': True,
            'client': partner.display_name,
            'health': 'Dormant' if days >= 30 else ('At Risk' if days >= 14 else ('New' if not orders else 'Active')),
            'days_since_last_purchase': days,
            'total_recent_spend': round(total_spend, 2),
            'top_products': top_products,
            'messages': messages,
        }

    @http.route('/field_sales/live_team_map/data', type='json', auth='user', methods=['POST'])
    def live_team_map_data(self):
        """Return active team positions based on today's checked-in visits."""
        if not (request.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') or request.env.user.has_group('sales_team.group_sale_manager')):
            return {'ok': False, 'error': 'Supervisor access required.', 'members': []}
        today = fields.Date.context_today(request.env.user)
        start_dt = datetime.combine(today, time.min)
        end_dt = start_dt + timedelta(days=1)
        visits = request.env['sales.route.visit'].sudo().search([
            ('check_in', '>=', fields.Datetime.to_string(start_dt)),
            ('check_in', '<', fields.Datetime.to_string(end_dt)),
            ('checkin_latitude', '!=', 0),
            ('checkin_longitude', '!=', 0),
        ], order='check_in desc', limit=300)
        seen = set()
        members = []
        for v in visits:
            if v.user_id.id in seen:
                continue
            seen.add(v.user_id.id)
            members.append({
                'user': v.user_id.name,
                'client': v.partner_id.display_name,
                'route': v.route_id.name,
                'state': v.state,
                'latitude': v.checkin_latitude,
                'longitude': v.checkin_longitude,
                'check_in': str(v.check_in or ''),
                'address': v.checkin_address or v.checkin_place or '',
            })
        return {'ok': True, 'members': members}

    @http.route('/field_sales/device/status', type='json', auth='user', methods=['POST'])
    def field_sales_device_status(self, **payload):
        """Store latest field user device status from browser/PWA.

        Browser support varies:
        - Battery is available only where the Battery Status API is supported.
        - Exact mobile data usage is not exposed by browsers; we store connection
          quality indicators such as effective type, downlink, RTT and data saver.
        """
        try:
            rec = request.env['sales.route.device.status'].create_or_update_from_payload(payload or {})
            return {
                'ok': True,
                'id': rec.id,
                'battery_level': rec.battery_level,
                'battery_status': rec.battery_status,
                'network_status': rec.network_status,
                'alert_level': rec.alert_level,
                'alert_message': rec.alert_message,
                'last_seen': str(rec.last_seen or ''),
            }
        except Exception as error:
            return {'ok': False, 'error': str(error)}

    @http.route('/field_sales/device/my_status', type='json', auth='user', methods=['POST'])
    def field_sales_my_device_status(self):
        rec = request.env['sales.route.device.status'].sudo().search([('user_id', '=', request.env.user.id)], order='last_seen desc', limit=1)
        if not rec:
            return {'ok': True, 'status': {}}
        return {
            'ok': True,
            'status': {
                'battery_level': rec.battery_level,
                'battery_status': rec.battery_status,
                'battery_charging': rec.battery_charging,
                'network_online': rec.network_online,
                'network_status': rec.network_status,
                'effective_type': rec.effective_type,
                'downlink_mbps': rec.downlink_mbps,
                'rtt_ms': rec.rtt_ms,
                'save_data': rec.save_data,
                'alert_level': rec.alert_level,
                'alert_message': rec.alert_message,
                'minutes_since_seen': rec.minutes_since_seen,
                'last_seen': str(rec.last_seen or ''),
            }
        }
