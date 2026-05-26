-- Optional cleanup for databases that previously installed experimental VAN Sales builds.
-- Run only if you want to remove stale VAN Sales metadata after installing the clean Field Sales Core.
DELETE FROM ir_ui_menu WHERE name ILIKE '%VAN%';
DELETE FROM ir_actions_act_window WHERE res_model IN (
    'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
    'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
    'sales.route.van.return', 'sales.route.van.return.line'
);
DELETE FROM ir_ui_view WHERE model IN (
    'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
    'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
    'sales.route.van.return', 'sales.route.van.return.line'
);
DELETE FROM ir_model_access WHERE model_id IN (
    SELECT id FROM ir_model WHERE model IN (
        'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
        'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
        'sales.route.van.return', 'sales.route.van.return.line'
    )
);
DELETE FROM ir_rule WHERE model_id IN (
    SELECT id FROM ir_model WHERE model IN (
        'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
        'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
        'sales.route.van.return', 'sales.route.van.return.line'
    )
);
DELETE FROM ir_model_fields WHERE model IN ('sales.route.plan', 'sales.route')
AND name IN ('van_id','van_location_id','van_stock_status','van_load_id','van_load_state','van_reconciliation_id','van_reconciliation_state','van_ids');
DELETE FROM ir_model_fields WHERE model IN (
    'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
    'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
    'sales.route.van.return', 'sales.route.van.return.line'
);
DELETE FROM ir_model WHERE model IN (
    'sales.route.van', 'sales.route.van.stock.line', 'sales.route.van.load', 'sales.route.van.load.line',
    'sales.route.van.dashboard', 'sales.route.van.reconciliation', 'sales.route.van.reconciliation.line',
    'sales.route.van.return', 'sales.route.van.return.line'
);
