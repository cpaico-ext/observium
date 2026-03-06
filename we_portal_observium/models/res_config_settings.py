# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    observium_enabled = fields.Boolean(
        string="Enable Observium Integration",
        config_parameter="observium.enabled",
    )
    observium_environment = fields.Selection(
        selection=[('dev', 'Development'), ('prod', 'Production')],
        string="Active Environment",
        config_parameter="observium.environment",
        default='dev',
    )
    observium_dev_url = fields.Char(string="Dev URL", config_parameter="observium.dev.url")
    observium_dev_username = fields.Char(string="Dev User", config_parameter="observium.dev.username")
    observium_dev_password = fields.Char(string="Dev Password", config_parameter="observium.dev.password")
    observium_prod_url = fields.Char(string="Prod URL", config_parameter="observium.prod.url")
    observium_prod_username = fields.Char(string="Prod User", config_parameter="observium.prod.username")
    observium_prod_password = fields.Char(string="Prod Password", config_parameter="observium.prod.password")
    observium_verify_ssl = fields.Boolean(string="Verify SSL Certificate", config_parameter="observium.verify_ssl")
    observium_timeout = fields.Integer(string="Timeout (seconds)", default=30, config_parameter="observium.timeout")

    @api.constrains("observium_timeout")
    def _check_timeout(self):
        for record in self:
            if record.observium_timeout and record.observium_timeout <= 0:
                raise ValidationError("Timeout must be greater than 0 seconds.")
