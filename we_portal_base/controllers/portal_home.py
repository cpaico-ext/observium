# -*- coding: utf-8 -*-
from odoo import http
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request


class PortalHomeController(CustomerPortal):

    def _get_accessible_dashboards(self):
        """
        Return all active dashboards accessible to the current portal user.

        FIX #7: Uses a single ORM query with an SQL IN clause instead of
        iterating roles and dashboards in Python (N+1 pattern).
        """
        partner = request.env.user.partner_id

        # Collect role IDs for this partner (as client or as contact)
        roles = request.env['portal.partner.role'].search([
            '|',
            ('contact_ids', 'in', partner.id),
            ('client_id', '=', partner.id),
        ])
        if not roles:
            return []

        # Single query: all active dashboards assigned to any of those roles
        dashboards = request.env['portal.dashboard'].search([
            ('active', '=', True),
            ('id', 'in', roles.mapped('dashboard_ids').ids),
        ], order='sequence, name')

        return dashboards

    def _prepare_portal_layout_values(self):
        """Inject accessible_dashboards into portal home context."""
        values = super()._prepare_portal_layout_values()
        values['accessible_dashboards'] = self._get_accessible_dashboards()
        return values
