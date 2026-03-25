import json
from urllib import response
import requests
from odoo import modules, models, api, models, _
import logging
import requests
from datetime import datetime
from odoo.exceptions import UserError
import jwt
import os

_logger = logging.getLogger(__name__)
class FCMService(models.AbstractModel):
    _name = 'fcm.service'
    _description = 'Service to send Firebase Cloud Messaging notifications'

    FCM_V1_URL = "https://fcm.googleapis.com/v1/projects/mavis-chat/messages:send"

    def _get_service_account_json(self):
        # récupère automatiquement le chemin du module
        module_path = modules.get_module_path("notification_FCM")
        
        # construit le chemin du JSON
        json_path = os.path.join(module_path, "data", "mavis-chat-firebase.json")
        
        # charge le fichier JSON
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
        
    @api.model
    def send_notification(self, token, title, body, data=None):
        """Envoi notification via FCM HTTP v1"""
        
        # Récupérer la configuration depuis les paramètres Odoo
        creds = self._get_service_account_json()
        
        client_email = creds["client_email"]
        private_key = creds["private_key"]
        project_id = creds["project_id"]
         
        if not all([project_id, private_key, client_email]):
            _logger.error("❌ Configuration FCM v1 incomplète")
            return {"success": False, "error": "Configuration FCM incomplète"}
        
        access_token = self._generate_access_token(
            private_key=private_key,
            client_email=client_email
        )
        
        if not access_token:
            return {"success": False, "error": "Échec génération token"}
        
        data_str = {str(k): str(v) for k, v in (data or {}).items()}
        
        # Préparer le payload
        message = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body
                },
                "data": data_str,
                "android": {
                    "priority": "HIGH"
                },
                "apns": {
                    "headers": {
                        "apns-priority": "10"
                    },
                    "payload": {
                        "aps": {
                            "sound": "default"
                        }
                    }
                }
            }
        }
        
        url = self.FCM_V1_URL
        _logger.info(f"FCM v1 URL: {url}")
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        _logger.info(f"FCM v1 Headers: {headers}")
        
        try:
            response = requests.post(url, json=message, headers=headers, timeout=10)
            _logger.info(f"OAuth response status: {response.status_code}")
            _logger.info(f"OAuth response body: {response.text}")

            if response.status_code != 200:
                _logger.error(f"FCM HTTP error {response.status_code}: {response.text}")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

            response.raise_for_status()        
            return response.json().get('access_token')
        except requests.exceptions.RequestException as e:
            _logger.error(f"❌ Erreur FCM v1: {e}")
            if e.response is not None:
                _logger.error(f"FCM Response: {e.response.text}")
            return {"success": False, "error": str(e)}
    
    def _generate_access_token(self, private_key, client_email):
        try:
            now = datetime.utcnow()

            payload = {
                'iss': client_email,
                'scope': 'https://www.googleapis.com/auth/firebase.messaging',
                'aud': 'https://oauth2.googleapis.com/token',
                'exp': int(now.timestamp()) + 3600,
                'iat': int(now.timestamp())
            }

            private_key = private_key.replace('\\n', '\n')
            signed_jwt = jwt.encode(payload, private_key, algorithm='RS256')

            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
                'assertion': signed_jwt
            }

            response = requests.post(token_url, data=token_data, timeout=10)

            _logger.error(f"OAuth status: {response.status_code}")
            _logger.error(f"OAuth body: {response.text}")

            if response.status_code != 200:
                _logger.error(" Échec obtention token OAuth")
                return {"success": False, "error": f"HTTP {response.status_code}: {response.text}"}

            return response.json().get('access_token')

        except Exception as e:
            _logger.error(f"OAuth exception: {str(e)}")
            return None

    @api.model
    def send_notification_to_users(self, user_ids, title, body, data=None):
        """ENVOYER DIRECTEMENT AUX USERS - Méthode principale"""
        _logger.info(f"----------------Envoi notification FCM aux utilisateurs: {user_ids}")
        _logger.info(f"Title: {title}")
        _logger.info(f"Body: {body}")
        _logger.info(f"Data: {data}")
        
        if not user_ids:
            return []
        
        results = []
        
        for user_id in user_ids:
            user = self.env['res.users'].browse(user_id)
            if not user.exists():
                continue
                
            # Chercher les devices MOBILE de cet utilisateur
            devices = self.env['mobile.device'].search([
                ('user_id', '=', user.id),
                ('logged_in', '=', True),
                ('fcm_token', '!=', False)
            ])
            _logger.info(f"User {user.login} has {len(devices)} registered devices for FCM.")
            
            for device in devices:
                _logger.info(f"Sending FCM to user {user.login}, device {device.device_name} with token {device.fcm_token[:30]}...")
                # Log détaillé du device
                _logger.info(f" ----- Device details for {user.login}:")
                _logger.info(f"   ID: {device.id}")
                _logger.info(f"   Name: {device.device_name}")
                _logger.info(f"   OS: {device.os}")
                _logger.info(f"   Device ID: {device.device_id}")
                _logger.info(f"   Token: {device.fcm_token}")
                _logger.info(f"   Logged in: {device.logged_in}")
                _logger.info(f"   Last seen: {device.last_seen}")
                
                result = self.send_notification(
                    token=device.fcm_token,
                    title=title,
                    body=body,
                    data=data
                )
                if result is None:
                    result = {"success": False, "error": "Unknown error"}   
                    
                _logger.info(f"FCM send result for user {user.login}, device {device.device_name}: {result}")
                results.append({
                    'user': user.name,
                    'device': device.device_name,
                    'success': result.get('success', False)
                })
        
        return results
    
    