from odoo import models, fields

class MailActivityType(models.Model):
    _inherit = 'mail.activity.type'

    fcm_color = fields.Char(
        string="Couleur (Mobile / FCM)"
    )

    fcm_display_name = fields.Char(
        string="Nom d'affichage (Mobile)",
        help="Nom affiché dans l'application mobile"
    )
