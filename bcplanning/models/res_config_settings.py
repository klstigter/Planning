from odoo import models, fields, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bcplanning_setting_client_id = fields.Char(
        string="Client Id",
        config_parameter='bcplanning.setting.client.id'
    )
    bcplanning_setting_client_secret = fields.Char(
        string="Client Secret",
        config_parameter='bcplanning.setting.client.secret'
    )
    bcplanning_setting_tenant_id = fields.Char(
        string="Tenant Id",
        config_parameter='bcplanning.setting.tenant.id'
    )



