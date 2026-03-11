# -*- coding: utf-8 -*-
from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    portal_role_ids = fields.One2many(
        comodel_name='portal.partner.role',
        inverse_name='client_id',
        string='Portal Roles',
    )
    
    observium_code = fields.Char(
        string='Observium Group Code',
        help='Group code in Observium used to filter devices for this client.',
    )
