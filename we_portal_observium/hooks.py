# -*- coding: utf-8 -*-
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Initialize Observium API configuration parameters on first install.
    Only creates parameters that do not already exist, so re-installation
    or upgrades never overwrite values set by the administrator.
    """
    params = [
        # General control
        ('observium.enabled',     'False'),
        ('observium.environment', 'dev'),
        # Development environment
        ('observium.dev.url',      'http://127.0.0.1'),
        ('observium.dev.username', 'observium'),
        ('observium.dev.password', 'password'),
        # Production environment
        ('observium.prod.url',      'http://127.0.0.1'),
        ('observium.prod.username', 'observium'),
        ('observium.prod.password', 'password'),
        # Shared
        ('observium.verify_ssl', 'False'),
        ('observium.timeout',    '30'),
    ]
    IrParam = env['ir.config_parameter']
    for key, default_value in params:
        if not IrParam.search([('key', '=', key)], limit=1):
            IrParam.create({'key': key, 'value': default_value})
            _logger.info('Observium: created config parameter %s', key)