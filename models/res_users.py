# -*- coding: utf-8 -*-
# Recovery build: no custom stored fields are added directly to res.users.
# This avoids startup crashes when Odoo reads res.users before module upgrade/migration completes.
from odoo import models


class ResUsers(models.Model):
    _inherit = 'res.users'

    # Intentionally empty. Team supervision is handled by sales.route.team.hierarchy.
    pass
