from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalesRouteFacilitationForm(models.Model):
    _name = 'sales.route.facilitation.form'
    _description = 'Daily Route Facilitation Form'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'plan_date desc, id desc'

    name = fields.Char(default='New', copy=False, readonly=True)
    plan_date = fields.Date(required=True, default=fields.Date.context_today, tracking=True, index=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', required=True, default=lambda self: self.env.user, tracking=True, index=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id', readonly=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('generated', 'Generated'),
        ('approved', 'Approved'),
        ('cancelled', 'Cancelled'),
    ], default='draft', tracking=True)
    line_ids = fields.One2many('sales.route.facilitation.form.line', 'form_id', string='Approved Route Plans')
    route_plan_count = fields.Integer(compute='_compute_totals', store=True)
    total_clients = fields.Integer(compute='_compute_totals', store=True)
    total_facilitation_amount = fields.Monetary(compute='_compute_totals', store=True, currency_field='currency_id')
    note = fields.Text()

    _sql_constraints = [
        ('date_supervisor_company_unique', 'unique(plan_date, supervisor_id, company_id)', 'A facilitation form already exists for this supervisor and day.'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                seq = self.env['ir.sequence'].next_by_code('sales.route.facilitation.form')
                vals['name'] = seq or _('Facilitation Form')
        return super().create(vals_list)

    @api.depends('line_ids', 'line_ids.planned_clients', 'line_ids.facilitation_amount')
    def _compute_totals(self):
        for form in self:
            form.route_plan_count = len(form.line_ids)
            form.total_clients = sum(form.line_ids.mapped('planned_clients'))
            form.total_facilitation_amount = sum(form.line_ids.mapped('facilitation_amount'))

    def _approved_plan_domain(self):
        self.ensure_one()
        return [
            ('plan_date', '=', self.plan_date),
            ('state', 'in', ['approved', 'in_progress', 'done']),
            ('company_id', '=', self.company_id.id),
        ]

    def action_generate_lines(self):
        for form in self:
            if not form.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') and not form.env.user.has_group('field_sales_route_plan.group_field_sales_manager') and not form.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_('Only a supervisor or sales manager can generate facilitation forms.'))
            plans = self.env['sales.route.plan'].search(form._approved_plan_domain(), order='user_id, route_id, id')
            if not plans:
                raise UserError(_('No approved route plans were found for %s.') % form.plan_date)
            existing_by_plan = {line.plan_id.id: line for line in form.line_ids if line.plan_id}
            commands = []
            for plan in plans:
                vals = {
                    'plan_id': plan.id,
                    'user_id': plan.user_id.id,
                    'route_id': plan.route_id.id,
                    'supervisor_id': plan.supervisor_id.id or form.supervisor_id.id,
                    'planned_clients': len(plan.line_ids),
                    'planned_productive_calls': plan.planned_productive_calls,
                    'approved_state': plan.state,
                }
                if plan.id in existing_by_plan:
                    existing_by_plan[plan.id].write(vals)
                else:
                    commands.append((0, 0, vals))
            if commands:
                form.write({'line_ids': commands})
            form.state = 'generated'
            form.message_post(body=_('Facilitation form generated for %s approved route plan(s).') % len(plans))
        return True


    def action_add_plans(self, plans):
        for form in self:
            if not form.env.user.has_group('field_sales_route_plan.group_field_sales_supervisor') and not form.env.user.has_group('field_sales_route_plan.group_field_sales_manager') and not form.env.user.has_group('sales_team.group_sale_manager'):
                raise UserError(_('Only a supervisor or sales manager can add route plans to facilitation sheets.'))

            today = fields.Date.context_today(form)
            if form.plan_date != today:
                raise UserError(_("You can only add route plans to today\'s facilitation sheet. Please use or create the sheet dated %s.") % today)

            plans = plans.filtered(lambda p: p.state in ('approved', 'in_progress', 'done') and p.plan_date == today and p.plan_date == form.plan_date and p.company_id == form.company_id)
            if not plans:
                raise UserError(_('No matching approved route plans for today were found for this facilitation sheet.'))
            existing_plan_ids = set(form.line_ids.mapped('plan_id').ids)
            commands = []
            updated = 0
            for plan in plans:
                vals = {
                    'plan_id': plan.id,
                    'user_id': plan.user_id.id,
                    'route_id': plan.route_id.id,
                    'supervisor_id': plan.supervisor_id.id or form.supervisor_id.id,
                    'planned_clients': len(plan.line_ids),
                    'planned_productive_calls': plan.planned_productive_calls,
                    'approved_state': plan.state,
                }
                existing_line = form.line_ids.filtered(lambda l, plan=plan: l.plan_id == plan)[:1]
                if existing_line:
                    existing_line.write(vals)
                    updated += 1
                elif plan.id not in existing_plan_ids:
                    commands.append((0, 0, vals))
            if commands:
                form.write({'line_ids': commands})
            if form.state == 'draft' and form.line_ids:
                form.state = 'generated'
            form.message_post(body=_('%s route plan(s) added and %s existing line(s) refreshed.') % (len(commands), updated))
        return True

    def action_approve(self):
        for form in self:
            if not form.line_ids:
                raise UserError(_('Generate facilitation lines before approving this form.'))
        self.write({'state': 'approved'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_draft(self):
        self.write({'state': 'draft'})


class SalesRouteFacilitationFormLine(models.Model):
    _name = 'sales.route.facilitation.form.line'
    _description = 'Daily Route Facilitation Form Line'
    _order = 'user_id, route_id, id'

    form_id = fields.Many2one('sales.route.facilitation.form', required=True, ondelete='cascade')
    plan_id = fields.Many2one('sales.route.plan', string='Route Plan', required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Salesperson', required=True)
    route_id = fields.Many2one('sales.route', required=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor')
    planned_clients = fields.Integer(string='Approved Clients')
    planned_productive_calls = fields.Integer(string='Target Productive Calls')
    approved_state = fields.Char(string='Plan Status', readonly=True)
    facilitation_amount = fields.Monetary(string='Facilitation Amount', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', related='form_id.currency_id', readonly=True)
    note = fields.Char()

    _sql_constraints = [
        ('form_plan_unique', 'unique(form_id, plan_id)', 'This route plan is already on the facilitation form.'),
    ]
