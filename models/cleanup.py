from odoo import api, models


class SalesRouteCleanup(models.AbstractModel):
    _name = 'sales.route.cleanup'
    _description = 'Field Sales Cleanup Utilities'

    @api.model
    def cleanup_fmcg_artifacts(self):
        """Remove FMCG and VAN Sales artifacts left by earlier experimental builds.

        This keeps the Field Sales Core clean and prevents old menus/actions/views from pointing to models that no longer exist.
        """
        model_names = [
            'sales.route.distributor.depot',
            'sales.route.trade.promotion',
            'sales.route.van',
            'sales.route.van.stock.line',
            'sales.route.van.load',
            'sales.route.van.load.line',
            'sales.route.van.dashboard',
            'sales.route.van.reconciliation',
            'sales.route.van.reconciliation.line',
            'sales.route.van.return',
            'sales.route.van.return.line',
            'sales.route.fmcg.forecast',
            'sales.route.team.leaderboard',
            'sales.route.executive.fmcg.cockpit',
            'sales.route.distributor.purchase.order',
            'sales.route.distributor.purchase.order.line',
            'sales.route.distributor.financial.dashboard',
            'sales.route.fmcg.kpi.engine',
            'sales.route.collection.management',
            'sales.route.trade.asset',
            'sales.route.trade.asset.audit',
        ]

        van_route_field_names = [
            'van_id', 'van_location_id', 'van_stock_status', 'van_load_id', 'van_load_state',
            'van_reconciliation_id', 'van_reconciliation_state', 'van_ids',
        ]
        partner_field_names = [
            'company_currency_id', 'fmcg_outlet_type', 'fmcg_outlet_grade', 'fmcg_channel',
            'fmcg_shelf_size', 'fmcg_cooler_available', 'fmcg_competitor_presence',
            'fmcg_monthly_potential', 'fmcg_credit_limit', 'fmcg_last_profile_date',
            'fmcg_profile_notes', 'fmcg_asset_count', 'outlet_grade', 'trade_channel',
        ]
        # Remove menus first so no menu points to deleted actions.
        menus = self.env['ir.ui.menu'].sudo()
        stale_menus = menus.browse()
        for keyword in ['FMCG', 'Distributor', 'Trade Asset', 'Collection Management', 'VAN']:
            stale_menus |= menus.search([('name', 'ilike', keyword)])
        stale_menus.unlink()
        # Remove views/actions/rules/access for removed models.
        self.env['ir.ui.view'].sudo().search([('model', 'in', model_names)]).unlink()
        self.env['ir.actions.act_window'].sudo().search([('res_model', 'in', model_names)]).unlink()
        self.env['ir.rule'].sudo().search([('model_id.model', 'in', model_names)]).unlink()
        self.env['ir.model.access'].sudo().search([('model_id.model', 'in', model_names)]).unlink()
        # Remove XML IDs referencing common FMCG files/views if still present.
        imd = self.env['ir.model.data'].sudo()
        stale_xmlids = imd.browse()
        for keyword in ['fmcg', 'distributor', 'trade_asset', 'collection', 'van']:
            stale_xmlids |= imd.search([('module', '=', 'field_sales_route_plan'), ('name', 'ilike', keyword)])
        stale_xmlids.unlink()
        # Hide stale field definitions from Odoo metadata. Do not drop physical columns here.
        self.env.cr.execute("""
            DELETE FROM ir_model_fields
             WHERE (model IN %s)
                OR (model = 'res.partner' AND name = ANY(%s))
                OR (model IN ('sales.route.plan', 'sales.route') AND name = ANY(%s))
        """, (tuple(model_names), partner_field_names, van_route_field_names))
        self.env.cr.execute("DELETE FROM ir_model WHERE model IN %s", (tuple(model_names),))
        return True
