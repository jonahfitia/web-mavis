from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class MailActivityFCM(models.Model):
    _inherit = 'mail.activity'

    @api.model
    def create(self, vals):
        activity = super(MailActivityFCM, self).create(vals)
        activity._notify_activity_creation()
        return activity

    def _notify_activity_creation(self):
        _logger.info(f"----///----- NOTIFY ACTIVITY CREATION | id={self.id} | model={self.res_model} | res_id={self.res_id} | user={self.user_id.name}")
        
        for activity in self:
            _logger.info(f"----///----- Processing activity ID 1 ={activity.id}")

            # Envoi de la notification FCM
            if activity.user_id:
                _logger.info(f"----///----- Processing activity ID 2 ={activity.id}")
                _logger.info(f"----///----- Sending FCM notification to user {activity.user_id.name} (ID {activity.user_id.id}) for activity ID {activity.id}")
                fcm_service = self.env['fcm.service']  # adapter selon ton module FCM
                notification_data = {
                    "activity_id": activity.id,
                    "res_model": activity.res_model,
                    "res_id": activity.res_id,
                }
                fcm_service.send_notification_to_users(
                    user_ids=[activity.user_id.id],
                    title="Nouvelle activité",
                    body=f"Vous avez une nouvelle activité : {activity.activity_type_id.name}",
                    data=notification_data
                )