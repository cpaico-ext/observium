# -*- coding: utf-8 -*-
from odoo import _, fields, models


class PortalDashboardElement(models.Model):
    _name = 'portal.dashboard.element'
    _description = 'Portal Dashboard Element'
    _order = 'sequence, name'

    name = fields.Char(
        string='Name',
        required=True,
        translate=True,
    )
    code = fields.Char(
        string='Code',
        copy=False,
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    template_id = fields.Many2one(
        comodel_name='ir.ui.view',
        string='Template',
        domain=[('type', '=', 'qweb')],
        help='QWeb template to render for this dashboard element',
    )
    dashboard_ids = fields.Many2many(
        comodel_name='portal.dashboard',
        relation='portal_dashboard_element_rel',
        column1='element_id',
        column2='dashboard_id',
        string='Dashboards',
    )
