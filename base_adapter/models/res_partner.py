# -*- coding: utf-8 -*-

from odoo import fields, models, _

class ResPartner(models.Model):
    _inherit = 'res.partner'
    
    is_customer = fields.Boolean(
        string='Is Customer',
    )
    
    intranet_code = fields.Integer(
        string='Intranet code',
    )

    win_business_code = fields.Integer(
        string='Win business code',
    )