# -*- coding: utf-8 -*-
{
    'name': 'Portal Base',
    'version': '19.0.1.0.0',
    'summary': 'Generic portal dashboard framework with role-based access control',
    'description': '''
        Base module for managing portal dashboards and access control.
        Provides the framework for assigning dashboards to partners through roles.
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
        'base',
        'portal',
        'mail',
        'contacts',
        'base_adapter',
    ],
    'data': [
        # Security
        'security/security.xml',
        'security/ir.model.access.csv',
        # Views - Backend
        'views/res_partner.xml',
        'views/menu.xml',
        'views/portal_dashboard_views.xml',
        'views/portal_dashboard_element_views.xml',
        'views/portal_partner_role_views.xml',
        # Views - Portal (frontend)
        'views/portal_home_template.xml',
        'views/portal_dashboard_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'we_portal_base/static/src/css/portal_base.css',
        ],
    },
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
