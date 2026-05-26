Migration-safe rebuild notes
============================

This package includes:
- pre_init_hook and post_init_hook schema repair
- Odoo migration scripts under migrations/
- RUN_THIS_SQL_ONCE_BEFORE_UPGRADE.sql for servers that crash before Apps can load

If your Odoo web client still crashes with `column res_partner.fmcg_partner_type does not exist`, run RUN_THIS_SQL_ONCE_BEFORE_UPGRADE.sql directly in PostgreSQL, restart Odoo, then upgrade this module.
