# -*- coding: utf-8 -*-


def migrate(cr, version):
    # Must run before registry/model reads for databases where field metadata
    # exists but SQL columns were not created by an earlier broken upgrade.
    cr.execute("""
        ALTER TABLE res_users
            ADD COLUMN IF NOT EXISTS field_sales_supervisor_id integer,
            ADD COLUMN IF NOT EXISTS field_sales_manager_id integer,
            ADD COLUMN IF NOT EXISTS field_sales_effective_manager_id integer;
    """)
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
