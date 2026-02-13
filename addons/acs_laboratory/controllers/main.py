# -*- coding: utf-8 -*-

import json
from odoo import http, fields, _
from odoo.http import request
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import AccessError, MissingError
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager, get_records_pager
from odoo import fields as odoo_fields, http, tools, _, SUPERUSER_ID
import base64
import xmlrpc.client
import jwt
import base64
import logging
_logger = logging.getLogger(__name__)

SECRET_KEY = 'rnd24*'

class ACSHms(http.Controller):
    
    @http.route(['/validate/patientlaboratorytest/<labresult_unique_code>'], type='http', auth="public", website=True)
    def labresult_details(self, labresult_unique_code, **post):
        if labresult_unique_code:
            labresult = request.env['patient.laboratory.test'].sudo().search([('unique_code','=',labresult_unique_code)], limit=1)
            if labresult:
                return request.render("acs_laboratory.acs_labresult_details", {'labresult': labresult})
        return request.render("acs_hms.acs_no_details")
    
    @http.route('/custom_login', type='http', auth='none')
    def custom_login(self, token=None, redirect_url='/laboratory_sample_test', **kwargs):
        #Default to localhost if request.httprequest.host_url is not set
        url = request.httprequest.host_url.rstrip('/') if request.httprequest.host_url else 'http://localhost:8069'
 
        database = 'sandbox'
        print('Token:', token)
        try:
            if not token:
                return "Token is missing"

            # Decode the token (base64 decode first)
            decoded_token = base64.urlsafe_b64decode(token.encode()).decode()
            token_data = jwt.decode(decoded_token, SECRET_KEY, algorithms=['HS256'])

            # Extract login and password from token
            login = token_data.get('login')
            password = token_data.get('password')
            print("Login:", login, "Password:", password)
            if not login or not password:
                return "Invalid token data"

            # Authenticate using XML-RPC
            common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
            uid = common.authenticate(database, login, password, {})
            
            if uid:
                # Authenticate session
                request.session.authenticate(database, login, password)
                # Redirect to the specified URL
                # return http.redirect_with_hash(redirect_url)
                return {'success': True}
            else:
                # return f"Invalid login: {login} or password: {password}"
                return {'success': False, 'message': 'Login ou mot de passe invalide'}

        except jwt.ExpiredSignatureError:
            # return "Token has expired"
            return {'success': False, 'message': 'Token expiré'}
        except jwt.InvalidTokenError:
            # return "Invalid token"
            return {'success': False, 'message': 'Token invalide'}
        except Exception as e:
            # return f"An unexpected error occurred: {str(e)}"
            return {'success': False, 'message': str(e)}

    @http.route(['/laboratory_sample_test'], type='http' , auth='public' , website=True)
    def laboratory_sample(self):
        _logger.info("---* Entering /lab route")
        if not request.session.sid:
            _logger.info("---* No existing session. Creating new session.")
            request.session.touch()

        user = request.env.user
        user_company = request.env.user.company_id.id
        is_logged = not user._is_public()
        user_info = False

        if is_logged:
            image_url = f"/web/image/res.users/{user.id}/image_128"
            user_info = {
                'name': user.name,
                'email': user.email,
                'id': user.id,
                'image_url': image_url,
                'user_company': user_company,
                # 'image_url': user.image_128.decode('utf-8') if user.image_128 else None
            }

        # Récupérer tous les départements
        departments = request.env['hr.department'].sudo().search([])
        departments_data = [(dept.id, dept.name) for dept in departments]
        
        _logger.info(f"---* is_logged: {is_logged}, user_info: {user_info}, departments found: {len(departments_data)}")
        return request.render(
        'acs_laboratory.laboratory_screen_sample',
        {
            'is_logged_json': json.dumps(is_logged),
            'departments_json': json.dumps(departments_data),
            'user_info_json': json.dumps(user_info or {}),
            'csrf_token': request.csrf_token(),   
        })

    @http.route('/laboratory/collect_sample', type='json', auth='user', methods=['POST'])
    def collect_sample(self):
        request_lab_data = request.jsonrequest.get('lab_request_ref')
        user_company = request.env.user.company_id.id
        _logger.info(f"---* Received collect_sample request with lab_request_ref: {request_lab_data} for company_id: {user_company}")
        
        # On laisse Odoo gérer le filtre multi-company automatiquement
        lab_request = request.env['acs.laboratory.request'].search([
            ('name', '=', request_lab_data),
            ('company_id', '=', user_company)
        ], limit=1)

        laboratory_requests = request.env['acs.patient.laboratory.sample'].search([
            ('request_id', '=', lab_request.id), 
            ('state', '=', 'draft'),
            ('company_id', '=', user_company)
        ])
        
        _logger.info(f"---* Collecting sample for request: {request_lab_data}, found {len(laboratory_requests)} samples")
        results = []
        for sample in laboratory_requests:
            sample_data = sample.read(['id', 'name', 'patient_id', 'request_id', 'sample_type_id'])[0]  
            patient_data = {} 
            if sample_data['patient_id']:
                patient = request.env['hms.patient'].sudo().browse(sample_data['patient_id'][0])
                patient_data = patient.read(['name', 'code', 'gender', 'street' , 'birthday']) 
            formatted_consumables = []
            if sample_data['sample_type_id']:
                sample_type = request.env['acs.laboratory.sample.type'].sudo().browse(sample_data['sample_type_id'][0])
                
                for product in sample_type.product_ids:
                    formatted_consumables.append({
                        'product_id': product.id,
                        'product_name': product.name,
                        'qty': 1,  # valeur par défaut
                    })
                
            else:
                formatted_type_consumables = []  

            formatted_sample = {
                'id' : sample_data['id'],
                'name': sample_data['name'],
                'patient': patient_data[0] if patient_data else {'name': 'N/A', 'dob': 'N/A', 'gender': 'N/A', 'address': 'N/A'},
                'request_id': sample_data['request_id'][1] if sample_data['request_id'] else 'N/A',
                'sample_type_id': sample_data['sample_type_id'][1] if sample_data['sample_type_id'] else 'N/A',
                'consumable_lines': formatted_consumables 
            }
            print(formatted_sample)
            results.append(formatted_sample)

        return {'status': 'success', 'data': results}

    @http.route('/laboratory/update_consumables', type='json', auth='public', methods=['POST'])
    def update_consumables(self):
        sample_id = request.jsonrequest.get('sample_id')
        consumables = request.jsonrequest.get('consumables')
        ex_collect_checkbox = request.jsonrequest.get('ex_collect_checkbox')

        department_id = request.jsonrequest.get('department_id')
        if not sample_id or not consumables:
            return {'status': 'error', 'message': 'Invalid request data'}

        sample = request.env['acs.patient.laboratory.sample'].sudo().browse(sample_id)
        company = sample.company_id.id
        if not sample.exists():
            return {'status': 'error', 'message': 'Sample not found'}
        
        if department_id:
            _logger.info(f"--*Department ID: {department_id}")
            department = request.env['hr.department'].sudo().browse(department_id)
            _logger.info(f"--*Department Exists: {department.exists()}")
            if department.exists():
                sample.sudo().write({'department_id': department_id})
            else:
                return {'status': 'error', 'message': 'Department not found'}
            
        updated_consumables = []
        for consumable in consumables:
            product_id = consumable.get('product_id')
            main_qty = consumable.get('main_qty', 0)
            qty = main_qty if main_qty else consumable.get('qty', 0)
            lots = consumable.get('lots', [])

            if not lots:
                consumable_line = sample.consumable_line_ids.filtered(lambda line: line.product_id.id == product_id and not line.lot_id)
                if consumable_line:
                    updated_line_data = {
                        'qty': qty,
                    }
                    updated_consumables.append((1, consumable_line.id, updated_line_data))
                else:
                    new_line_data = {
                        'product_id': product_id,
                        'qty': qty,
                        'lot_id': '', 
                        'lab_sample_id': sample_id
                    }
                    updated_consumables.append((0, 0, new_line_data))
            else:
                for lot in lots:
                    lot_value = lot.get('lot')
                    new_qty = lot.get('qty')
                    #modification du lot
                    lot_record = request.env['stock.production.lot'].sudo().search([('name', '=', lot_value),('company_id','=', company)]).id
                    consumable_line = sample.consumable_line_ids.filtered(lambda line: line.product_id.id == product_id and line.lot_id.name == lot_value)
                    #id_lot = self.env['stock.production.lot'].search([('name','=','lot_value'),('product_id','=', product_id)]).id

                    new_line_data = {
                            'product_id': product_id,
                            'qty': new_qty,
                            'lot_id': lot_record,
                            'lab_sample_id': sample_id 
                        }
                    updated_consumables.append((0, 0, new_line_data))
                    
        sample.sudo().write({'consumable_line_ids': updated_consumables,'external_collect' : ex_collect_checkbox})
        sample.sudo().action_collect()
        return {'status': 'success', 'message': 'Consumables mis à jour avec succes'}

    @http.route(['/logout'], type='http', auth='public', website=True)
    def logout(self, **kw):
        next_url = kw.get('next', '/laboratory_sample_test')
        request.session.logout(keep_db=False)
        _logger.info("---* User logged out successfully.")
        return request.redirect(next_url)

