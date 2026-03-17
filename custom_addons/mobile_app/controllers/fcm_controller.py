from odoo import fields, http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class FCMController(http.Controller):
    @http.route('/fcm/register', type='json', auth='user', methods=['POST'])
    def register_device(self, **kwargs):
        user = request.env.user
        user_id = user.id
        _logger.warning('------------------ USER ID -- %s', user_id)
        device_id = kwargs.get('device_id')
        fcm_token = kwargs.get('fcm_token')
        device_name = kwargs.get('device_name')
        os = kwargs.get('os')

        if not device_id or not fcm_token:
            return {"status": "error", "message": "device_id and fcm_token are required"}

        MobileDevice = request.env['mobile.device'].sudo()

        # Récupérer le device déjà enregistré (s'il existe)
        existing_device = MobileDevice.search([('device_id', '=', device_id)], limit=1)

        # -----------------------------
        # CASE 1 ou 3 : NEW DEVICE
        # (aucun device avec ce device_id)
        # -----------------------------
        if not existing_device:
            MobileDevice.create({
                'user_id': user_id,
                'device_id': device_id,
                'fcm_token': fcm_token,
                'device_name': device_name,
                'os': os,
                'logged_in': True,
                'last_seen': fields.Datetime.now(),   # always here
            })
            return {"status": "ok", "message": "Device registered successfully"}

        # -----------------------------
        # CASE 4 : SAME USER + SAME DEVICE
        # Juste réactiver
        # -----------------------------
        if existing_device.user_id.id == user_id:
            existing_device.write({
                'logged_in': True,
                'fcm_token': fcm_token,
                'last_seen': fields.Datetime.now(),    # always here
            })
            return {"status": "ok", "message": "Device reactivated for this user"}

        # -----------------------------
        # CASE 2 : NEW USER + EXISTING DEVICE
        # Déconnecter ancien user + créer nouvelle ligne
        # -----------------------------
        existing_device.write({
            'logged_in': False,
            'last_seen': fields.Datetime.now(),        # update pour l'ancien device
        })

        MobileDevice.create({
            'user_id': user_id,
            'device_id': device_id,
            'fcm_token': fcm_token,
            'device_name': device_name,
            'os': os,
            'logged_in': True,
            'last_seen': fields.Datetime.now(),        # update pour le nouveau
        })

        return {"status": "ok", "message": "Device transferred to new user"}
    
    @http.route('/fcm/unregister', type='json', auth='user', methods=['POST'])
    def logout_device(self, **kwargs):
        device_id = kwargs.get('device_id')
        user = request.env.user

        if not device_id:
            return {"status": "error", "message": "device_id required"}

        MobileDevice = request.env['mobile.device'].sudo()
        device = MobileDevice.search([
            ('device_id', '=', device_id),
            ('user_id', '=', user.id)
        ], limit=1)

        if not device:
            return {"status": "error", "message": "Device not found for this user"}

        device.write({
            'logged_in': False,
            'last_seen': fields.Datetime.now(),
        })

        return {"status": "ok", "message": "Device logged out"}
    