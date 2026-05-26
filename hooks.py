# -*- coding: utf-8 -*-


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1
          FROM information_schema.columns
         WHERE table_name=%s AND column_name=%s
         LIMIT 1
    """, (table, column))
    return bool(cr.fetchone())


def _ensure_schema(cr):
    """Create compatibility columns before the ORM reads inherited models.

    Some live databases from earlier rebuilds contain ir.model.fields metadata for
    FMCG fields but the physical res_partner columns are missing. When Odoo reads
    users/partners during web client login or ir.rule evaluation it SELECTs those
    missing columns and crashes before normal module upgrade can complete. This
    helper is intentionally pure SQL and safe to run many times.
    """
    cr.execute("""
        ALTER TABLE res_users
            ADD COLUMN IF NOT EXISTS field_sales_supervisor_id integer,
            ADD COLUMN IF NOT EXISTS field_sales_manager_id integer,
            ADD COLUMN IF NOT EXISTS field_sales_effective_manager_id integer;
    """)
    cr.execute("CREATE INDEX IF NOT EXISTS res_users_field_sales_supervisor_id_idx ON res_users(field_sales_supervisor_id)")
    cr.execute("CREATE INDEX IF NOT EXISTS res_users_field_sales_manager_id_idx ON res_users(field_sales_manager_id)")
    cr.execute("CREATE INDEX IF NOT EXISTS res_users_field_sales_effective_manager_id_idx ON res_users(field_sales_effective_manager_id)")

    cr.execute("""
        ALTER TABLE res_partner
            ADD COLUMN IF NOT EXISTS fmcg_partner_type varchar,
            ADD COLUMN IF NOT EXISTS trade_channel varchar,
            ADD COLUMN IF NOT EXISTS distributor_id integer,
            ADD COLUMN IF NOT EXISTS depot_id integer,
            ADD COLUMN IF NOT EXISTS credit_limit_amount numeric,
            ADD COLUMN IF NOT EXISTS credit_hold boolean;
    """)
    cr.execute("CREATE INDEX IF NOT EXISTS res_partner_fmcg_partner_type_idx ON res_partner(fmcg_partner_type)")
    cr.execute("CREATE INDEX IF NOT EXISTS res_partner_trade_channel_idx ON res_partner(trade_channel)")
    cr.execute("CREATE INDEX IF NOT EXISTS res_partner_distributor_id_idx ON res_partner(distributor_id)")
    cr.execute("CREATE INDEX IF NOT EXISTS res_partner_depot_id_idx ON res_partner(depot_id)")


def pre_init_hook(cr):
    _ensure_schema(cr)
    return True


def post_init_hook(cr, registry):
    _ensure_schema(cr)
    return True
