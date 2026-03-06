# -*- coding: utf-8 -*-
from odoo import http, _
from odoo.http import request
from werkzeug.exceptions import NotFound, Forbidden


class DashboardController(http.Controller):

    def _get_dashboard(self, code):
        """Fetch dashboard by its exact code."""
        dashboard = request.env['portal.dashboard'].search(
            [('code', '=', code), ('active', '=', True)],
            limit=1,
        )
        return dashboard or None

    def _check_access(self, dashboard):
        """Return True if the current user can access the given dashboard."""
        if not dashboard:
            return False
        partner = request.env.user.partner_id
        return bool(request.env['portal.partner.role'].search_count([
            '|',
            ('contact_ids', 'in', partner.id),
            ('client_id', '=', partner.id),
            ('dashboard_ids', 'in', dashboard.id),
        ]))

    @http.route('/my/dashboard/<string:code>', type='http', auth='user', website=True)
    def dashboard_view(self, code, **kw):
        dashboard = self._get_dashboard(code)
        if not dashboard:
            raise NotFound(_("Dashboard not found."))
        if not self._check_access(dashboard):
            raise Forbidden(_("You do not have access to this dashboard."))

        values = {
            'dashboard': dashboard,
            'title': dashboard.name,
            'elements': dashboard.element_ids.sorted(lambda i: (i.sequence, i.name)),
            'page_name': 'dashboard_%s' % code,
            'languages': request.env['res.lang'].sudo().search([('active', '=', True)]),
            'default_lang': request.env.lang or 'en_US',
        }
        return request.render('we_portal_base.portal_dashboard_detail', values)
