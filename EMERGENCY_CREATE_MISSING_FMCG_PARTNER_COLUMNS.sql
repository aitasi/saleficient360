-- Run only if your Odoo web client is locked by: column res_partner.fmcg_partner_type does not exist
ALTER TABLE res_partner
    ADD COLUMN IF NOT EXISTS fmcg_partner_type varchar,
    ADD COLUMN IF NOT EXISTS trade_channel varchar,
    ADD COLUMN IF NOT EXISTS distributor_id integer,
    ADD COLUMN IF NOT EXISTS depot_id integer,
    ADD COLUMN IF NOT EXISTS credit_limit_amount numeric,
    ADD COLUMN IF NOT EXISTS credit_hold boolean;
CREATE INDEX IF NOT EXISTS res_partner_fmcg_partner_type_idx ON res_partner(fmcg_partner_type);
CREATE INDEX IF NOT EXISTS res_partner_trade_channel_idx ON res_partner(trade_channel);
CREATE INDEX IF NOT EXISTS res_partner_distributor_id_idx ON res_partner(distributor_id);
CREATE INDEX IF NOT EXISTS res_partner_depot_id_idx ON res_partner(depot_id);