class HMSPortal(CustomerPortal):
    def _prepare_portal_layout_values(self):
        values = super(HMSPortal, self)._prepare_portal_layout_values()
        lab_result_count = 0
        if request.env['patient.laboratory.test'].check_access_rights('read', raise_exception=False):
            lab_result_count = request.env['patient.laboratory.test'].search_count([])

        lab_request_count = 0
        if request.env['acs.laboratory.request'].check_access_rights('read', raise_exception=False):
            lab_request_count = request.env['acs.laboratory.request'].search_count([])
        values.update({
            'lab_result_count': lab_result_count,
            'lab_request_count': lab_request_count,
        })
        return values

    #Lab Result
    @http.route(['/my/lab_results', '/my/lab_results/page/<int:page>'], type='http', auth="user", website=True)
    def my_lab_results(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        user = request.env.user
        if not sortby:
            sortby = 'date'

        sortings = {
            'date': {'label': _('Newest'), 'order': 'date_analysis desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }

        order = sortings.get(sortby, sortings['date'])['order']
 
        pager = portal_pager(
            url="/my/lab_results",
            url_args={},
            total=values['lab_result_count'],
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected

        lab_results = request.env['patient.laboratory.test'].search([],
            order=order, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'sortings': sortings,
            'sortby': sortby,
            'lab_results': lab_results,
            'page_name': 'lab_result',
            'default_url': '/my/lab_results',
            'searchbar_sortings': sortings,
            'pager': pager
        })
        return request.render("acs_laboratory.lab_results", values)

    @http.route(['/my/lab_results/<int:result_id>'], type='http', auth="user", website=True)
    def my_lab_test_result(self, result_id=None, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('patient.laboratory.test', result_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        return request.render("acs_laboratory.my_lab_test_result", {'lab_result': order_sudo})

    #Lab Request
    @http.route(['/my/lab_requests', '/my/lab_requests/page/<int:page>'], type='http', auth="user", website=True)
    def my_lab_requests(self, page=1, sortby=None, **kw):
        values = self._prepare_portal_layout_values()
        user = request.env.user
        if not sortby:
            sortby = 'date'

        sortings = {
            'date': {'label': _('Newest'), 'order': 'date desc'},
            'name': {'label': _('Name'), 'order': 'name'},
        }

        order = sortings.get(sortby, sortings['date'])['order']
 
        pager = portal_pager(
            url="/my/lab_requests",
            url_args={},
            total=values['lab_request_count'],
            page=page,
            step=self._items_per_page
        )
        # content according to pager and archive selected
        lab_requests = request.env['acs.laboratory.request'].search([],
            order=order, limit=self._items_per_page, offset=pager['offset'])

        values.update({
            'sortings': sortings,
            'sortby': sortby,
            'lab_requests': lab_requests,
            'page_name': 'lab_request',
            'default_url': '/my/lab_requests',
            'searchbar_sortings': sortings,
            'pager': pager
        })
        return request.render("acs_laboratory.lab_requests", values)

    @http.route(['/my/lab_requests/<int:request_id>'], type='http', auth="user", website=True)
    def my_lab_test_request(self, request_id=None, access_token=None, **kw):
        try:
            order_sudo = self._document_check_access('acs.laboratory.request', request_id, access_token=access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')

        return request.render("acs_laboratory.my_lab_test_request", {'lab_request': order_sudo})

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: