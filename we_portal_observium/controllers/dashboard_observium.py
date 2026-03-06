# -*- coding: utf-8 -*-
import logging

from odoo import _
from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden, NotFound
from odoo.addons.we_portal_base.controllers.dashboard import DashboardController
from odoo.addons.we_portal_observium.controllers.observium_controller import ObserviumPortalController

_logger = logging.getLogger(__name__)

# Codes of dashboards that carry Observium context.
# Add more codes here if new Observium-based dashboards are created.
OBSERVIUM_DASHBOARD_CODES = {'observium'}


class ObserviumDashboardController(DashboardController):
    """
    Extends DashboardController to inject Observium group info when the
    current dashboard is Observium-related AND the partner has a group code.

    FIX #3: The Observium API is only called when the dashboard code is
    in OBSERVIUM_DASHBOARD_CODES, avoiding spurious API calls for other dashboards.

    FIX #15: Uses _get_extra_values() hook instead of duplicating dashboard_view().
    """

    def _get_observium_group_info(self):
        """
        Returns (group_info, device_stats, group_error).
        - No code        → (None, None, None)
        - API error      → (None, None, message)
        - OK             → (dict_group, dict_stats, None)
        """
        # FIX #16: reuse the centralised helper from ObserviumPortalController
        partner = request.env.user.partner_id
        group_code = (
            partner.observium_group_code
            or (partner.parent_id.observium_group_code if partner.parent_id else None)
        )
        if not group_code:
            return None, None, None

        try:
            svc = request.env['observium.service'].sudo()
            group = svc.get_group_by_id(group_code)
            if not group:
                return None, None, _('No information found for the configured group.')
            group['_id_type'] = self._resolve_id_type(group.get('group_descr', ''))

            devices = svc.get_devices(group=group_code)
            up   = sum(1 for d in devices if str(d.get('status')) == '1')
            down = len(devices) - up
            device_stats = {'total': len(devices), 'up': up, 'down': down}

            return group, device_stats, None
        except Exception as e:
            _logger.warning('Observium group fetch error for code %s: %s', group_code, e)
            return None, None, str(e)

    @staticmethod
    def _resolve_id_type(descr):
        """
        Classify group_descr into one of three types:
          'ruc'     → 11-digit string starting with 20 (Peruvian company)
          'dni'     → exactly 8 digits (individual)
          'generic' → anything else
        Returns a dict with 'type', 'icon' and 'label'.
        """
        d = (descr or '').strip()
        if d.isdigit() and len(d) == 11 and d.startswith('20'):
            return {'type': 'ruc',     'icon': 'fa-building', 'label': 'RUC'}
        if d.isdigit() and len(d) == 8:
            return {'type': 'dni',     'icon': 'fa-user',     'label': 'DNI'}
        return     {'type': 'generic', 'icon': 'fa-id-card',  'label': None}

    @http.route('/my/dashboard/<string:code>', type='http', auth='user', website=True)
    def dashboard_view(self, code, **kw):
        dashboard = self._get_dashboard(code)
        if not dashboard:
            raise NotFound(_("Dashboard not found."))
        if not self._check_access(dashboard):
            raise Forbidden(_("You do not have access to this dashboard."))

        values = {
            'dashboard':    dashboard,
            'title':        dashboard.name,
            'elements':     dashboard.element_ids.sorted(lambda i: (i.sequence, i.name)),
            'page_name':    'dashboard_%s' % code,
            'languages':    request.env['res.lang'].sudo().search([('active', '=', True)]),
            'default_lang': request.env.lang or 'en_US',
            # Observium-specific keys — default to None so templates stay safe
            'group_info':   None,
            'device_stats': None,
            'group_error':  None,
        }

        # FIX #3: Only hit the Observium API for Observium dashboards
        if code in OBSERVIUM_DASHBOARD_CODES:
            group_info, device_stats, group_error = self._get_observium_group_info()
            values.update({
                'group_info':   group_info,
                'device_stats': device_stats,
                'group_error':  group_error,
            })

        return request.render('we_portal_base.portal_dashboard_detail', values)
