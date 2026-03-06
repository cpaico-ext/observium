# -*- coding: utf-8 -*-
import base64
import logging

import requests

from odoo import _, api, models

_logger = logging.getLogger(__name__)

API_PATH = '/api/v0'


class ObserviumService(models.AbstractModel):
    _name = 'observium.service'
    _description = 'Observium API Service'

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @api.model
    def _get_config(self):
        get = self.env['ir.config_parameter'].sudo().get_param

        enabled = get('observium.enabled', 'False').lower() == 'true'
        if not enabled:
            raise ValueError(
                _('Observium integration is disabled. Please enable it in Settings.')
            )

        env = get('observium.environment', 'dev')  # 'dev' | 'prod'

        url      = get(f'observium.{env}.url',      '').rstrip('/')
        username = get(f'observium.{env}.username', '')
        password = get(f'observium.{env}.password', '')

        verify_ssl = get('observium.verify_ssl', 'False').lower() == 'true'
        timeout    = int(get('observium.timeout', '30'))

        if not url or not username or not password:
            raise ValueError(
                _('Observium (%s) is not fully configured. '
                  'Please set URL, username and password in Settings.') % env.upper()
            )

        return {
            'url': url,
            'username': username,
            'password': password,
            'verify_ssl': verify_ssl,
            'timeout': timeout,
        }

    @api.model
    def _build_auth_header(self, cfg):
        credentials = '{}:{}'.format(cfg['username'], cfg['password'])
        token = base64.b64encode(credentials.encode('utf-8')).decode('ascii')
        return {'Authorization': 'Basic ' + token}

    @api.model
    def _get(self, endpoint, params=None):
        cfg = self._get_config()
        url = '{}{}/{}'.format(cfg['url'], API_PATH, endpoint.lstrip('/'))
        headers = self._build_auth_header(cfg)
        _logger.info('Observium GET %s params=%s', url, params)
        response = requests.get(
            url, headers=headers, params=params or {},
            timeout=cfg['timeout'], verify=cfg['verify_ssl'],
        )
        response.raise_for_status()
        return response.json()

    @api.model
    def _get_image(self, endpoint, params=None):
        cfg = self._get_config()
        url = '{}/{}'.format(cfg['url'].rstrip('/'), endpoint.lstrip('/'))
        headers = self._build_auth_header(cfg)
        response = requests.get(
            url, headers=headers, params=params or {},
            timeout=cfg['timeout'], verify=cfg['verify_ssl'],
        )
        response.raise_for_status()
        return response.content, response.headers.get('Content-Type', 'image/png')

    @staticmethod
    def _dict_or_list(data):
        """Normalizes responses that may come as a dict {id: obj} or as a list."""
        if isinstance(data, dict):
            return list(data.values())
        if isinstance(data, list):
            return data
        return []

    # ------------------------------------------------------------------
    # Devices
    # ------------------------------------------------------------------

    @api.model
    def get_devices(self, group=None):
        params = {}
        if group:
            params['group'] = group
        data = self._get('devices', params=params)
        devices_raw = data.get('devices', {})

        if isinstance(devices_raw, dict):
            for dev_id, dev in devices_raw.items():
                dev.setdefault('device_id', dev_id)
            devices = list(devices_raw.values())
        else:
            devices = devices_raw

        return sorted(devices, key=lambda d: d.get('hostname', '').lower())

    @api.model
    def get_device(self, device_id):
        """
        Fetch a single device by ID using the direct /devices/<id> endpoint.
        Returns None if the device does not exist (404).
        Does NOT enforce group membership — use get_device_for_group() for that.
        """
        try:
            data = self._get('devices/{}'.format(device_id))
            device = data.get('device') or data.get('devices', {}).get(str(device_id))
            if device:
                device.setdefault('device_id', str(device_id))
            return device
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    @api.model
    def get_device_for_group(self, device_id, group_code):
        """
        Fetch a single device AND verify it belongs to group_code in one API call.

        Uses GET /api/v0/devices?group=<group>&device_id=<id>
        Observium returns count=0 when the device is not in the group,
        so this simultaneously handles access control and data retrieval.

        Returns:
            dict  — device data if found and accessible
            None  — device does not exist or is not in the group (caller raises 403/404)

        When group_code is None (admin without a group restriction) it falls
        back to get_device() so admins always see all devices.
        """
        if not group_code:
            return self.get_device(device_id)

        data = self._get('devices', params={'group': group_code, 'device_id': device_id})
        devices_raw = data.get('devices', {})
        if not devices_raw:
            return None

        if isinstance(devices_raw, dict):
            device = devices_raw.get(str(device_id))
        else:
            device = devices_raw[0] if devices_raw else None

        if device:
            device.setdefault('device_id', str(device_id))
        return device

    @api.model
    def get_device_addresses(self, device_id):
        data = self._get('address', params={'device_id': device_id})
        return self._dict_or_list(data.get('addresses', []))

    @api.model
    def get_device_mempools(self, device_id):
        data = self._get('mempools', params={'device_id': device_id})
        return self._dict_or_list(data.get('entries', {}))

    @api.model
    def get_device_processors(self, device_id):
        data = self._get('processors', params={'device_id': device_id})
        return self._dict_or_list(data.get('entries', {}))

    @api.model
    def get_device_storage(self, device_id):
        data = self._get('storage', params={'device_id': device_id})
        return self._dict_or_list(data.get('storages', {}))

    @api.model
    def get_graph_image(self, device_id, graph_type, period='-1d'):
        params = {
            'device': device_id,
            'type': graph_type,
            'from': period,
            'to': 'now',
            'width': 600,
            'height': 200,
            'legend': 'yes',
        }
        return self._get_image('graph.php', params=params)

    # ------------------------------------------------------------------
    # Alerts
    # ------------------------------------------------------------------

    @api.model
    def get_alerts(self, device_id=None, status=None, entity_type=None,
                   alert_test_id=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if status:
            params['status'] = status
        if entity_type:
            params['entity_type'] = entity_type
        if alert_test_id:
            params['alert_test_id'] = alert_test_id
        data = self._get('alerts', params=params)
        return self._dict_or_list(data.get('alerts', {}))

    @api.model
    def get_device_alerts(self, device_id, status='failed'):
        return self.get_alerts(device_id=device_id, status=status)

    @api.model
    def get_alert_checks(self, alert_check_id=None):
        endpoint = 'alert_checks/{}'.format(alert_check_id) if alert_check_id else 'alert_checks'
        data = self._get(endpoint)
        if alert_check_id:
            return data.get('alert_check')
        return self._dict_or_list(data.get('alert_checks', {}))

    # ------------------------------------------------------------------
    # Ports
    # ------------------------------------------------------------------

    @api.model
    def get_ports(self, device_id=None, state=None, errors=None, fields=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if state:
            params['state'] = state
        if errors:
            params['errors'] = errors
        if fields:
            params['fields'] = ','.join(fields) if isinstance(fields, list) else fields
        data = self._get('ports', params=params)
        return self._dict_or_list(data.get('ports', {}))

    @api.model
    def get_device_ports(self, device_id, state=None):
        return self.get_ports(device_id=device_id, state=state)

    @api.model
    def get_port_graph_image(self, port_id, graph_type='port_bits', period='-1d'):
        params = {
            'id': port_id,
            'type': graph_type,
            'from': period,
            'to': 'now',
            'width': 600,
            'height': 200,
            'legend': 'yes',
        }
        return self._get_image('graph.php', params=params)

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    @api.model
    def get_sensors(self, device_id=None, sensor_type=None, event=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if sensor_type:
            params['sensor_type'] = sensor_type
        if event:
            params['event'] = event
        data = self._get('sensors', params=params)
        return self._dict_or_list(data.get('sensors', {}))

    @api.model
    def get_device_sensors(self, device_id):
        return self.get_sensors(device_id=device_id)

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @api.model
    def get_status(self, device_id=None, status_class=None, event=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if status_class:
            params['class'] = status_class
        if event:
            params['event'] = event
        data = self._get('status', params=params)
        return self._dict_or_list(data.get('status', {}))

    @api.model
    def get_device_status(self, device_id):
        return self.get_status(device_id=device_id)

    # ------------------------------------------------------------------
    # Inventory
    # ------------------------------------------------------------------

    @api.model
    def get_inventory(self, device_id=None, physical_class=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if physical_class:
            params['entPhysicalClass'] = physical_class
        data = self._get('inventory', params=params)
        return self._dict_or_list(data.get('inventory', {}))

    @api.model
    def get_device_inventory(self, device_id):
        return self.get_inventory(device_id=device_id)

    # ------------------------------------------------------------------
    # Neighbours
    # ------------------------------------------------------------------

    @api.model
    def get_neighbours(self, device_id=None, protocol=None, active=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if protocol:
            params['protocol'] = protocol
        if active is not None:
            params['active'] = active
        data = self._get('neighbours', params=params)
        return self._dict_or_list(data.get('neighbours', {}))

    @api.model
    def get_device_neighbours(self, device_id):
        return self.get_neighbours(device_id=device_id, active=1)

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    @api.model
    def get_counters(self, device_id=None, counter_class=None, event=None):
        params = {}
        if device_id:
            params['device_id'] = device_id
        if counter_class:
            params['counter_class'] = counter_class
        if event:
            params['counter_event'] = event
        data = self._get('counters', params=params)
        return self._dict_or_list(data.get('counters', {}))

    # ------------------------------------------------------------------
    # Bills
    # ------------------------------------------------------------------

    @api.model
    def get_bills(self):
        data = self._get('bills')
        return self._dict_or_list(data.get('bills', {}))

    # ------------------------------------------------------------------
    # Groups
    # ------------------------------------------------------------------

    @api.model
    def get_groups(self, group_id=None):
        endpoint = 'groups/{}'.format(group_id) if group_id else 'groups'
        data = self._get(endpoint)
        if group_id:
            return data.get('group')
        return self._dict_or_list(data.get('groups', {}))

    @api.model
    def get_group_by_id(self, group_id):
        """Return group dict for the given numeric group_id, or None if not found."""
        return self.get_groups(group_id=group_id)

    # ------------------------------------------------------------------
    # Generic entity
    # ------------------------------------------------------------------

    @api.model
    def get_entity(self, entity_type, entity_id):
        data = self._get('entity/{}/{}'.format(entity_type, entity_id))
        return data.get('entity')
