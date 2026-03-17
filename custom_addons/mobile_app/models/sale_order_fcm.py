from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class SaleOrderFCM(models.Model):
    _inherit = 'sale.order'

    @api.model
    def create(self, vals):
        order = super().create(vals)
        order._notify_sale_creation()
        return order

    def _notify_sale_creation(self):
        for record in self:
            # Récupérer le groupe Sales / Administrator
            group = self.env.ref('sales_team.group_sale_manager')
            users = group.users
            partner_ids = [user.partner_id.id for user in users if user.partner_id]

            # Générer l'URL
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            menu_id = self.env.ref('sale.menu_sale_order').id
            company_id = record.company_id.id if record.company_id else self.env.company.id

            record_url = f"{base_url}/web#cids={company_id}&id={record.id}&menu_id={menu_id}&model=sale.order&view_type=form"

            # Envoyer la notification
            if partner_ids:
                body_html = (
                    f"Nouvelle commande de vente <b>{record.name}</b> créée et en attente de validation. "
                    f"Accédez à la commande ici : <a href='{record_url}' target='_blank'>Voir la commande</a>"
                )

                record.message_post(
                    body=body_html,
                    partner_ids=partner_ids,
                    subtype_id=self.env.ref('mail.mt_note').id,
                    subject=f"Nouvelle commande en attente de validation: {record.name}",
                    author_id=self.env.ref('base.user_root').id,
                )
            
            # 4. NOTIFICATION FCM (NOUVEAU - juste ces 8 lignes)
            if partner_ids:
                _logger.info(f"Envoi notification FCM pour la commande {record.name}")
                try:
                    notification_data = {
                        'type': 'sale_order_created',
                        'model': 'sale.order',
                        'res_id': record.id,
                        'res_name': record.name
                    }
                    
                    _logger.info(f"FCM Data: {notification_data}")
                    fcm_service = self.env['fcm.service']
                    _logger.info(f"FCM Service: {fcm_service}")
                    results = fcm_service.send_notification_to_users(
                        user_ids=users.ids,
                        title="Nouvelle commande",
                        body=f"Commande {record.name} créée",
                        data=notification_data
                    )
                    _logger.info(f"FCM Results: {results}")
                    
                    if results:
                        _logger.info(f"FCM envoyé à {len(results)} device(s)")
                    
                except Exception as e:
                    _logger.warning(f"FCM échoué: {str(e)}")
    
