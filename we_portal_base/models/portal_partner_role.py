# -*- coding: utf-8 -*-
from odoo import _, fields, models


class PortalPartnerRole(models.Model):
    _name = 'portal.partner.role'
    _description = 'Portal Partner Role'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        string='Name',
        required=True,
    )
    active = fields.Boolean(
        string='Active',
        default=True,
    )
    client_id = fields.Many2one(
        comodel_name='res.partner',
        string='Client',
        required=True,
        ondelete='restrict',
        help='Company or main partner associated with this role',
    )
    contact_ids = fields.Many2many(
        comodel_name='res.partner',
        relation='portal_partner_role_contact_rel',
        column1='role_id',
        column2='partner_id',
        string='Contacts',
        tracking=True,
        domain="[('parent_id', '=', client_id)]",
        help='Portal users (contacts) who will see the assigned dashboards',
    )
    dashboard_ids = fields.Many2many(
        comodel_name='portal.dashboard',
        relation='portal_partner_role_dashboard_rel',
        column1='role_id',
        column2='dashboard_id',
        string='Dashboards',
        tracking=True,
        help='Dashboards accessible to this role',
    )

    def action_grant_portal_access(self):
        self.ensure_one()
        partners = self.client_id
        if self.contact_ids:
            partners |= self.contact_ids

        wizard = self.env['portal.wizard'].with_context(
            active_ids=partners.ids,
            active_model='res.partner',
        ).create({})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'portal.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }