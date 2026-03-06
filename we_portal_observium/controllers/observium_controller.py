# -*- coding: utf-8 -*-
import logging

import requests
from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.tools.translate import _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


class ObserviumPortalController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_partner_group_code(self):
        """
        Returns the Observium group code for the current user.
        Checks direct partner field first, then falls back to role's client.
        Centralised here so both controllers share the same logic.
        """
        partner = request.env.user.partner_id
        # Direct code on the partner (or its parent company)
        code = partner.observium_group_code or (
            partner.parent_id.observium_group_code if partner.parent_id else None
        )
        if code:
            return code
        # Fallback: look it up through the assigned portal role
        role = request.env['portal.partner.role'].sudo().search([
            '|',
            ('contact_ids', 'in', partner.id),
            ('client_id', '=', partner.id),
        ], limit=1)
        if role:
            return role.client_id.observium_group_code or None
        return None

    def _observium(self):
        return request.env['observium.service'].sudo()

    def _check_device_access(self, device_id, group_code):
        """Return True if device_id belongs to the partner's group."""
        if not group_code:
            return True
        try:
            devices = self._observium().get_devices(group=group_code)
            allowed_ids = {str(d.get('device_id')) for d in devices}
            return str(device_id) in allowed_ids
        except Exception:
            return False

    def _safe_fetch(self, fn, *args, label='data', **kwargs):
        """
        Executes fn(*args, **kwargs).
        Returns (result, None) on success or ([], error_message) on failure.
        Supplementary data must not break the page.
        """
        try:
            return fn(*args, **kwargs), None
        except Exception as e:
            _logger.warning('Observium %s error: %s', label, e)
            return [], str(e)

    # ------------------------------------------------------------------
    # Device List  /my/observium
    # ------------------------------------------------------------------

    @http.route('/my/observium', type='http', auth='user', website=True)
    def device_list(self, **kw):
        group_code = self._get_partner_group_code()
        devices = []
        error = None
        try:
            devices = self._observium().get_devices(group=group_code)
        except ValueError as e:
            error = str(e)
            _logger.warning('Observium not configured: %s', e)
        except requests.exceptions.ConnectionError:
            error = _('Could not connect to the Observium server. Please contact your administrator.')
            _logger.error('Observium connection error')
        except requests.exceptions.Timeout:
            error = _('The Observium server did not respond in time. Please try again later.')
            _logger.error('Observium timeout')
        except requests.exceptions.HTTPError as e:
            error = _('Observium API error: %s') % str(e)
            _logger.error('Observium HTTP error: %s', e)
        except Exception as e:
            error = _('Unexpected error: %s') % str(e)
            _logger.exception('Observium unexpected error')

        is_admin = not request.env.user.has_group('base.group_portal')
        values = {
            'devices': devices,
            'device_count': len(devices),
            'group_code': group_code,
            'is_admin': is_admin,
            'error': error,
            'page_name': 'observium_devices',
        }
        return request.render('we_portal_observium.observium_devices_template', values)

    # ------------------------------------------------------------------
    # Device details /my/observium/<device_id>
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>', type='http', auth='user', website=True)
    def device_detail(self, device_id, **kw):
        group_code = self._get_partner_group_code()

        if not self._check_device_access(device_id, group_code):
            raise Forbidden()

        svc = self._observium()
        device = None
        error = None

        try:
            device = svc.get_device(device_id)
            if not device:
                raise NotFound()
        except (NotFound, Forbidden):
            raise
        except ValueError as e:
            error = str(e)
        except Exception as e:
            error = _('Unexpected error: %s') % str(e)
            _logger.exception('Observium device detail error')

        warnings = {}
        addresses,  warnings['addresses']  = self._safe_fetch(svc.get_device_addresses,  device_id, label='addresses')
        mempools,   warnings['mempools']   = self._safe_fetch(svc.get_device_mempools,   device_id, label='mempools')
        processors, warnings['processors'] = self._safe_fetch(svc.get_device_processors, device_id, label='processors')
        storages,   warnings['storages']   = self._safe_fetch(svc.get_device_storage,    device_id, label='storages')
        alerts,     warnings['alerts']     = self._safe_fetch(svc.get_device_alerts,     device_id, label='alerts')
        ports,      warnings['ports']      = self._safe_fetch(svc.get_device_ports,      device_id, label='ports')
        sensors,    warnings['sensors']    = self._safe_fetch(svc.get_device_sensors,    device_id, label='sensors')
        statuses,   warnings['statuses']   = self._safe_fetch(svc.get_device_status,     device_id, label='statuses')
        neighbours, warnings['neighbours'] = self._safe_fetch(svc.get_device_neighbours, device_id, label='neighbours')
        warnings = {k: v for k, v in warnings.items() if v}

        cpu_avg = 0
        if processors:
            usages = [int(p.get('processor_usage', 0) or 0) for p in processors]
            cpu_avg = int(sum(usages) / len(usages)) if usages else 0

        mem_perc = mem_used_gb = mem_total_gb = 0
        mem_descr = ''
        if mempools:
            physical = next(
                (m for m in mempools if 'Physical' in m.get('mempool_descr', '')),
                mempools[0],
            )
            mem_perc     = int(physical.get('mempool_perc',  0) or 0)
            mem_descr    = physical.get('mempool_descr', '')
            mem_used_gb  = round(int(physical.get('mempool_used',  0) or 0) / (1024 ** 3), 1)
            mem_total_gb = round(int(physical.get('mempool_total', 0) or 0) / (1024 ** 3), 1)

        alerts_failed = [a for a in alerts if a.get('status') == 'failed']
        ports_up      = [p for p in ports  if p.get('ifOperStatus') == 'up']
        ports_down    = [p for p in ports  if p.get('ifOperStatus') == 'down']

        sensor_groups = {}
        for s in sensors:
            sensor_groups.setdefault(s.get('sensor_type', 'other'), []).append(s)

        graph_types = [
            ('device_ucd_cpu', 'CPU',     'fa-microchip'),
            ('device_mempool', 'Memory',  'fa-database'),
            ('device_storage', 'Storage', 'fa-hdd-o'),
            ('device_bits',    'Traffic', 'fa-exchange'),
            ('device_ping',    'Ping',    'fa-heartbeat'),
            ('device_uptime',  'Uptime',  'fa-clock-o'),
        ]

        # FIX #10 — Format uptime as human-readable string
        uptime_str = self._format_uptime(device.get('uptime') if device else None)

        values = {
            'device':        device,
            'addresses':     addresses,
            'mempools':      mempools,
            'processors':    processors,
            'storages':      storages,
            'alerts':        alerts,
            'alerts_failed': alerts_failed,
            'ports':         ports,
            'ports_up':      ports_up,
            'ports_down':    ports_down,
            'sensors':       sensors,
            'sensor_groups': sensor_groups,
            'statuses':      statuses,
            'neighbours':    neighbours,
            'cpu_avg':       cpu_avg,
            'mem_perc':      mem_perc,
            'mem_descr':     mem_descr,
            'mem_used_gb':   mem_used_gb,
            'mem_total_gb':  mem_total_gb,
            'graph_types':   graph_types,
            'device_id':     device_id,
            'uptime_str':    uptime_str,
            'error':         error,
            'warnings':      warnings,
            'page_name':     'observium_device_detail',
        }
        return request.render('we_portal_observium.observium_device_detail_template', values)

    @staticmethod
    def _format_uptime(seconds):
        """Convert raw uptime seconds to a human-readable string like '14d 6h 56m'."""
        try:
            secs = int(seconds or 0)
        except (TypeError, ValueError):
            return 'N/A'
        if secs <= 0:
            return 'N/A'
        days    = secs // 86400
        hours   = (secs % 86400) // 3600
        minutes = (secs % 3600) // 60
        parts = []
        if days:
            parts.append('%dd' % days)
        if hours:
            parts.append('%dh' % hours)
        if minutes or not parts:
            parts.append('%dm' % minutes)
        return ' '.join(parts)

    # ------------------------------------------------------------------
    # Device graphs  /my/observium/<device_id>/graph/<graph_type>
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>/graph/<string:graph_type>',
                type='http', auth='user', website=True)
    def device_graph(self, device_id, graph_type, period='-1d', **kw):
        if not self._check_device_access(device_id, self._get_partner_group_code()):
            raise Forbidden()

        allowed_types = {
            'device_ucd_cpu', 'device_mempool', 'device_bits', 'device_ping',
            'device_uptime', 'device_storage', 'device_netstats_bits',
        }
        if graph_type not in allowed_types:
            raise NotFound()
        try:
            image_bytes, content_type = self._observium().get_graph_image(
                device_id, graph_type, period=period)
        except requests.exceptions.RequestException as e:
            _logger.error('Observium graph fetch error: %s', e)
            raise NotFound()
        # FIX #6 — increase cache to match Observium's 5-minute poll cycle
        return Response(image_bytes, content_type=content_type,
                        headers={'Cache-Control': 'private, max-age=300'})

    # ------------------------------------------------------------------
    # Port graphs  /my/observium/<device_id>/port/<port_id>/graph/<graph_type>
    # FIX #8 — device_id is now part of the URL so we reuse _check_device_access
    # instead of fetching all ports to find the parent device.
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>/port/<string:port_id>/graph/<string:graph_type>',
                type='http', auth='user', website=True)
    def port_graph(self, device_id, port_id, graph_type, period='-1d', **kw):
        allowed_types = {'port_bits', 'port_upkts', 'port_errors', 'port_nonecast'}
        if graph_type not in allowed_types:
            raise NotFound()

        # Security: reuse device-level access check — no need to fetch all ports
        group_code = self._get_partner_group_code()
        if not self._check_device_access(device_id, group_code):
            raise Forbidden()

        try:
            image_bytes, content_type = self._observium().get_port_graph_image(
                port_id, graph_type, period=period)
        except requests.exceptions.RequestException as e:
            _logger.error('Observium port graph error: %s', e)
            raise NotFound()
        return Response(image_bytes, content_type=content_type,
                        headers={'Cache-Control': 'private, max-age=300'})

    # ------------------------------------------------------------------
    # Alerts  /my/observium/alerts
    # ------------------------------------------------------------------

    @http.route('/my/observium/alerts', type='http', auth='user', website=True)
    def alert_list(self, status='failed', **kw):
        group_code = self._get_partner_group_code()
        svc = self._observium()
        alerts = []
        error = None

        allowed_device_ids = None
        if group_code:
            try:
                devices = svc.get_devices(group=group_code)
                allowed_device_ids = {str(d.get('device_id')) for d in devices}
            except Exception as e:
                error = _('Could not load device list: %s') % str(e)

        try:
            all_alerts = svc.get_alerts(status=status or 'failed')
            if allowed_device_ids is not None:
                alerts = [a for a in all_alerts
                          if str(a.get('device_id')) in allowed_device_ids]
            else:
                alerts = all_alerts
        except Exception as e:
            error = _('Could not load alerts: %s') % str(e)
            _logger.exception('Alert list error')

        values = {
            'alerts':      alerts,
            'alert_count': len(alerts),
            'status':      status,
            'error':       error,
            'page_name':   'observium_alerts',
        }
        return request.render('we_portal_observium.observium_alerts_template', values)

    # ------------------------------------------------------------------
    # Services placeholder  /my/services
    # ------------------------------------------------------------------

    @http.route('/my/services', type='http', auth='user', website=True)
    def services(self, **kw):
        values = {'page_name': 'services'}
        return request.render('we_portal_observium.services_placeholder_template', values)
