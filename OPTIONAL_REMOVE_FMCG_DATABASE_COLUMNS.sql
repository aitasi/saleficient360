-- Optional cleanup only. Run after the module upgrades successfully if you want to remove leftover FMCG columns physically.
-- These columns are no longer used by the clean non-FMCG build.
ALTER TABLE res_partner DROP COLUMN IF EXISTS company_currency_id;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_outlet_type;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_outlet_grade;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_channel;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_shelf_size;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_cooler_available;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_competitor_presence;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_monthly_potential;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_credit_limit;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_last_profile_date;
ALTER TABLE res_partner DROP COLUMN IF EXISTS fmcg_profile_notes;
ALTER TABLE res_partner DROP COLUMN IF EXISTS outlet_grade;
ALTER TABLE res_partner DROP COLUMN IF EXISTS trade_channel;
