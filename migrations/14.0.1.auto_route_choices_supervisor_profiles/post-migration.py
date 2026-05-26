# -*- coding: utf-8 -*-


def migrate(cr, version):
    cr.execute("""
        ALTER TABLE res_partner
            ADD COLUMN IF NOT EXISTS fmcg_partner_type varchar,
            ADD COLUMN IF NOT EXISTS trade_channel varchar,
            ADD COLUMN IF NOT EXISTS distributor_id integer,
            ADD COLUMN IF NOT EXISTS depot_id integer,
            ADD COLUMN IF NOT EXISTS credit_limit_amount numeric,
            ADD COLUMN IF NOT EXISTS credit_hold boolean;
    """)
