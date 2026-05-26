-- Run this once in PostgreSQL if Odoo cannot even open Apps/Upgrade because of
-- ERROR: column res_partner.fmcg_partner_type does not exist
-- It is safe to run multiple times. Replace <your_database_name> as needed.

ALTER TABLE res_partner
    ADD COLUMN IF NOT EXISTS fmcg_partner_type varchar,
    ADD COLUMN IF NOT EXISTS trade_channel varchar,
    ADD COLUMN IF NOT EXISTS distributor_id integer,
    ADD COLUMN IF NOT EXISTS depot_id integer,
    ADD COLUMN IF NOT EXISTS credit_limit_amount numeric,
    ADD COLUMN IF NOT EXISTS credit_hold boolean;

ALTER TABLE res_users
    ADD COLUMN IF NOT EXISTS field_sales_supervisor_id integer,
    ADD COLUMN IF NOT EXISTS field_sales_manager_id integer,
    ADD COLUMN IF NOT EXISTS field_sales_effective_manager_id integer;

CREATE INDEX IF NOT EXISTS res_partner_fmcg_partner_type_idx ON res_partner(fmcg_partner_type);
CREATE INDEX IF NOT EXISTS res_partner_trade_channel_idx ON res_partner(trade_channel);
CREATE INDEX IF NOT EXISTS res_partner_distributor_id_idx ON res_partner(distributor_id);
CREATE INDEX IF NOT EXISTS res_partner_depot_id_idx ON res_partner(depot_id);
