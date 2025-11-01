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
    bcplanning_setting_env_name = fields.Char(
        string="BC Environment Name",
        config_parameter='bcplanning.setting.env.name'
    )
    bcplanning_setting_company_id = fields.Char(
        string="Company Id",
        config_parameter='bcplanning.setting.company.id'
    )
    bcplanning_base_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning Base Group',
        config_parameter='bcplanning.setting.base_group_id',
        help="Select the group used for Planning base"
    )
    bcplanning_project_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning Project Group',
        config_parameter='bcplanning.setting.project_group_id',
        help="Select the group used for Project menu"
    )
    bcplanning_team_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning Team Group',
        config_parameter='bcplanning.setting.team_group_id',
        help="Select the group used for team menu"
    )
    bcplanning_planning_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning Task Vendor Group',
        config_parameter='bcplanning.setting.planning_group_id',
        help="Select the group used for task of vendor menu"
    )
    bcplanning_bor_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning BOR Group',
        config_parameter='bcplanning.setting.bor_group_id',
        help="Select the group used for BOR menu"
    )
    bcplanning_taskresource_group_id = fields.Many2one(
        'res.groups',
        string='BC Planning Task Resource Group',
        config_parameter='bcplanning.setting.taskresource_group_id',
        help="Select the group used for task of resource menu"
    )