from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError
import base64
import hashlib
import json

# Public verification key only. The private signing key is intentionally not loaded
# into Odoo. Keep the generator folder outside the Odoo addons path.
LICENSE_PUBLIC_E = 65537
LICENSE_PUBLIC_N = int(
    '90196504057376230926848548234891381349326215277803606512181913205150663489863811656617233770859118533420850234058715656252686628166893697615604195871828744844029719578956057031961490660776370705189571266364678991389173395816486116852069554613899284288419868327700232311616950934179820370304154704582559447491'
)


class SalesRouteLicense(models.Model):
    _name = 'sales.route.license'
    _description = 'Field Sales Local License'
    _inherit = ['mail.thread']
    _order = 'id desc'

    name = fields.Char(default='Field Sales License', required=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    license_key = fields.Char(string='License Key', tracking=True, readonly=True, help='Only the last safe fingerprint of the activation code is stored. The full activation key is not kept in Odoo.')
    activation_fingerprint = fields.Char(string='Activation Fingerprint', readonly=True, copy=False)
    activated_by_id = fields.Many2one('res.users', string='Activated By', readonly=True, copy=False)
    activation_date = fields.Datetime(string='Activation Date', readonly=True, copy=False)
    plan_type = fields.Selection([
        ('trial_30', '30 Day Free Trial'),
        ('days_90', '90 Day License'),
        ('months_6', '6 Month License'),
        ('annual', 'Annual License'),
        ('years_3', '3 Year License'),
        ('custom', 'Custom'),
    ], default='trial_30', required=True, tracking=True)
    start_date = fields.Date(default=fields.Date.context_today, required=True, tracking=True)
    expiry_date = fields.Date(required=True, tracking=True)
    grace_days = fields.Integer(default=0, string='Grace Period Days')
    warning_days = fields.Integer(default=14, string='Expiry Warning Days')
    max_users = fields.Integer(default=0, string='Maximum Field Users', help='0 means unlimited')
    active = fields.Boolean(default=True)
    notes = fields.Text()
    days_remaining = fields.Integer(compute='_compute_status', string='Days Remaining')
    state = fields.Selection([
        ('trial', 'Trial'),
        ('active', 'Active'),
        ('expiring', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('blocked', 'Blocked'),
    ], compute='_compute_status', store=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if not vals.get('expiry_date'):
            vals['expiry_date'] = fields.Date.add(fields.Date.context_today(self), days=30)
        return vals

    @api.onchange('plan_type', 'start_date')
    def _onchange_plan_type_dates(self):
        for rec in self:
            start = rec.start_date or fields.Date.context_today(rec)
            if rec.plan_type == 'trial_30':
                rec.expiry_date = fields.Date.add(start, days=30)
            elif rec.plan_type == 'days_90':
                rec.expiry_date = fields.Date.add(start, days=90)
            elif rec.plan_type == 'months_6':
                rec.expiry_date = fields.Date.add(start, months=6)
            elif rec.plan_type == 'annual':
                rec.expiry_date = fields.Date.add(start, years=1)
            elif rec.plan_type == 'years_3':
                rec.expiry_date = fields.Date.add(start, years=3)

    @api.depends('expiry_date', 'grace_days', 'warning_days', 'plan_type', 'active')
    def _compute_status(self):
        today = fields.Date.context_today(self)
        for rec in self:
            if not rec.active:
                rec.days_remaining = 0
                rec.state = 'blocked'
                continue
            if rec.expiry_date:
                days = (rec.expiry_date - today).days
            else:
                days = 0
            rec.days_remaining = days
            grace_limit = -(rec.grace_days or 0)
            if days < grace_limit:
                rec.state = 'blocked'
            elif days < 0:
                rec.state = 'expired'
            elif days <= (rec.warning_days or 0):
                rec.state = 'expiring'
            elif rec.plan_type == 'trial_30':
                rec.state = 'trial'
            else:
                rec.state = 'active'

    @api.model
    def _ensure_default_license(self):
        license_rec = self.sudo().search([('company_id', '=', self.env.company.id)], limit=1)
        if not license_rec:
            today = fields.Date.context_today(self)
            license_rec = self.sudo().create({
                'name': '30 Day Free Trial',
                'company_id': self.env.company.id,
                'plan_type': 'trial_30',
                'start_date': today,
                'expiry_date': fields.Date.add(today, days=30),
                'license_key': 'TRIAL-%s' % self.env.cr.dbname,
            })
        return license_rec

    @api.model
    def get_license_info(self):
        lic = self._ensure_default_license()
        return {
            'state': lic.state,
            'plan_type': lic.plan_type,
            'expiry_date': str(lic.expiry_date) if lic.expiry_date else '',
            'days_remaining': lic.days_remaining,
            'is_blocked': lic.state in ('expired', 'blocked'),
            'message': lic._license_message(),
            'expiry_label': lic.expiry_date.strftime('%d %b %Y') if lic.expiry_date else '',
            'can_activate': self.env.user.has_group('base.group_system'),
        }

    def _license_message(self):
        self.ensure_one()
        if self.state == 'blocked':
            return _('Field Sales license is blocked. Please renew the license.')
        if self.state == 'expired':
            return _('Field Sales license expired %s day(s) ago. Please renew the license.') % abs(self.days_remaining)
        if self.state == 'expiring':
            return _('Field Sales license expires in %s day(s).') % self.days_remaining
        if self.state == 'trial':
            return _('Field Sales trial license: %s day(s) remaining.') % self.days_remaining
        return _('Field Sales license is active.')

    @api.model
    def check_access_or_raise(self):
        lic = self._ensure_default_license()
        if lic.state in ('expired', 'blocked'):
            raise UserError(lic._license_message())
        if lic.max_users:
            group = self.env.ref('field_sales_route_plan.group_field_sales_user', raise_if_not_found=False)
            if group and len(group.users) > lic.max_users:
                raise UserError(_('Field Sales license user limit exceeded. Allowed users: %s') % lic.max_users)
        return True

    def action_activate_trial(self):
        today = fields.Date.context_today(self)
        self.write({
            'active': True,
            'plan_type': 'trial_30',
            'start_date': today,
            'expiry_date': fields.Date.add(today, days=30),
        })


    @api.model
    def _decode_activation_code(self, activation_code):
        code = (activation_code or '').strip().replace('\n', '').replace(' ', '')
        if not code:
            raise UserError(_('Please enter a license activation code.'))
        try:
            raw = base64.urlsafe_b64decode(code + '=' * (-len(code) % 4)).decode('utf-8')
            payload_b64, sig_hex = raw.split('.', 1)
            payload_raw = base64.urlsafe_b64decode(payload_b64 + '=' * (-len(payload_b64) % 4))
            signature = int(sig_hex, 16)
        except Exception:
            raise UserError(_('Invalid activation code format.'))
        digest = int.from_bytes(hashlib.sha256(payload_raw).digest(), 'big')
        if pow(signature, LICENSE_PUBLIC_E, LICENSE_PUBLIC_N) != digest:
            raise UserError(_('Invalid activation signature. This code was not generated by the private license key.'))
        try:
            payload = json.loads(payload_raw.decode('utf-8'))
        except Exception:
            raise UserError(_('Invalid activation payload.'))
        return payload, hashlib.sha256(code.encode('utf-8')).hexdigest()

    def action_open_activation_wizard(self):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an Odoo System Administrator can activate or renew the Field Sales license.'))
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Activate Field Sales License'),
            'res_model': 'sales.route.license.activation.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_license_id': self.id},
        }

    def activate_with_code(self, activation_code):
        if not self.env.user.has_group('base.group_system'):
            raise AccessError(_('Only an Odoo System Administrator can activate or renew the Field Sales license.'))
        self.ensure_one()
        payload, fingerprint = self._decode_activation_code(activation_code)
        dbname = payload.get('db')
        company = payload.get('company')
        if dbname and dbname != self.env.cr.dbname:
            raise UserError(_('This activation code is for another database.'))
        if company and str(company) not in (str(self.company_id.id), self.company_id.name):
            raise UserError(_('This activation code is for another company.'))
        expiry_date = payload.get('expiry_date')
        if not expiry_date:
            raise UserError(_('The activation code does not include an expiry date.'))
        plan_type = payload.get('plan_type') or 'custom'
        if plan_type not in dict(self._fields['plan_type'].selection):
            plan_type = 'custom'
        self.write({
            'active': True,
            'plan_type': plan_type,
            'start_date': payload.get('start_date') or fields.Date.context_today(self),
            'expiry_date': expiry_date,
            'max_users': int(payload.get('max_users') or 0),
            'license_key': 'KEY-' + fingerprint[-12:].upper(),
            'activation_fingerprint': fingerprint,
            'activated_by_id': self.env.user.id,
            'activation_date': fields.Datetime.now(),
            'notes': (self.notes or '') + '\nActivated with external license key on %s.' % fields.Datetime.now(),
        })
        return True

    def action_open_renewal(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Field Sales License'),
            'res_model': 'sales.route.license',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
