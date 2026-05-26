from odoo import fields, models, _


class AutoRouteAssignmentWizard(models.TransientModel):
    _name = 'sales.route.auto.assignment.wizard'
    _description = 'Generate Daily Auto Route Plans'

    plan_date = fields.Date(string='Route Date', required=True, default=fields.Date.context_today)
    user_ids = fields.Many2many('res.users', string='Salespersons', help='Leave empty to generate for all active salespeople assigned to routes.')
    max_clients = fields.Integer(string='Maximum Clients per Salesperson', default=20, required=True)
    approve = fields.Boolean(string='Approve Generated Plans', default=True, help='Approved plans appear ready to start on the salesperson dashboard.')
    overwrite = fields.Boolean(string='Replace Existing Plans', default=False, help='Cancel existing plans for the same salesperson/date and create new system plans.')

    def action_generate(self):
        self.ensure_one()
        plans, skipped = self.env['sales.route.plan'].generate_daily_auto_route_plans(
            plan_date=self.plan_date,
            user_ids=self.user_ids.ids,
            max_clients=self.max_clients,
            approve=self.approve,
            overwrite=self.overwrite,
        )
        message = _('Generated %(count)s auto assigned route plan(s).') % {'count': len(plans)}
        if skipped:
            message += '<br/><br/>' + _('Skipped:') + '<br/>' + '<br/>'.join(skipped[:30])
        return {
            'type': 'ir.actions.act_window',
            'name': _('Auto Assigned Route Plans'),
            'res_model': 'sales.route.plan',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', plans.ids)],
            'context': {'search_default_today': 1},
            'target': 'current',
            'effect': {
                'fadeout': 'slow',
                'message': message,
                'type': 'rainbow_man',
            },
        }
