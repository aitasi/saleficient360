-- Run this BEFORE upgrading if Odoo still crashes during module upgrade.
-- It removes stale selection metadata left by older VAN/FMCG experimental builds.

DELETE FROM ir_model_data
 WHERE module = 'field_sales_route_plan'
   AND model = 'ir.model.fields.selection';

DELETE FROM ir_model_fields_selection s
 WHERE NOT EXISTS (SELECT 1 FROM ir_model_fields f WHERE f.id = s.field_id)
    OR EXISTS (SELECT 1 FROM ir_model_fields f WHERE f.id = s.field_id AND f.ttype <> 'selection');

DELETE FROM ir_model_data
 WHERE module = 'field_sales_route_plan'
   AND (name ILIKE '%van%'
        OR name ILIKE '%fmcg%'
        OR name ILIKE '%distributor%'
        OR name ILIKE '%trade_asset%'
        OR name ILIKE '%collection%');

DELETE FROM ir_ui_view
 WHERE arch_db::text ILIKE '%van_ids%'
    OR arch_db::text ILIKE '%van_id%'
    OR arch_db::text ILIKE '%VAN%'
    OR arch_db::text ILIKE '%fmcg%'
    OR arch_db::text ILIKE '%FMCG%';
