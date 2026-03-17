{
    'name': 'Feat for Mobile App - Mavis',
    'version': '1.0',
    'summary': 'Feat for Mobile App - Mavis (FCM, API, etc.)',
    'author': 'RND',
    'depends': ['base', 'mail', 'sale', 'stock', 'website_helpdesk_support_ticket'],
    'description': '''
        Module combiné gérant :
        1. Notifications FCM pour mobile
        2. Automatisation des notifications métier comme apres confirmation d'une commande ou création d'un ticket helpdesk
    ''',
    'external_dependencies': {
        'python': ['pyjwt', 'requests']
    },
    'data': [
        'data/mail_activity_type_fcm.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
