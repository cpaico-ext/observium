# -*- coding: utf-8 -*-
import logging

import requests
from werkzeug.exceptions import Forbidden, NotFound

from odoo import http
from odoo.tools.translate import _
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Users that belong to this group are considered "internal admins".
# Portal users (base.group_portal) are always filtered by group_code.
_ADMIN_GROUP = 'base.group_system'


class ObserviumPortalController(http.Controller):

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_portal_user(self):
        """True when the current user is a portal-only user (not an internal employee)."""
        return request.env.user.has_group('base.group_portal')

    def _get_partner_group_code(self):
        """
        Returns (group_code, is_portal) for the current user.

        Resolution order:
          1. partner.observium_group_code
          2. partner.parent_id.observium_group_code  (contact under a company)
          3. portal.partner.role → client.observium_group_code  (role-based fallback)

        Returns (str|None, bool):
          - group_code: the Observium group ID or None
          - is_portal: True if the user is a portal user (no admin bypass)
        """
        is_portal = self._is_portal_user()
        partner   = request.env.user.partner_id

        code = (
            partner.observium_group_code
            or (partner.parent_id.observium_group_code if partner.parent_id else None)
        )
        if not code:
            role = request.env['portal.partner.role'].sudo().search([
                '|',
                ('contact_ids', 'in', partner.id),
                ('client_id',   '=',  partner.id),
            ], limit=1)
            if role:
                code = role.client_id.observium_group_code or None

        return code, is_portal

    def _observium(self):
        return request.env['observium.service'].sudo()

    def _resolve_access(self, device_id=None):
        """
        Central access-resolution method. Results are cached per HTTP request
        to avoid repeated API calls when multiple graphs load on the same page.
        """
        # Request-level cache key
        cache_key = '_obs_access_' + str(device_id or '__nodev__')
        cached = getattr(request, cache_key, None)
        if cached is not None:
            return cached

        group_code, is_portal = self._get_partner_group_code()

        if is_portal and not group_code:
            result = {
                'group_code':      None,
                'is_portal':       True,
                'identity_error':  _(
                    'Your account has not been linked to a monitoring group yet. '
                    'Please contact your administrator.'
                ),
                'device':          None,
            }
            setattr(request, cache_key, result)
            return result

        result = {
            'group_code':     group_code,
            'is_portal':      is_portal,
            'identity_error': None,
            'device':         None,
        }

        if device_id is not None:
            device = self._observium().get_device_for_group(device_id, group_code)
            if device is None and group_code:
                raise Forbidden()
            result['device'] = device

        setattr(request, cache_key, result)
        return result

    def _safe_fetch(self, fn, *args, label='data', **kwargs):
        """
        Call fn(*args, **kwargs) without letting it crash the page.
        Returns (result, None) on success or ([], error_string) on failure.
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
        group_code, is_portal = self._get_partner_group_code()

        # Portal user with no group configured → show identity error page
        if is_portal and not group_code:
            return request.render('we_portal_observium.observium_devices_template', {
                'devices':      [],
                'device_count': 0,
                'group_code':   None,
                'is_admin':     False,
                'error':        None,
                'identity_error': _(
                    'Your account has not been linked to a monitoring group yet. '
                    'Please contact your administrator.'
                ),
                'page_name': 'observium_devices',
            })

        devices = []
        error   = None
        try:
            # Admin without group_code → no filter (all devices)
            # Everyone else          → filtered by group
            devices = self._observium().get_devices(group=group_code or None)
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

        values = {
            'devices':        devices,
            'device_count':   len(devices),
            'group_code':     group_code,
            'is_admin':       not is_portal,
            'error':          error,
            'identity_error': None,
            'page_name':      'observium_devices',
        }
        return request.render('we_portal_observium.observium_devices_template', values)

    # ------------------------------------------------------------------
    # Device details /my/observium/<device_id>
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>', type='http', auth='user', website=True)
    def device_detail(self, device_id, **kw):
        # _resolve_access handles: identity error, access check, AND device fetch
        # — all in a single Observium API call when group_code is set.
        access = self._resolve_access(device_id=device_id)

        if access['identity_error']:
            return request.render('we_portal_observium.observium_devices_template', {
                'devices': [], 'device_count': 0, 'group_code': None,
                'is_admin': False, 'error': None,
                'identity_error': access['identity_error'],
                'page_name': 'observium_devices',
            })

        svc    = self._observium()
        device = access['device']
        error  = None

        # Admin without group_code: device wasn't fetched yet by _resolve_access
        if device is None and not access['group_code']:
            try:
                device = svc.get_device(device_id)
                if not device:
                    raise NotFound()
            except (NotFound, Forbidden):
                raise
            except Exception as e:
                error = _('Unexpected error: %s') % str(e)
                _logger.exception('Observium device detail error')


        warnings = {}
        from concurrent.futures import ThreadPoolExecutor, as_completed

        tasks = {
            'addresses':  lambda: self._safe_fetch(svc.get_device_addresses,  device_id, label='addresses'),
            'mempools':   lambda: self._safe_fetch(svc.get_device_mempools,   device_id, label='mempools'),
            'processors': lambda: self._safe_fetch(svc.get_device_processors, device_id, label='processors'),
            'storages':   lambda: self._safe_fetch(svc.get_device_storage,    device_id, label='storages'),
            'alerts':     lambda: self._safe_fetch(svc.get_device_alerts,     device_id, label='alerts'),
            'ports':      lambda: self._safe_fetch(svc.get_device_ports,      device_id, label='ports'),
            'sensors':    lambda: self._safe_fetch(svc.get_device_sensors,    device_id, label='sensors'),
            'statuses':   lambda: self._safe_fetch(svc.get_device_status,     device_id, label='statuses'),
            'neighbours': lambda: self._safe_fetch(svc.get_device_neighbours, device_id, label='neighbours'),
        }
        results = {}
        with ThreadPoolExecutor(max_workers=9) as executor:
            futures = {executor.submit(fn): key for key, fn in tasks.items()}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    data, err = future.result()
                except Exception as e:
                    data, err = [], str(e)
                results[key] = data
                if err:
                    warnings[key] = err

        addresses  = results['addresses']
        mempools   = results['mempools']
        processors = results['processors']
        storages   = results['storages']
        alerts     = results['alerts']
        ports      = results['ports']
        sensors    = results['sensors']
        statuses   = results['statuses']
        neighbours = results['neighbours']

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

        # Full catalogue: graph_key (from API graphs{}) → (type_param, label, icon, group)
        # group: 'performance' | 'sensors' | 'network' | 'system'
        GRAPH_CATALOGUE = {
            'processor':    ('device_processor',    'CPU',          'fa-microchip',       'performance'),
            'mempool':      ('device_mempool',       'Memory',       'fa-database',        'performance'),
            'storage':      ('device_storage',       'Storage',      'fa-hdd-o',           'performance'),
            'bits':         ('device_bits',          'Traffic',      'fa-exchange',        'network'),
            'ping':         ('device_ping',          'Ping',         'fa-heartbeat',       'network'),
            'ping_snmp':    ('device_ping_snmp',     'Ping SNMP',    'fa-wifi',            'network'),
            'uptime':       ('device_uptime',        'Uptime',       'fa-clock-o',         'system'),
            'availability': ('device_availability',  'Availability', 'fa-check-circle',    'system'),
            'temperature':  ('device_temperature',   'Temperature',  'fa-thermometer-half','sensors'),
            'fanspeed':     ('device_fanspeed',      'Fan Speed',    'fa-refresh',         'sensors'),
            'voltage':      ('device_voltage',       'Voltage',      'fa-bolt',            'sensors'),
            'current':      ('device_current',       'Current',      'fa-plug',            'sensors'),
            'power':        ('device_power',         'Power',        'fa-fire',            'sensors'),
            'frequency':    ('device_frequency',     'Frequency',    'fa-signal',          'sensors'),
            'dbm':          ('device_dbm',           'dBm',          'fa-rss',             'sensors'),
            'wavelength':   ('device_wavelength',    'Wavelength',   'fa-tint',            'sensors'),
            'dhcp_leases':  ('device_dhcp_leases',   'DHCP Leases',  'fa-list',            'system'),
            'fdb_count':    ('device_fdb_count',     'FDB Count',    'fa-table',           'system'),
        }

        # Build dynamic graph list from what this device actually has enabled
        # NOTE: GET /api/v0/devices?group=X&device_id=Y does not return graphs{}.
        # If empty, fetch the full device individually to get graphs{}.
        device_graphs_raw = device.get('graphs', {}) if device else {}
        if not device_graphs_raw and device:
            try:
                full_device = svc.get_device(device_id)
                if full_device:
                    device_graphs_raw = full_device.get('graphs', {})
                    # Merge graphs into device so template has full data too
                    device['graphs'] = device_graphs_raw
            except Exception:
                pass

        enabled_keys = {
            k for k, v in device_graphs_raw.items()
            if isinstance(v, dict) and str(v.get('enabled', '0')) == '1'
        }
        _logger.info('Observium device %s enabled_keys: %s', device_id, sorted(enabled_keys))

        # Order: performance → network → system → sensors
        GROUP_ORDER = ['performance', 'network', 'system', 'sensors']
        graph_types = []
        for group in GROUP_ORDER:
            for key, (type_param, label, icon, grp) in GRAPH_CATALOGUE.items():
                if grp == group and key in enabled_keys:
                    graph_types.append((type_param, label, icon, group))

        # Fallback: if device has no graphs{} data, use minimal hardcoded set
        if not graph_types:
            graph_types = [
                ('device_processor',  'CPU',     'fa-microchip', 'performance'),
                ('device_mempool',    'Memory',  'fa-database',  'performance'),
                ('device_bits',       'Traffic', 'fa-exchange',  'network'),
                ('device_ping',       'Ping',    'fa-heartbeat', 'network'),
                ('device_uptime',     'Uptime',  'fa-clock-o',   'system'),
            ]

        # Header mini-graphs: always these 4 if available, else first 4 from graph_types
        HEADER_PREFERENCE = ['uptime', 'mempool', 'processor', 'bits']
        header_graphs = []
        for key in HEADER_PREFERENCE:
            if key in enabled_keys and key in GRAPH_CATALOGUE:
                tp, lbl, ico, grp = GRAPH_CATALOGUE[key]
                header_graphs.append((tp, lbl, ico))
        if not header_graphs:
            header_graphs = [(t, l, i) for t, l, i, _ in graph_types[:4]]

        # Format uptime as human-readable string
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
            'header_graphs': header_graphs,
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
    # Access check reuses _resolve_access (one combined API call).
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>/graph/<string:graph_type>',
                type='http', auth='user', website=True)
    def device_graph(self, device_id, graph_type, period='-1d', **kw):
        allowed_types = {
            'device_processor', 'device_mempool', 'device_bits', 'device_ping',
            'device_ping_snmp', 'device_uptime', 'device_availability',
            'device_storage', 'device_netstats_bits',
            'device_temperature', 'device_fanspeed', 'device_voltage',
            'device_current', 'device_power', 'device_frequency',
            'device_dbm', 'device_wavelength',
            'device_dhcp_leases', 'device_fdb_count', 'device_status',
        }
        if graph_type not in allowed_types:
            raise NotFound()

        # _resolve_access raises Forbidden if the device is not accessible.
        # We don't need the returned device data here, just the access gate.
        self._resolve_access(device_id=device_id)

        try:
            image_bytes, content_type = self._observium().get_graph_image(
                device_id, graph_type, period=period)
        except requests.exceptions.RequestException as e:
            _logger.error('Observium graph fetch error: %s', e)
            raise NotFound()
        return Response(image_bytes, content_type=content_type,
                        headers={'Cache-Control': 'private, max-age=300'})

    # ------------------------------------------------------------------
    # Port graphs  /my/observium/<device_id>/port/<port_id>/graph/<graph_type>
    # device_id in URL → reuse device-level access gate, no port enumeration.
    # ------------------------------------------------------------------

    @http.route('/my/observium/<string:device_id>/port/<string:port_id>/graph/<string:graph_type>',
                type='http', auth='user', website=True)
    def port_graph(self, device_id, port_id, graph_type, period='-1d', **kw):
        allowed_types = {'port_bits', 'port_upkts', 'port_errors', 'port_nonecast'}
        if graph_type not in allowed_types:
            raise NotFound()

        self._resolve_access(device_id=device_id)

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
        group_code, is_portal = self._get_partner_group_code()
        svc    = self._observium()
        alerts = []
        error  = None

        # Portal user without group → identity error
        if is_portal and not group_code:
            return request.render('we_portal_observium.observium_alerts_template', {
                'alerts': [], 'alert_count': 0, 'status': status,
                'error': None,
                'identity_error': _(
                    'Your account has not been linked to a monitoring group yet. '
                    'Please contact your administrator.'
                ),
                'page_name': 'observium_alerts',
            })

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
            'alerts':         alerts,
            'alert_count':    len(alerts),
            'status':         status,
            'error':          error,
            'identity_error': None,
            'page_name':      'observium_alerts',
        }
        return request.render('we_portal_observium.observium_alerts_template', values)

    # ------------------------------------------------------------------
    # Services placeholder  /my/services
    # ------------------------------------------------------------------

    @http.route('/my/services', type='http', auth='user', website=True)
    def services(self, **kw):
        values = {'page_name': 'services'}
        return request.render('we_portal_observium.services_placeholder_template', values)