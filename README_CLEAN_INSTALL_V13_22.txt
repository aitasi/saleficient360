Field Sales Route Plan v13.22 Clean Build

Install/upgrade notes:
1. Delete the old field_sales_route_plan folder completely from custom-addons.
2. Extract this ZIP and copy only the field_sales_route_plan folder.
3. Restart Odoo.
4. Upgrade the module from Apps.

This build removes the broken direct Team Hierarchy fields from res.users.
The hierarchy is now stored safely in sales.route.team.hierarchy.

If your database was already damaged by a previous failed upgrade and Odoo cannot start,
run EMERGENCY_REPAIR_BEFORE_RESTART.sql once in PostgreSQL, then restart Odoo and upgrade.


V13.23: Team hierarchy supports one Sales Manager with many Supervisors and one Supervisor with many Sales Persons. Use one hierarchy line per Sales Person; group the list by Manager and Supervisor for a clean view.
