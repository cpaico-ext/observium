# -*- coding: utf-8 -*-
{
    'name': 'Portal Observium',
    'version': '19.0.1.0.0',
    'summary': 'Observium network monitoring integration for the client portal',
    'description': '''
        Integrates the Observium REST API with the Odoo portal so that clients
        can view their monitored network devices, metrics and graphs directly
        from their portal account.
    ''',
    "author": "Carlos Enrique Paico Zavala, " "ON Empresas",
    'website': 'https://www.onempresa.com',
    'category': 'Portal',
    'license': 'LGPL-3',
    "development_status": "Beta",
    'maintainers': ['EnriqueCoDev'],
    'contributors': [
        'Carlos Enrique Paico Zavala <EnriqueZav96@gmail.com>',
    ],
    'depends': [
        'we_portal_base',
    ],
    'data': [
        # Security
        'security/ir.model.access.csv',
        # Backend views
        'views/res_config_settings.xml',
        'views/res_partner_views.xml',
        # Portal templates
        'views/observium_devices_template.xml',
        'views/observium_device_detail_template.xml',

        'views/observium_alerts_template.xml',

        'views/dashboard_element_observium_template.xml',
        'views/dashboard_element_alerts_template.xml',
        'views/dashboard_element_services_template.xml',

        'views/services_placeholder_template.xml',
        'views/observium_dashboard_inherit_template.xml',

        # Data
        'data/portal_dashboard_data.xml',
    ],
    'demo': [
        'demo/portal_demo_data.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_frontend': [
            'we_portal_observium/static/src/css/observium_portal.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}