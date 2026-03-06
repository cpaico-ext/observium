# -*- coding: utf-8 -*-
from odoo import _, api, fields, models


class PortalDashboard(models.Model):
    _name = 'portal.dashboard'
    _description = 'Portal Dashboard'
    _order = 'sequence, name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True, copy=False, help='Unique identifier used in the URL, e.g. "network-monitor"')
    description = fields.Char(string='Description', translate=True)
    icon_type = fields.Selection(selection=[('fa', 'FontAwesome Icon'), ('image', 'Image')], string='Icon Type', default='fa', required=True)
    icon = fields.Char(string='Icon', default='fa-tachometer', help='FontAwesome icon class, e.g. "fa-eye"')
    icon_image = fields.Image(string='Icon Image', max_width=256, max_height=256)
    url = fields.Char(string='URL Path', compute='_compute_url', store=True, help='Auto-generated portal URL based on code')
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)
    element_ids = fields.Many2many(
        comodel_name='portal.dashboard.element',
        relation='portal_dashboard_element_rel',
        column1='dashboard_id', column2='element_id', string='Elements',
    )
    element_count = fields.Integer(string='Element Count', compute='_compute_element_count')

    _sql_constraints = [('code_unique', 'UNIQUE(code)', 'Dashboard code must be unique.')]

    @api.depends('code')
    def _compute_url(self):
        for rec in self:
            rec.url = '/my/dashboard/%s' % rec.code if rec.code else False

    @api.depends('element_ids')
    def _compute_element_count(self):
        for rec in self:
            rec.element_count = len(rec.element_ids)
