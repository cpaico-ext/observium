# -*- coding: utf-8 -*-
{
    'name': 'Base Adapter',
    'version': '19.0.1.0.0',
    'summary': 'Adapt base modules for ON Empresas',
    'description': """
This module extends and adapts Odoo's base kernel functionality for ON Empresas
It introduces model inheritances, utilities, and algorithms to subtly modify
core flows while maintaining compatibility with Odoo's standard framework.
    """,
    "author": "Carlos Enrique Paico Zavala, " "ON Empresas",
    'website': 'https://www.onempresa.com',
    'category': 'Base',
    'license': 'LGPL-3',
    'development_status': 'Beta',
    'maintainers': ['EnriqueCoDev'],
    'contributors': [
        'Carlos Enrique Paico Zavala <EnriqueZav96@gmail.com>',
    ],
    'depends': [
        'base',
        'contacts',
        'portal',
    ],
    'data': [
        'security/security.xml',
        
        'data/res_partner_data.xml',
        
        'templates/login_templates.xml',
        'templates/portal_my_home.xml',
        
        'views/ir_views.xml',
        'views/ir_module_module_views.xml',
    ],
    'demo': [
        'demo/res_partner_data.xml',
        'demo/res_currency_data.xml'
    ],
    'application': False,
    'sequence': 1
}
