{
    'name': 'Field Sales Route Plan & GPS Tracking',
    'version': '16.0.3.0.0.mobile_kanban_fix',
    'summary': 'Enterprise FMCG commercial execution suite: route planning, quick sales, dashboards, depots, VAN sales, distributors, trade promotions, market impact workflows and Phase 3 enterprise intelligence.',
    'description': '''
Clean stable build with enterprise delivery fulfilment for Odoo 16 Community.

Core features retained:
- Market routes with multiple salespeople and primary salesperson compatibility.
- Customer-to-route mapping and automatic route assignment from salesperson/sales team.
- Daily route plans, approval workflow, planned visits and mobile-friendly quick planning.
- GPS check-in/check-out with inline same-page capture and place resolution.
- POS settlement tracking for sales orders, receipt number, POS total, paid and due values.
- Client map / heat map, route optimization, live navigation and team visibility.
- Delivery tracking with proof/signature.
- AI assistant, smart reminders, visit history timeline and smart recommendations.
- Merchandising audits, gamification, attendance tracking, executive dashboard and mobile UX.
- Three-level access hierarchy: Sales Person, Supervisor and Sales Manager.
- Phase 1 local licensing with trial and renewable time-based plans.

Removed from this clean build:
- Offline sync system.
- Collections.
- Geofence restrictions.
- PWA install/app shell.
- Board dashboard dependency.
    ''',
    'category': 'Sales/Sales',
    'author': 'AITASI',
    'license': 'LGPL-3',
    'depends': ['base', 'contacts', 'sale_management', 'mail', 'point_of_sale', 'hr', 'crm', ],
    'assets': {
        'web.assets_backend': [
            'field_sales_route_plan/static/src/js/route_sale_terminal.js',
            'field_sales_route_plan/static/src/js/route_client_map.js',
            'field_sales_route_plan/static/src/js/visit_inline_gps.js',
            'field_sales_route_plan/static/src/js/field_simple_mode.js',
            'field_sales_route_plan/static/src/js/manager_control_panel.js',
            'field_sales_route_plan/static/src/js/offline_queue.js',
            'field_sales_route_plan/static/src/js/dashboard_scroll_fix.js',
            'field_sales_route_plan/static/src/js/device_status.js',
            'field_sales_route_plan/static/src/xml/route_sale_terminal.xml',
            'field_sales_route_plan/static/src/xml/route_client_map.xml',
            'field_sales_route_plan/static/src/xml/field_simple_mode.xml',
            'field_sales_route_plan/static/src/xml/manager_control_panel.xml',
            'field_sales_route_plan/static/src/scss/route_sale_terminal.scss',
        ],
    },
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/sequence.xml',
                'data/call_reasons.xml',
        'data/visit_purposes.xml',
        'data/device_monitoring_cron.xml',
        'data/sku_target_performance_cron.xml',
        'report/pos_receipt_report.xml',
        'report/facilitation_report.xml',
        'views/res_partner_views.xml',
        'views/call_reason_views.xml',
        'views/visit_purpose_views.xml',
        'views/marketing_program_views.xml',
        'views/route_target_views.xml',
        'views/sku_target_performance_views.xml',
        'views/route_dashboard_views.xml',
        'views/team_hierarchy_views.xml',
        'views/device_status_views.xml',
        'views/ai_chat_views.xml',
        'views/merchandising_audit_views.xml',
        'views/smart_reminder_views.xml',
        'views/gamification_views.xml',
        'views/attendance_views.xml',
        'views/license_views.xml',
        'wizard/license_activation_wizard_views.xml',
        'wizard/sales_route_add_partner_wizard_views.xml',
        'wizard/route_plan_add_client_wizard_views.xml',
        'wizard/route_sale_terminal_wizard_views.xml',
        'wizard/visit_purpose_wizard_views.xml',
        'wizard/marketing_visit_quick_wizard_views.xml',
        'wizard/quick_route_plan_wizard_views.xml',
        'wizard/sales_marketing_period_wizard_views.xml',
        'views/sales_route_views.xml',
        'views/route_plan_views.xml',
        'views/route_visit_views.xml',
        'views/sale_order_views.xml',
        'views/commercial_request_views.xml',
        'views/facilitation_views.xml',
        'views/menu_views.xml',
        'views/customer_360_views.xml',
        'views/sales_person_profile_views.xml',
        'views/fmcg_extension_views.xml',
        'views/fmcg_phase2_views.xml',
        'views/fmcg_phase3_views.xml',
    ],
    'pre_init_hook': 'pre_init_hook',
    'post_init_hook': 'post_init_hook',
    'installable': True,
    'application': True,
}
