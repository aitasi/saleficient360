# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SalesRouteTeamHierarchy(models.Model):
    _name = 'sales.route.team.hierarchy'
    _description = 'Field Sales Team Hierarchy'
    _rec_name = 'display_name'
    _order = 'manager_id, supervisor_id, salesperson_id'

    manager_id = fields.Many2one('res.users', string='Sales Manager', required=True, ondelete='cascade', index=True)
    supervisor_id = fields.Many2one('res.users', string='Supervisor', required=True, ondelete='cascade', index=True)
    salesperson_id = fields.Many2one('res.users', string='Sales Person', required=True, ondelete='cascade', index=True)
    display_name = fields.Char(compute='_compute_display_name', store=False)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ('unique_salesperson_hierarchy', 'unique(salesperson_id)', 'This sales person is already assigned to a supervisor.'),
    ]

    @api.depends('manager_id', 'supervisor_id', 'salesperson_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '%s / %s / %s' % (
                rec.manager_id.name or '',
                rec.supervisor_id.name or '',
                rec.salesperson_id.name or '',
            )

    @api.constrains('manager_id', 'supervisor_id', 'salesperson_id')
    def _check_hierarchy_users(self):
        for rec in self:
            if rec.manager_id == rec.supervisor_id:
                raise ValidationError(_('The Sales Manager and Supervisor must be different users.'))
            if rec.supervisor_id == rec.salesperson_id:
                raise ValidationError(_('The Supervisor and Sales Person must be different users.'))
            if rec.manager_id == rec.salesperson_id:
                raise ValidationError(_('The Sales Manager and Sales Person must be different users.'))

    @api.model
    def get_visible_user_ids(self, user=None):
        """Return the users a logged-in user is allowed to monitor.

        One Sales Manager can have many Supervisors.
        One Supervisor can have many Sales Persons.
        This is stored as one row per Sales Person, which keeps upgrades safe and
        avoids adding custom columns to res.users.
        """
        user = user or self.env.user
        user_ids = {user.id}
        rows = self.sudo().search([('active', '=', True), '|', ('manager_id', '=', user.id), ('supervisor_id', '=', user.id)])
        user_ids.update(rows.mapped('manager_id').ids)
        user_ids.update(rows.mapped('supervisor_id').ids)
        user_ids.update(rows.mapped('salesperson_id').ids)
        return list(user_ids)

    @api.model
    def get_supervisor_ids_for_manager(self, manager):
        rows = self.sudo().search([('active', '=', True), ('manager_id', '=', manager.id)])
        return rows.mapped('supervisor_id').ids

    @api.model
    def get_salesperson_ids_for_supervisor(self, supervisor):
        rows = self.sudo().search([('active', '=', True), ('supervisor_id', '=', supervisor.id)])
        return rows.mapped('salesperson_id').ids
