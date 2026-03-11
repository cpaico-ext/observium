# -*- coding: utf-8 -*-
import random
import string

from odoo import _, api, fields, models


def _generate_reference(env):
    """Generate a unique 8-char mixed-case alphanumeric code."""
    chars = string.ascii_letters + string.digits
    for _ in range(20):
        code = ''.join(random.choices(chars, k=8))
        if not env['portal.partner.role'].sudo().search([('reference', '=', code)], limit=1):
            return code
    return ''.join(random.choices(chars, k=12))


class PortalPartnerRole(models.Model):
    _name = 'portal.partner.role'
    _description = 'Portal Partner Role'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    reference = fields.Char(
        string='Reference',
        copy=False,
        readonly=True,
        index=True,
    )
    active = fields.Boolean(string='Active', default=True)
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

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('reference'):
                vals['reference'] = _generate_reference(self.env)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        # Back-fill only records that have no reference at all
        for record in self.filtered(lambda r: not r.reference):
            record.reference = _generate_reference(self.env)
        return result

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

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