-- Emergency cleanup for databases with stale VAN/FMCG view metadata from previous builds.
-- Run this only if Odoo cannot upgrade because views reference VAN/FMCG fields.

DELETE FROM ir_ui_view
 WHERE model IN ('sales.route','sales.route.plan','sales.route.visit','res.partner')
   AND (arch_db::text ILIKE '%van_%'
        OR arch_db::text ILIKE '%van_ids%'
        OR arch_db::text ILIKE '%VAN%'
        OR arch_db::text ILIKE '%fmcg%'
        OR arch_db::text ILIKE '%FMCG%');

DELETE FROM ir_model_data
 WHERE module = 'field_sales_route_plan'
   AND (name ILIKE '%van%' OR name ILIKE '%fmcg%' OR name ILIKE '%distributor%'
        OR name ILIKE '%trade_asset%' OR name ILIKE '%collection%');
