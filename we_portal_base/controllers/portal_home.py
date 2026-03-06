# -*- coding: utf-8 -*-
import re

from odoo import http, _
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class PortalHomeController(CustomerPortal):

    def _get_accessible_dashboards(self):
        """Return all dashboards accessible to the current portal user."""
        partner = request.env.user.partner_id

        roles = request.env['portal.partner.role'].search([
            '|',
            ('contact_ids', 'in', partner.id),
            ('client_id', '=', partner.id),
            ('dashboard_ids', '!=', False),
        ])

        seen = set()
        dashboards = []
        for role in roles:
            for db in role.dashboard_ids:
                if db.id not in seen and db.active:
                    seen.add(db.id)
                    dashboards.append(db)

        return sorted(dashboards, key=lambda d: (d.sequence, d.name.lower()))

    def _prepare_portal_layout_values(self):
        """Inject accessible_dashboards into portal home context."""
        values = super()._prepare_portal_layout_values()
        values['accessible_dashboards'] = self._get_accessible_dashboards()
        return values
