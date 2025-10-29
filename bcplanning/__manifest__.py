{
    'name': "bcplanning",

    'summary': "Odoo integration with Business Central for BC Vendor portal",

    'description': """
        Odoo integration with Business Central for BC Vendor portal
    """,

    'author': "Ahmad Heriyanto",
    'website': "https://bc365optimizers.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Integration',
    'version': '0.1',
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': [
        'base',
        'web',
        'website',
    ],
    # always loaded
    'data': [
        'security/ir.model.access.csv',
        'views/bc_planning_views.xml',
        'views/remove_website_odoo_logo.xml',
        'views/website_menu.xml',
        'views/partner_projects.xml',
        'views/partner_tasks.xml',
        'views/res_config_settings_views.xml',
        'views/partner_resource.xml',
        'views/web_partner_no_records_template.xml',
        'views/web_task_template_overlay.xml',
        'views/partner_bor.xml',
    ],
    'assets': {
        'web.assets_frontend': [            
            '/bcplanning/static/src/scss/partner_task.scss',
            '/bcplanning/static/src/scss/partner_project.scss',
            '/bcplanning/static/src/js/partner_project.js',
            '/bcplanning/static/src/js/partner_task.js',
            '/bcplanning/static/src/js/partner_bor.js',
            '/bcplanning/static/src/js/resources.js',            
        ],
    },
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
    "application": True,
    "installable": True,
}