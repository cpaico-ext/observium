# -*- coding: utf-8 -*-
import logging

from odoo import _
from odoo import http
from odoo.http import request
from werkzeug.exceptions import Forbidden, NotFound
from odoo.addons.we_portal_base.controllers.dashboard import DashboardController

_logger = logging.getLogger(__name__)


class ObserviumDashboardController(DashboardController):
    """
    Extiende DashboardController para inyectar información del grupo
    Observium cuando el partner tiene observium_group_code configurado.
    """

    def _get_observium_group_info(self):
        """
        Retorna (group_info, device_stats, group_error).
        - Sin código       → (None, None, None)
        - Error de API     → (None, None, mensaje)
        - OK               → (dict_grupo, dict_stats, None)
        """
        partner = request.env.user.partner_id
        group_code = partner.observium_group_code or partner.parent_id.observium_group_code
        if not group_code:
            return None, None, None
        try:
            svc = request.env['observium.service'].sudo()
            group = svc.get_group_by_id(group_code)
            if not group:
                return None, None, _('No se encontró información para el grupo configurado.')
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
        Clasifica group_descr en uno de tres tipos:
          'ruc'     → 11 dígitos que empiezan por 20 (empresa peruana)
          'dni'     → exactamente 8 dígitos (persona natural)
          'generic' → cualquier otro valor o vacío
        Retorna un dict con 'type', 'icon' y 'label'.
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

        group_info, device_stats, group_error = self._get_observium_group_info()

        values = {
            'dashboard':    dashboard,
            'title':        dashboard.name,
            'elements':     dashboard.element_ids.sorted(lambda i: (i.sequence, i.name)),
            'page_name':    'dashboard_%s' % code,
            'languages':    request.env['res.lang'].sudo().search([('active', '=', True)]),
            'default_lang': request.env.lang or 'en_US',
            'group_info':   group_info,
            'device_stats': device_stats,
            'group_error':  group_error,
        }
        return request.render('we_portal_base.portal_dashboard_detail', values)