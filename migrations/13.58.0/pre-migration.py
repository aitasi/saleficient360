# -*- coding: utf-8 -*-


def migrate(cr, version):
    """Run before Odoo module data cleanup on upgrade.

    Older experimental VAN/FMCG builds left ir.model.fields.selection XML ids
    attached to fields that are now Char fields. During upgrade Odoo tries to
    unlink those stale selection values and crashes with:
    AttributeError: 'Char' object has no attribute 'ondelete'.
    """
    # Remove stale selection XML ids for this module before _process_end.
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'field_sales_route_plan'
           AND model = 'ir.model.fields.selection'
    """)

    # Remove invalid selection rows: rows whose field no longer exists or whose
    # field is not a Selection field anymore.
    cr.execute("""
        DELETE FROM ir_model_fields_selection s
         WHERE NOT EXISTS (SELECT 1 FROM ir_model_fields f WHERE f.id = s.field_id)
            OR EXISTS (SELECT 1 FROM ir_model_fields f WHERE f.id = s.field_id AND f.ttype <> 'selection')
    """)

    # Remove stale VAN/FMCG XML ids and views before validation/end cleanup.
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'field_sales_route_plan'
           AND (name ILIKE '%%van%%'
                OR name ILIKE '%%fmcg%%'
                OR name ILIKE '%%distributor%%'
                OR name ILIKE '%%trade_asset%%'
                OR name ILIKE '%%collection%%')
    """)
    cr.execute("""
        DELETE FROM ir_ui_view
         WHERE arch_db::text ILIKE '%%van_ids%%'
            OR arch_db::text ILIKE '%%van_id%%'
            OR arch_db::text ILIKE '%%VAN%%'
            OR arch_db::text ILIKE '%%fmcg%%'
            OR arch_db::text ILIKE '%%FMCG%%'
    """)

    # Leave DB columns in place, but remove stale model field metadata from
    # removed experimental features so Odoo stops trying to manage them.
    removed_models = (
        'sales.route.distributor.depot', 'sales.route.trade.promotion',
        'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load',
        'sales.route.van.load.line', 'sales.route.van.dashboard',
        'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
        'sales.route.van.return', 'sales.route.van.return.line',
        'sales.route.fmcg.forecast', 'sales.route.team.leaderboard',
        'sales.route.executive.fmcg.cockpit', 'sales.route.distributor.purchase.order',
        'sales.route.distributor.purchase.order.line', 'sales.route.distributor.financial.dashboard',
        'sales.route.fmcg.kpi.engine', 'sales.route.collection.management',
        'sales.route.trade.asset', 'sales.route.trade.asset.audit',
    )
    cr.execute("DELETE FROM ir_actions_act_window WHERE res_model = ANY(%s)", (list(removed_models),))
    cr.execute("DELETE FROM ir_rule WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))", (list(removed_models),))
    cr.execute("DELETE FROM ir_model_access WHERE model_id IN (SELECT id FROM ir_model WHERE model = ANY(%s))", (list(removed_models),))
    cr.execute("DELETE FROM ir_model_fields WHERE model = ANY(%s)", (list(removed_models),))
    cr.execute("DELETE FROM ir_model WHERE model = ANY(%s)", (list(removed_models),))
