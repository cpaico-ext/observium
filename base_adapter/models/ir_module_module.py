# -*- coding: utf-8 -*-

from odoo import api, fields, models, modules, tools, _
import operator

class IrModule(models.Model):
    _inherit = 'ir.module.module'

    # Field to identify if a newer version is available on the local file system
    local_updatable = fields.Boolean('Local updatable', default=False, store=True)

    def module_multi_uninstall(self):
        """ 
        Perform mass uninstallation of selected modules.
        Filters out core system modules to prevent accidental system failure.
        """
        # Exclude critical modules 'base' and 'web' from mass uninstallation
        target_modules = self.filtered(lambda m: m.name not in ['base', 'web'] and m.state == 'installed')
        if target_modules:
            return target_modules.button_immediate_uninstall()

    def module_multi_refresh_po(self):
        """ 
        Refresh translations for the current user language.
        In Odoo 18, this updates the JSON translation fields directly.
        """
        lang = self.env.user.lang or 'en_US'
        installed_modules = self.filtered(lambda r: r.state == 'installed')
        
        if installed_modules:
            # Re-load PO files from the module folder and overwrite existing terms
            installed_modules._update_translations(filter_lang=lang, overwrite=True)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _("Translations Refreshed"),
                'message': _("The language files have been successfully reloaded. "
                             "An app upgrade is recommended to apply all changes."),
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.act_window_close'},
            }
        }

    def button_get_po(self):
        """ 
        Redirects to the translation export wizard with the current module and language.
        """
        self.ensure_one()
        # Ensure the XML ID matches the record defined in base_adapter/views/ir_views.xml
        action = self.env.ref('base_adapter.action_server_module_multi_get_po').read()[0]
        action['context'] = dict(self.env.context, default_lang=self.env.user.lang)
        return action

    def update_list(self):
        """ 
        Override to check for version increments on the file system compared to the DB.
        """
        res = super(IrModule, self).update_list()
        
        # Load all known modules into a dictionary to minimize DB queries inside the loop
        known_mods = self.search([])
        known_mods_dict = {mod.name: mod for mod in known_mods}
        
        default_version = modules.adapt_version('1.0')
        
        for mod_name in modules.get_modules():
            mod = known_mods_dict.get(mod_name)
            if not mod:
                continue
                
            try:
                # Retrieve module manifest information from disk
                info = self.get_module_info(mod_name)
                disk_version = info.get('version', default_version)
                
                # 'latest_version' in the database stores the currently installed version
                installed_version = mod.latest_version
                
                is_updatable = False
                if disk_version and installed_version:
                    # Compare version strings (e.g., '18.0.1.1' > '18.0.1.0')
                    if operator.gt(disk_version, installed_version):
                        is_updatable = True
                
                # Update only if the state has changed to optimize performance
                if mod.local_updatable != is_updatable:
                    mod.local_updatable = is_updatable
            except Exception:
                # Skip modules with corrupted manifests or inaccessible paths
                continue
        return res