import json
from odoo.http import request, Response
from odoo import http, fields, _
from odoo.http import request
from odoo import http, _
import base64
from odoo.service import security
import logging
_logger = logging.getLogger(__name__)

class BarcodeAuthController(http.Controller):

    @http.route('/barcode/login', type='http', auth='none', csrf=False, methods=['POST'])
    def barcode_login(self, token=None, redirect_url='/', **kwargs):
        _logger.info("Barcode login called")
        if not token:
            return Response(
                json.dumps({
                    'success': False,
                    'message': 'Token manquant'
                }),
                content_type='application/json',
                status=400
            )

        card = request.env['user.barcode.token'].sudo().search([
            ('token', '=', token),
            ('active', '=', True)
        ], limit=1)

        if not card:
            return request.make_json_response({
                'success': False,
                'message': 'Carte invalide ou désactivée'
            })

        user = card.user_id

        # 🔥 Ici on récupère les départements de la société de l'utilisateur
        
        departments = user.department_ids.filtered(
                lambda d: d.company_id == user.company_id
            )
        
        request.session.uid = user.id
        request.session.login = user.login
        request.session.session_token = security.compute_session_token(
            request.session,
            request.env
        )

        card.sudo().write({
            'last_used': fields.Datetime.now()
        })

        _logger.info("✅ User %s logged in via barcode", user.login)

        return Response(
            json.dumps({
                'success': True,
                'uid': user.id,
                'name': user.name,
                'departments': [
                    {'id': d.id, 'name': d.name}
                    for d in departments
                ]
            }),
            content_type='application/json',
            status=200
        )
    
    @http.route('/whoamilabo', type='http', auth='user', csrf=False)
    def whoami(self):
        user = request.env.user
        return http.Response(
            json.dumps({
                'uid': user.id,
                'name': user.name,
                'login': user.login,
            }),
            content_type='application/json'
        )

    @http.route('/barcode/user_info', type='http', auth='user', csrf=True, methods=['POST'])
    def barcode_user_info(self, **kwargs):
        try:
            # Vérifier si l'utilisateur est authentifié
            user = http.request.env.user
            if user.id == http.request.env.ref('base.public_user').id:
                return http.Response(
                    json.dumps({'error': 'Not authenticated', 'is_logged': False}),
                    content_type='application/json',
                    status=401
                )
            
            # Récupérer les infos utilisateur
            response_data = {
                'success': True,
                'is_logged': True,
                'user_id': user.id,
                'name': user.name,
                'login': user.login,
            }
            
            return http.Response(
                json.dumps(response_data),
                content_type='application/json'
            )
            
        except Exception as e:
            return http.Response(
                json.dumps({'error': str(e), 'is_logged': False}),
                content_type='application/json',
                status=500
            )

    @http.route('/barcode/departements', type='json', auth='user')
    def get_departments(self):

        user = request.env.user

        departments = request.env['hr.department'].sudo().search([
            ('company_id', '=', user.company_id.id)
        ])

        return {
            "success": True,
            "departments": [
                {
                    "id": dept.id,
                    "name": dept.name
                }
                for dept in departments
            ]
        }