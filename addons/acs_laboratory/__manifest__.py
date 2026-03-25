# -*- coding: utf-8 -*-
#╔══════════════════════════════════════════════════════════════════════╗
#║                                                                      ║
#║                  ╔═══╦╗       ╔╗  ╔╗     ╔═══╦═══╗                   ║
#║                  ║╔═╗║║       ║║ ╔╝╚╗    ║╔═╗║╔═╗║                   ║
#║                  ║║ ║║║╔╗╔╦╦══╣╚═╬╗╔╬╗ ╔╗║║ ╚╣╚══╗                   ║
#║                  ║╚═╝║║║╚╝╠╣╔╗║╔╗║║║║║ ║║║║ ╔╬══╗║                   ║
#║                  ║╔═╗║╚╣║║║║╚╝║║║║║╚╣╚═╝║║╚═╝║╚═╝║                   ║
#║                  ╚╝ ╚╩═╩╩╩╩╩═╗╠╝╚╝╚═╩═╗╔╝╚═══╩═══╝                   ║
#║                            ╔═╝║     ╔═╝║                             ║
#║                            ╚══╝     ╚══╝                             ║
#║                  SOFTWARE DEVELOPED AND SUPPORTED BY                 ║
#║                ALMIGHTY CONSULTING SOLUTIONS PVT. LTD.               ║
#║                      COPYRIGHT (C) 2016 - TODAY                      ║
#║                      https://www.almightycs.com                      ║
#║                                                                      ║
#╚══════════════════════════════════════════════════════════════════════╝
{ 
    'name': 'Laboratory Management',
    'summary': 'Manage Lab requests, Lab tests, Invoicing and related history for hospital.',
    'description': """
        This module add functionality to manage Laboratory flow. laboratory management system
        Hospital Management lab tests laboratory invoices laboratory test results ACS HMS
    """,
    'version': '1.2.17',
    'category': 'Medical',
    'author': 'Almighty Consulting Solutions Pvt. Ltd.',
    'support': 'info@almightycs.com',
    'website': 'https://www.almightycs.com',
    'license': 'OPL-1',
    'depends': ['acs_hms_base', 'acs_hms_document_preview', 'sms','health_service', 'odx_m2m_attachment_preview', 'website'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',

        'report/report_acs_lab_prescription.xml',
        'report/lab_report.xml',
        'report/lab_report_ctb.xml',
        # 'report/lab_report_imm.xml',
        'report/lab_samples_report.xml',
        'report/lab_samples_report_codebarre.xml',
        'report/paper_format.xml',
        'report/lab_result_worklist.xml',
        'report/sample_in_request.xml',
        'report/list_barcode_request.xml',
        'report/report_lab_combine.xml',
        'report/lab_report_imm_basic.xml',
        'report/lab_report_imm_combine_basic.xml',

        'data/mail_template.xml',
        'data/laboratory_data.xml',
        'data/lab_uom_data.xml',
        'data/lab_sample_type_data.xml',
        'views/lab_uom_view.xml',
        'views/laboratory_request_view.xml',
        'views/laboratory_view.xml',
        'views/laboratory_test_view.xml',
        'views/laboratory_sample_view.xml',
        'views/hr_department_views.xml',
        'views/stock_picking_views.xml',
        'views/hms_base_view.xml',
        'views/res_config.xml',
        # 'views/res_users_view.xml',
        'views/user_barcode_token_view.xml',
        'views/portal_template.xml',
        'views/templates_view.xml',
        'wizard/resultat_anterieur_wizard_views.xml',
        'wizard/reverification_wizard_view.xml',
        'views/website_lab_sample.xml',
        'views/menu_item.xml',
    ],
    'demo': [
        'data/laboratory_demo.xml',
    ],
    'images': [
        'static/description/hms_laboratory_almightycs_cover.jpg',
    ],
    'installable': True,
    'application': True,
    'sequence': 1,
    'price': 61,
    'currency': 'EUR',
}
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
