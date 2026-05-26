from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SalesRouteMarketingQuickWizard(models.TransientModel):
    _name = 'sales.route.marketing.quick.wizard'
    _description = 'Marketing Visit Quick Capture'

    visit_id = fields.Many2one('sales.route.visit', required=True, readonly=True)
    partner_id = fields.Many2one(related='visit_id.partner_id', readonly=True)
    route_id = fields.Many2one(related='visit_id.route_id', readonly=True)
    # Compatibility field: older wizard views/contexts may still pass `step`.
    # Keep it stored so existing databases and browser cached payloads cannot crash.
    step = fields.Selection([('programs', 'Programmes / Catalogues'), ('details', 'Client Details')], string='Step', default='programs')
    program_issued = fields.Selection([('yes', 'Yes'), ('no', 'No')], string='Program / Catalogue Issued?', default='no', required=True)
    program_custom_count = fields.Integer(string='Other Program Count', default=0)
    program_count = fields.Integer(string='Program Count', compute='_compute_program_count', readonly=True)
    program_ids = fields.Many2many('sales.route.marketing.program', 'sales_route_marketing_quick_program_rel', 'wizard_id', 'program_id', string='Programs / Catalogues')
    program_line_ids = fields.One2many('sales.route.marketing.quick.program.line', 'wizard_id', string='Programs / Catalogues')
    marketing_activities_done = fields.Text(string='Activities Done at Client Place')
    marketing_notes = fields.Text(string='Marketing Notes / Customer Feedback')
    contact_person_name = fields.Char(string='Contact Person Name')
    contact_person_phone = fields.Char(string='Contact Person Phone')
    contact_person_email = fields.Char(string='Contact Person Email')
    followup_activity_type_id = fields.Many2one('mail.activity.type', string='Next Activity Type')
    followup_date_deadline = fields.Date(string='Next Activity Due Date')
    followup_summary = fields.Char(string='Next Activity Summary')
    followup_note = fields.Text(string='Next Activity Note')

    @api.depends('program_ids', 'program_issued', 'program_custom_count', 'program_line_ids.count', 'program_line_ids.response', 'program_line_ids.is_issued', 'program_line_ids.program_id')
    def _compute_program_count(self):
        for rec in self:
            # The modern marketing wizard uses program_ids as the main checkbox selector.
            # Each selected programme/catalogue counts as 1. Unselected active programmes count as 0.
            if rec.program_ids:
                rec.program_count = len(rec.program_ids)
                continue
            valid_lines = rec.program_line_ids.filtered(lambda line: line.program_id)
            if valid_lines:
                rec.program_count = sum(1 if line.is_issued or line.response == 'yes' else 0 for line in valid_lines)
            elif rec.program_issued == 'yes':
                rec.program_count = 1
            else:
                rec.program_count = 0

    def _ensure_partner_contact(self):
        """Create/update a child contact on the customer from the wizard details."""
        self.ensure_one()
        if not self.contact_person_name or not self.visit_id.partner_id:
            return False
        parent = self.visit_id.partner_id
        domain = [('parent_id', '=', parent.id), ('name', '=', self.contact_person_name)]
        if self.contact_person_phone:
            domain = ['|', ('phone', '=', self.contact_person_phone), ('mobile', '=', self.contact_person_phone)] + domain
        existing = self.env['res.partner'].search(domain, limit=1)
        vals = {
            'name': self.contact_person_name,
            'parent_id': parent.id,
            'type': 'contact',
            'phone': self.contact_person_phone or False,
            'mobile': self.contact_person_phone or False,
            'email': self.contact_person_email or False,
            'customer_rank': 0,
        }
        if existing:
            existing.write({k: v for k, v in vals.items() if v})
            return existing
        return self.env['res.partner'].create(vals)

    def _prepare_program_lines(self, visit):
        existing = {line.program_id.id: line for line in visit.program_line_ids if line.program_id}
        lines = []
        programs = self.env['sales.route.marketing.program'].search([('active', '=', True)], order='name, id')
        for program in programs:
            line = existing.get(program.id)
            lines.append((0, 0, {
                'program_id': program.id,
                'response': line.response if line else 'no',
                'is_issued': True if line and line.response == 'yes' else False,
                'count': line.count if line else 0,
                'note': line.note if line else False,
            }))
        return lines

    @api.model
    def default_get(self, fields_list):
        values = super().default_get(fields_list)
        visit_id = values.get('visit_id') or self.env.context.get('default_visit_id')
        if visit_id:
            visit = self.env['sales.route.visit'].browse(visit_id)
            values.update({
                'visit_id': visit.id,
                'program_issued': visit.program_issued or 'no',
                'program_ids': [(6, 0, visit.program_ids.ids or ([visit.program_id.id] if visit.program_id else []))],
                'program_custom_count': visit.program_custom_count,
                'program_line_ids': self._prepare_program_lines(visit),
                'marketing_activities_done': visit.marketing_activities_done,
                'marketing_notes': visit.marketing_notes,
                'contact_person_name': visit.contact_person_name,
                'contact_person_phone': visit.contact_person_phone,
                'contact_person_email': visit.contact_person_email,
                'followup_activity_type_id': visit.followup_activity_type_id.id or False,
                'followup_date_deadline': visit.followup_date_deadline,
                'followup_summary': visit.followup_summary,
                'followup_note': visit.followup_note,
            })
        return values

    @api.onchange('visit_id')
    def _onchange_visit_id(self):
        if self.visit_id:
            self.program_issued = self.visit_id.program_issued or 'no'
            self.program_ids = [(6, 0, self.visit_id.program_ids.ids or ([self.visit_id.program_id.id] if self.visit_id.program_id else []))]
            self.program_custom_count = self.visit_id.program_custom_count
            self.program_line_ids = [(5, 0, 0)] + self._prepare_program_lines(self.visit_id)
            self.marketing_activities_done = self.visit_id.marketing_activities_done
            self.marketing_notes = self.visit_id.marketing_notes
            self.contact_person_name = self.visit_id.contact_person_name
            self.contact_person_phone = self.visit_id.contact_person_phone
            self.contact_person_email = self.visit_id.contact_person_email
            self.followup_activity_type_id = self.visit_id.followup_activity_type_id
            self.followup_date_deadline = self.visit_id.followup_date_deadline
            self.followup_summary = self.visit_id.followup_summary
            self.followup_note = self.visit_id.followup_note

    def _write_to_visit(self):
        self.ensure_one()
        visit = self.visit_id
        # Main source for the modern wizard: selected programmes/catalogues.
        selected_program_ids = self.program_ids.ids

        # Fallback for older cached forms that may still send transient line values.
        if not selected_program_ids and self.program_line_ids:
            selected_program_ids = self.program_line_ids.filtered(lambda line: line.program_id and line.is_issued).mapped('program_id').ids

        active_programs = self.env['sales.route.marketing.program'].search([('active', '=', True)], order='name, id')
        selected_set = set(selected_program_ids)
        program_line_values = []
        for program in active_programs:
            issued = program.id in selected_set
            program_line_values.append((0, 0, {
                'program_id': program.id,
                'response': 'yes' if issued else 'no',
                'count': 1 if issued else 0,
                'note': False,
            }))

        visit.write({
            'visit_purpose': 'marketing',
            'program_issued': 'yes' if selected_program_ids else 'no',
            'program_custom_count': len(selected_program_ids),
            'program_id': selected_program_ids[0] if selected_program_ids else False,
            'program_ids': [(6, 0, selected_program_ids)],
            'program_line_ids': [(5, 0, 0)] + program_line_values,
            'marketing_activities_done': self.marketing_activities_done,
            'marketing_notes': self.marketing_notes,
            'contact_person_name': self.contact_person_name,
            'contact_person_phone': self.contact_person_phone,
            'contact_person_email': self.contact_person_email,
            'followup_activity_type_id': self.followup_activity_type_id.id or False,
            'followup_date_deadline': self.followup_date_deadline,
            'followup_summary': self.followup_summary,
            'followup_note': self.followup_note,
        })
        self._ensure_partner_contact()
        return visit


    def action_save_and_open_visit(self):
        """Save the quick marketing capture, then open the normal visit form.

        The salesperson will then use the existing GPS Check In / Check Out
        buttons on the visit form. This keeps the marketing wizard focused on
        programmes/catalogues and contact capture only.
        """
        visit = self._write_to_visit()
        return visit.action_open_visit_form()

    def action_create_next_activity(self):
        visit = self._write_to_visit()
        if not self.followup_activity_type_id or not self.followup_date_deadline:
            raise UserError(_('Please select the next activity type and due date.'))
        visit.action_create_followup_activity()
        return visit.action_open_visit_form()


