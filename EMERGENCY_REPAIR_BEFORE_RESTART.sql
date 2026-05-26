-- Run this in PostgreSQL only if Odoo cannot start because res_users.field_sales_supervisor_id is missing.
-- It immediately satisfies the old broken registry, then v13.18 removes direct res.users hierarchy fields from code.

ALTER TABLE res_users
    ADD COLUMN IF NOT EXISTS field_sales_supervisor_id integer,
    ADD COLUMN IF NOT EXISTS field_sales_manager_id integer,
    ADD COLUMN IF NOT EXISTS field_sales_effective_manager_id integer;

CREATE INDEX IF NOT EXISTS res_users_field_sales_supervisor_id_idx ON res_users(field_sales_supervisor_id);
CREATE INDEX IF NOT EXISTS res_users_field_sales_manager_id_idx ON res_users(field_sales_manager_id);
CREATE INDEX IF NOT EXISTS res_users_field_sales_effective_manager_id_idx ON res_users(field_sales_effective_manager_id);

-- Optional cleanup of stale model metadata after Odoo is upgraded successfully:
-- DELETE FROM ir_model_fields WHERE model='res.users' AND name IN ('field_sales_supervisor_id','field_sales_manager_id','field_sales_effective_manager_id','field_sales_salesperson_ids','field_sales_supervisor_ids');