class SalesRouteMarketingQuickProgramLine(models.TransientModel):
    _name = 'sales.route.marketing.quick.program.line'
    _description = 'Marketing Quick Program / Catalogue Line'
    _order = 'program_id, id'

    wizard_id = fields.Many2one('sales.route.marketing.quick.wizard', ondelete='cascade')
    program_id = fields.Many2one('sales.route.marketing.program', string='Program / Catalogue')
    is_issued = fields.Boolean(string='Issued?')
    response = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No'),
    ], string='Issued?', default='no', required=True)
    count = fields.Integer(string='Count', default=0)
    note = fields.Char(string='Note')

    @api.onchange('is_issued')
    def _onchange_is_issued(self):
        for rec in self:
            rec.response = 'yes' if rec.is_issued else 'no'
            rec.count = 1 if rec.is_issued else 0

    @api.onchange('response')
    def _onchange_response(self):
        for rec in self:
            rec.is_issued = rec.response == 'yes'
            if rec.response == 'yes':
                rec.count = 1
            elif rec.response == 'no':
                rec.count = 0



    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'is_issued' in vals:
                vals['response'] = 'yes' if vals.get('is_issued') else 'no'
            if vals.get('response') == 'yes':
                vals['is_issued'] = True
                vals['count'] = 1
            elif vals.get('response') == 'no':
                vals['is_issued'] = False
                vals['count'] = 0
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        if 'is_issued' in vals:
            vals['response'] = 'yes' if vals.get('is_issued') else 'no'
        if vals.get('response') == 'yes':
            vals['is_issued'] = True
            vals['count'] = 1
        elif vals.get('response') == 'no':
            vals['is_issued'] = False
            vals['count'] = 0
        return super().write(vals)
