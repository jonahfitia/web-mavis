# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import logging
import psycopg2
import werkzeug.utils
import werkzeug.wrappers

from werkzeug.urls import url_encode

from odoo import api, http, registry, SUPERUSER_ID, _
from odoo.addons.mail.controllers.mail_activity_helper import MailActivityHelper
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.tools import consteq
from datetime import datetime

_logger = logging.getLogger(__name__)
class MailController(http.Controller):
    _cp_path = '/mail'

    @classmethod
    def _redirect_to_messaging(cls):
        url = '/web#%s' % url_encode({'action': 'mail.action_discuss'})
        return werkzeug.utils.redirect(url)

    @classmethod
    def _check_token(cls, token):
        base_link = request.httprequest.path
        params = dict(request.params)
        params.pop('token', '')
        valid_token = request.env['mail.thread']._notify_encode_link(base_link, params)
        return consteq(valid_token, str(token))

    @classmethod
    def _check_token_and_record_or_redirect(cls, model, res_id, token):
        comparison = cls._check_token(token)
        if not comparison:
            _logger.warning('Invalid token in route %s', request.httprequest.url)
            return comparison, None, cls._redirect_to_messaging()
        try:
            record = request.env[model].browse(res_id).exists()
        except Exception:
            record = None
            redirect = cls._redirect_to_messaging()
        else:
            redirect = cls._redirect_to_record(model, res_id)
        return comparison, record, redirect

    @classmethod
    def _redirect_to_record(cls, model, res_id, access_token=None, **kwargs):
        # access_token and kwargs are used in the portal controller override for the Send by email or Share Link
        # to give access to the record to a recipient that has normally no access.
        uid = request.session.uid
        user = request.env['res.users'].sudo().browse(uid)
        cids = False

        # no model / res_id, meaning no possible record -> redirect to login
        if not model or not res_id or model not in request.env:
            return cls._redirect_to_messaging()

        # find the access action using sudo to have the details about the access link
        RecordModel = request.env[model]
        record_sudo = RecordModel.sudo().browse(res_id).exists()
        if not record_sudo:
            # record does not seem to exist -> redirect to login
            return cls._redirect_to_messaging()

        # the record has a window redirection: check access rights
        if uid is not None:
            if not RecordModel.with_user(uid).check_access_rights('read', raise_exception=False):
                return cls._redirect_to_messaging()
            try:
                # We need here to extend the "allowed_company_ids" to allow a redirection
                # to any record that the user can access, regardless of currently visible
                # records based on the "currently allowed companies".
                cids = request.httprequest.cookies.get('cids', str(user.company_id.id))
                cids = [int(cid) for cid in cids.split(',')]
                try:
                    record_sudo.with_user(uid).with_context(allowed_company_ids=cids).check_access_rule('read')
                except AccessError:
                    # In case the allowed_company_ids from the cookies (i.e. the last user configuration
                    # on his browser) is not sufficient to avoid an ir.rule access error, try to following
                    # heuristic:
                    # - Guess the supposed necessary company to access the record via the method
                    #   _get_mail_redirect_suggested_company
                    #   - If no company, then redirect to the messaging
                    #   - Merge the suggested company with the companies on the cookie
                    # - Make a new access test if it succeeds, redirect to the record. Otherwise, 
                    #   redirect to the messaging.
                    suggested_company = record_sudo._get_mail_redirect_suggested_company()
                    if not suggested_company:
                        raise AccessError('')
                    cids = cids + [suggested_company.id]
                    record_sudo.with_user(uid).with_context(allowed_company_ids=cids).check_access_rule('read')
            except AccessError:
                return cls._redirect_to_messaging()
            else:
                record_action = record_sudo.get_access_action(access_uid=uid)
        else:
            record_action = record_sudo.get_access_action()
            if record_action['type'] == 'ir.actions.act_url' and record_action.get('target_type') != 'public':
                url_params = {
                    'model': model,
                    'id': res_id,
                    'active_id': res_id,
                    'action': record_action.get('id'),
                }
                view_id = record_sudo.get_formview_id()
                if view_id:
                    url_params['view_id'] = view_id
                url = '/web/login?redirect=#%s' % url_encode(url_params)
                return werkzeug.utils.redirect(url)

        record_action.pop('target_type', None)
        # the record has an URL redirection: use it directly
        if record_action['type'] == 'ir.actions.act_url':
            return werkzeug.utils.redirect(record_action['url'])
        # other choice: act_window (no support of anything else currently)
        elif not record_action['type'] == 'ir.actions.act_window':
            return cls._redirect_to_messaging()

        url_params = {
            'model': model,
            'id': res_id,
            'active_id': res_id,
            'action': record_action.get('id'),
        }
        view_id = record_sudo.get_formview_id()
        if view_id:
            url_params['view_id'] = view_id

        if cids:
            url_params['cids'] = ','.join([str(cid) for cid in cids])
        url = '/web?#%s' % url_encode(url_params)
        return werkzeug.utils.redirect(url)

    @http.route('/mail/thread/data', methods=['POST'], type='json', auth='user')
    def mail_thread_data(self, thread_model, thread_id, request_list, **kwargs):
        res = {}
        thread = request.env[thread_model].with_context(active_test=False).search([('id', '=', thread_id)])
        if 'attachments' in request_list:
            res['attachments'] = thread.env['ir.attachment'].search([('res_id', '=', thread.id), ('res_model', '=', thread._name)], order='id desc')._attachment_format(commands=True)
        return res

    @http.route('/mail/read_followers', type='json', auth='user')
    def read_followers(self, res_model, res_id):
        request.env['mail.followers'].check_access_rights("read")
        request.env[res_model].check_access_rights("read")
        request.env[res_model].browse(res_id).check_access_rule("read")
        follower_recs = request.env['mail.followers'].search([('res_model', '=', res_model), ('res_id', '=', res_id)])

        followers = []
        follower_id = None
        for follower in follower_recs:
            if follower.partner_id == request.env.user.partner_id:
                follower_id = follower.id
            followers.append({
                'id': follower.id,
                'partner_id': follower.partner_id.id,
                'channel_id': follower.channel_id.id,
                'name': follower.name,
                'display_name': follower.display_name,
                'email': follower.email,
                'is_active': follower.is_active,
                # When editing the followers, the "pencil" icon that leads to the edition of subtypes
                # should be always be displayed and not only when "debug" mode is activated.
                'is_editable': True
            })
        return {
            'followers': followers,
            'subtypes': self.read_subscription_data(follower_id) if follower_id else None
        }

    @http.route('/mail/read_subscription_data', type='json', auth='user')
    def read_subscription_data(self, follower_id):
        """ Computes:
            - message_subtype_data: data about document subtypes: which are
                available, which are followed if any """
        request.env['mail.followers'].check_access_rights("read")
        follower = request.env['mail.followers'].sudo().browse(follower_id)
        follower.ensure_one()
        request.env[follower.res_model].check_access_rights("read")
        request.env[follower.res_model].browse(follower.res_id).check_access_rule("read")

        # find current model subtypes, add them to a dictionary
        subtypes = request.env['mail.message.subtype'].search([
            '&', ('hidden', '=', False),
            '|', ('res_model', '=', follower.res_model), ('res_model', '=', False)])
        followed_subtypes_ids = set(follower.subtype_ids.ids)
        subtypes_list = [{
            'name': subtype.name,
            'res_model': subtype.res_model,
            'sequence': subtype.sequence,
            'default': subtype.default,
            'internal': subtype.internal,
            'followed': subtype.id in followed_subtypes_ids,
            'parent_model': subtype.parent_id.res_model,
            'id': subtype.id
        } for subtype in subtypes]
        return sorted(subtypes_list,
                      key=lambda it: (it['parent_model'] or '', it['res_model'] or '', it['internal'], it['sequence']))

    @http.route('/mail/view', type='http', auth='public')
    def mail_action_view(self, model=None, res_id=None, access_token=None, **kwargs):
        """ Generic access point from notification emails. The heuristic to
            choose where to redirect the user is the following :

         - find a public URL
         - if none found
          - users with a read access are redirected to the document
          - users without read access are redirected to the Messaging
          - not logged users are redirected to the login page

            models that have an access_token may apply variations on this.
        """
        # ==============================================================================================
        # This block of code disappeared on saas-11.3 to be reintroduced by TBE.
        # This is needed because after a migration from an older version to saas-11.3, the link
        # received by mail with a message_id no longer work.
        # So this block of code is needed to guarantee the backward compatibility of those links.
        if kwargs.get('message_id'):
            try:
                message = request.env['mail.message'].sudo().browse(int(kwargs['message_id'])).exists()
            except:
                message = request.env['mail.message']
            if message:
                model, res_id = message.model, message.res_id
        # ==============================================================================================

        if res_id and isinstance(res_id, str):
            try:
                res_id = int(res_id)
            except ValueError:
                res_id = False
        return self._redirect_to_record(model, res_id, access_token, **kwargs)

    @http.route('/mail/assign', type='http', auth='user', methods=['GET'])
    def mail_action_assign(self, model, res_id, token=None):
        comparison, record, redirect = self._check_token_and_record_or_redirect(model, int(res_id), token)
        if comparison and record:
            try:
                record.write({'user_id': request.uid})
            except Exception:
                return self._redirect_to_messaging()
        return redirect

    @http.route('/mail/<string:res_model>/<int:res_id>/avatar/<int:partner_id>', type='http', auth='public')
    def avatar(self, res_model, res_id, partner_id):
        headers = [('Content-Type', 'image/png')]
        status = 200
        content = 'R0lGODlhAQABAIABAP///wAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw=='  # default image is one white pixel
        if res_model in request.env:
            try:
                # if the current user has access to the document, get the partner avatar as sudo()
                request.env[res_model].browse(res_id).check_access_rule('read')
                if partner_id in request.env[res_model].browse(res_id).sudo().exists().message_ids.mapped('author_id').ids:
                    status, headers, _content = request.env['ir.http'].sudo().binary_content(
                        model='res.partner', id=partner_id, field='image_128', default_mimetype='image/png')
                    # binary content return an empty string and not a placeholder if obj[field] is False
                    if _content != '':
                        content = _content
                    if status == 304:
                        return werkzeug.wrappers.Response(status=304)
            except AccessError:
                pass
        image_base64 = base64.b64decode(content)
        headers.append(('Content-Length', len(image_base64)))
        response = request.make_response(image_base64, headers)
        response.status = str(status)
        return response

    @http.route('/mail/needaction', type='json', auth='user')
    def needaction(self):
        return request.env['res.partner'].get_needaction_count()

    @http.route('/mail/init_messaging', type='json', auth='user')
    def mail_init_messaging(self):
        values = {
            'needaction_inbox_counter': request.env['res.partner'].get_needaction_count(),
            'starred_counter': request.env['res.partner'].get_starred_count(),
            'channel_slots': request.env['mail.channel'].channel_fetch_slot(),
            'mail_failures': request.env['mail.message'].message_fetch_failed(),
            'commands': request.env['mail.channel'].get_mention_commands(),
            'mention_partner_suggestions': request.env['res.partner'].get_static_mention_suggestions(),
            'shortcodes': request.env['mail.shortcode'].sudo().search_read([], ['source', 'substitution', 'description']),
            'menu_id': request.env['ir.model.data'].xmlid_to_res_id('mail.menu_root_discuss'),
            'moderation_counter': request.env.user.moderation_counter,
            'moderation_channel_ids': request.env.user.moderation_channel_ids.ids,
            'partner_root': request.env.ref('base.partner_root').sudo().mail_partner_format(),
            'public_partner': request.env.ref('base.public_partner').sudo().mail_partner_format(),
            'public_partners': [partner.mail_partner_format() for partner in request.env.ref('base.group_public').sudo().with_context(active_test=False).users.partner_id],
            'current_partner': request.env.user.partner_id.mail_partner_format(),
            'current_user_id': request.env.user.id,
        }
        return values

    @http.route('/mail/count_messaging_unread', type='json', auth='user')
    def mail_count_messaging_unread(self):
        if not request.uid:
            return []
        
        uid = request.uid
        user = request.env['res.users'].sudo().browse(uid)
        partner = user.partner_id

        # Recherche des canaux où ce partner est membre
        channels = request.env['mail.channel'].sudo().search([
            ('channel_partner_ids', 'in', [partner.id])
        ])

        result = []
        # The above Python code snippet is iterating over a list of channels and retrieving
        # information about unread messages for each channel and a specific partner. It does the following:
        for channel in channels:
            partner_info = request.env['mail.channel.partner'].sudo().search([
                ('channel_id', '=', channel.id),
                ('partner_id', '=', partner.id),
            ], limit=1)

            if partner_info and partner_info.seen_message_id:
                unread_count = request.env['mail.message'].sudo().search_count([
                    ('model', '=', 'mail.channel'),
                    ('res_id', '=', channel.id),
                    ('id', '>', partner_info.seen_message_id.id),
                ])
            else:
                unread_count = request.env['mail.message'].sudo().search_count([
                    ('model', '=', 'mail.channel'),
                    ('res_id', '=', channel.id),
                ])

            result.append({
                'id': channel.id,
                'uuid': channel.uuid,
                'name': channel.name,
                'channel_type': channel.channel_type,
                'unread_count': unread_count,
            })
        return result
    
    @http.route('/mail/discussions/all', type='json', auth='user')
    def get_combined_discussions(self, limit=30, offset=0, filter_type='all'):
        """
        Un seul endpoint avec 4 options:
        - filter_type='all' → Tout combiné (comportement actuel)
        - filter_type='channels' → Canaux seulement
        - filter_type='activities' → Activités seulement
        - filter_type='notifications' → Notifications système seulement
        """
        try:
            limit = int(limit)
            offset = int(offset)
            partner = request.env.user.partner_id
            
            if filter_type == 'channels':
                return self._get_channels(partner, limit, offset)
            elif filter_type == 'activities':
                return self._get_activities(partner, limit, offset)
            elif filter_type == 'notifications':
                return self._get_system_notifications(partner, limit, offset)
            else:  # 'all' ou par défaut
                return self._get_all_combined(partner, limit, offset)
                
        except Exception as e:
            _logger.error(f"Erreur dans get_combined_discussions: {str(e)}")
            raise

    # -------------------------------------------------------------------
    # 1. Fonction pour les CANAUX seulement
    # -------------------------------------------------------------------
    def _get_channels(self, partner, limit, offset):
        _logger.debug(f"***************Fetching channels for partner {partner.id} with limit={limit}, offset={offset}")
        """Retourne seulement les canaux de discussion"""
        # Récupérer les canaux
        channel_slots = request.env['mail.channel'].channel_fetch_slot()
        all_channels = [c for slot in channel_slots.values() for c in slot]
        channel_ids = [c['id'] for c in all_channels]
        
        # Messages des canaux (comment + email seulement)
        messages = request.env['mail.message'].sudo().search([
            ('model', '=', 'mail.channel'),
            ('res_id', 'in', channel_ids),
            ('message_type', 'in', ['comment', 'email'])
        ], order='date desc')
        
        # Précharger les informations de canal partenaire
        partner_info_map = {
            p.channel_id.id: p
            for p in request.env['mail.channel.partner'].sudo().search([
                ('channel_id', 'in', channel_ids),
                ('partner_id', '=', partner.id)
            ])
        }
        
        # Dernier message par canal
        last_message_map = {}
        for msg in messages:
            if msg.res_id not in last_message_map:
                last_message_map[msg.res_id] = msg
        
        # Formater les canaux
        formatted_channels = []
        for canal in all_channels:
            last_message = last_message_map.get(canal['id'])
            if not last_message:
                continue
            
            partner_info = partner_info_map.get(canal['id'])
            
            # Calcul messages non lus
            if partner_info and partner_info.seen_message_id:
                unread_count = sum(
                    1 for m in messages
                    if m.res_id == canal['id'] and m.id > partner_info.seen_message_id.id
                )
            else:
                unread_count = sum(1 for m in messages if m.res_id == canal['id'])
            
            # Formatage du texte
            clean_text = last_message.body or "Nouveau message"
            is_mine = last_message.author_id.id == partner.id
            
            display_name = canal['name']
            display_text = clean_text
            
            profile_image = None
            if canal['channel_type'] == 'chat':
                other_members = [m['id'] for m in canal.get('members', []) if m['id'] != partner.id]
                if other_members:
                    other_member = request.env['res.partner'].sudo().browse(other_members[0])
                    display_name = other_member.name or other_member.email
                    
                    # URL image profil (image_128 pour mobile)
                    profile_image = f"/web/image/res.partner/{other_member.id}/image_128"
                
                if is_mine:
                    display_text = f"⤻ Vous : {clean_text}"
            else:
                display_text = f"⤻ {'Vous' if is_mine else last_message.author_id.name} : {clean_text}"
            
            formatted_channels.append({
                'uuid': canal['uuid'],
                'name': display_name,
                'conversation_type': canal['channel_type'],
                'text': display_text[:100] + ('...' if len(display_text) > 100 else ''),
                'time': last_message.date.isoformat() if last_message.date else '2000-01-01T00:00:00',
                'channelId': canal['id'],
                'email': getattr(last_message.author_id, 'email', ''),
                'unreadCount': unread_count,
                'filter_type': 'channel',
                # ✅ NOUVEAU
                'profileImage': profile_image
            })
        
        # Trier et paginer
        formatted_channels.sort(key=lambda x: x['time'], reverse=True)
        return formatted_channels[offset:offset + limit]

    # -------------------------------------------------------------------
    # 2. Fonction pour les ACTIVITÉS seulement
    # -------------------------------------------------------------------
    def _get_activities(self, partner, limit, offset):
        """Retourne uniquement la dernière activité + nombre d'activités non lues"""
        _logger.debug(f"***************Fetching last activity for partner {partner.id}")
        
        # 1. Récupérer la DERNIÈRE activité (la plus récente)
        last_activity = request.env['mail.activity'].sudo().search([
            ('user_id', '=', request.env.user.id),  # Activités de l'utilisateur
            ('date_deadline', '!=', False)          # Avec date d'échéance
        ], order='create_date desc', limit=1)     # ← DESC pour avoir la plus récente
        
        if not last_activity:
            return []
        
        # 2. Compter les activités NON LUS/NON TERMINÉES
        # Selon votre logique métier, vous pouvez choisir :
        
        # Option A: Toutes les activités actives
        unread_count = request.env['mail.activity'].sudo().search_count([
            ('user_id', '=', request.env.user.id),
            ('date_deadline', '!=', False),
            ('state', '!=', 'done'),  # Non terminées
            ('state', '!=', 'cancelled')  # Non annulées
        ])
        
        # Option B: Basé sur votre propre logique de "non lu"
        # unread_count = request.env['mail.activity'].sudo().search_count([
        #     ('user_id', '=', request.env.user.id),
        #     ('date_deadline', '!=', False),
        #     ('is_read', '=', False)  # Si vous avez un champ is_read
        # ])
        
        # 3. Déterminer le nom d'affichage selon le type
        info = MailActivityHelper.get_activity_type_info(last_activity.activity_type_id.name)
            # Exemple 
        icon = info['icon']
        color = info['color']
        fcm_display_name = info['display_name']
        
        # 4. Format du texte
        # icon = self._get_activity_icon(last_activity.activity_type_id.name)
        activity_type = last_activity.activity_type_id.name or "Activité"
        res_name = last_activity.res_name or ""
        
        activity_text = f"{activity_type} {res_name} • Échéance: {last_activity.date_deadline}"
        
        # 5. Construire l'URL vers l'enregistrement
        activity_url = ""
        if last_activity.res_model and last_activity.res_id:
            base_url = request.env['ir.config_parameter'].sudo().get_param('web.base.url')
            activity_url = f"{base_url}/web#id={last_activity.res_id}&model={last_activity.res_model}&view_type=form"
        
        # 6. Retourner UNIQUEMENT la dernière activité
        return [{
            'uuid': 'activity_all',  # UUID fixe pour ouvrir TOUTES les activités
            'name': 'Activités',     # Nom fixe pour le canal
            'conversation_type': 'activity',
            'text': activity_text,   # Texte de la dernière activité
            'time': last_activity.create_date if last_activity.create_date else '2000-01-01T00:00:00',
            'channelId': None,
            'email': '',
            'unreadCount': unread_count,  # Nombre TOTAL d'activités non lues
            'target': {
                'model': 'mail.activity',
                'type': last_activity.activity_type_id.name,  # Type de la dernière activité
                'record_name': last_activity.res_name,
                'deadline': str(last_activity.date_deadline),
                'res_id': last_activity.res_id,
                'res_model': last_activity.res_model,
                'url': activity_url  # URL vers l'enregistrement
            },
            'metadata': {
                'total_count': unread_count,  # Nombre total d'activités
                'has_unread': unread_count > 0,
                # 'icon': self._get_activity_icon(last_activity.activity_type_id.name),  # Icône selon type
                # 'color': self._get_activity_color(last_activity.activity_type_id.name),  # Couleur selon type
                'icon': icon,  # Icône selon type
                'color': color,
                'last_activity_id': last_activity.id
            },
            'filter_type': 'activity'
        }]
    











    # -------------------------------------------------------------------
    # 3. Fonction pour les NOTIFICATIONS SYSTÈME seulement
    # -------------------------------------------------------------------
    def _get_system_notifications(self, partner, limit, offset):
        _logger.debug(f"***************Fetching system notifications for partner {partner.id} with limit={limit}, offset={offset}")
        """Retourne seulement les notifications système"""
        system_user_id = request.env.ref('base.user_root').id
        
        # Récupérer les notifications système
        notifications = request.env['mail.message'].sudo().search([
            ('message_type', 'in', ['user_notification', 'notification']),
            ('author_id', '=', system_user_id)
        ], order='date desc', limit=limit + offset + 20)
        
        _logger.debug(f"System notifications fetched: {len(notifications)} for partner {partner.id}")
        
        # Notifications non lues
        unread_notifications = request.env['mail.notification'].sudo().search([
            ('res_partner_id', '=', partner.id),
            ('is_read', '=', False)
        ])
        unread_map = {n.mail_message_id.id: True for n in unread_notifications}
        
        # Grouper par modèle
        grouped_by_model = {}
        for notif in notifications:
            model_key = notif.model or 'other'
            
            if model_key not in grouped_by_model:
                grouped_by_model[model_key] = {
                    'messages': [],
                    'unreadCount': 0,
                    'lastMessageTime': notif.date
                }
            
            grouped_by_model[model_key]['messages'].append(notif)
            if unread_map.get(notif.id):
                grouped_by_model[model_key]['unreadCount'] += 1
            grouped_by_model[model_key]['lastMessageTime'] = max(
                grouped_by_model[model_key]['lastMessageTime'], notif.date
            )
        
        # Titres des modèles
        model_titles = {
            'sale.order': 'Bon de commande',
            'account.move': 'Facture',
            'account.bank.statement': 'Relevé bancaire',
            'res.partner': 'Contact',
            'mail.channel': 'Canal de discussion',
            'stock.picking': 'Transfert de stock',
            'mail.activity': 'Activité',
        }
        
        # Formater les groupes
        formatted_notifications = []
        for model, group in grouped_by_model.items():
            if all(not (m.body or '').strip() for m in group['messages']):
                continue
            
            last_message = group['messages'][0]
            last_body = (last_message.body or '').strip()
            res_id = last_message.res_id if last_message and last_message.res_id else 0
            
            formatted_notifications.append({
                'uuid': f'group_{model}',
                'name': model_titles.get(model, model),
                'conversation_type': 'notification',
                'text': f"{last_body[:80]}...",
                'time': group['lastMessageTime'] or '2000-01-01T00:00:00',
                'channelId': None,
                'email': '',
                'unreadCount': group['unreadCount'],
                'target': {
                    'model': model,
                    'res_id': res_id
                },
                'filter_type': 'notification'
            })
        
        # Trier et paginer
        formatted_notifications.sort(key=lambda x: x['time'], reverse=True)
        return formatted_notifications[offset:offset + limit]

    # -------------------------------------------------------------------
    # 4. Fonction pour TOUT combiné (comportement original)
    # -------------------------------------------------------------------
    def _get_all_combined(self, partner, limit, offset):
        """Retourne tout combiné - votre logique originale"""
        # Appeler les 3 fonctions
        channels = self._get_channels(partner, limit//3 + 10, 0)
        activities = self._get_activities(partner, limit//3 + 10, 0)
        notifications = self._get_system_notifications(partner, limit//3 + 10, 0)
        
        _logger.debug(f"++++ Channels fetched: {len(channels)}")
        _logger.debug(f"++++ Activities fetched: {len(activities)}")
        # _logger.debug(f"Notifications fetched: {len(notifications)}")
        
        # Combiner
        combined_list = channels + activities + notifications
        _logger.debug(f"++++ Combined list size before sorting: {len(combined_list)}")
        # Trier par date
        # combined_list.sort(key=lambda x: x['time'], reverse=True)
        combined_list.sort(key=lambda x: self._normalize_time_for_sorting(x['time']), reverse=True)
        _logger.debug(f"++++ Combined list size after sorting: {len(combined_list)}")
        # Paginer
        paginated_list = combined_list[offset:offset + limit]
        
        # Ajouter un flag pour indiquer le type (pour le tri mobile)
        for item in paginated_list:
            if 'filter_type' not in item:
                if item['conversation_type'] == 'channel':
                    item['filter_type'] = 'channel'
                elif item['conversation_type'] == 'activity':
                    item['filter_type'] = 'activity'
                elif item['conversation_type'] == 'notification':
                    item['filter_type'] = 'notification'
        return paginated_list
    
    def _normalize_time_for_sorting(self, time_value):
        """
        Convertit n'importe quel format de time en datetime pour le tri
        Accepte: string, datetime, date, ou None
        """
        from datetime import datetime
        
        if not time_value:
            return datetime.min
        
        try:
            # ★★★ CORRECTION : Vérifier d'abord si c'est déjà un datetime ★★★
            if isinstance(time_value, datetime):
                return time_value
            
            # Si c'est une date (sans heure)
            if hasattr(time_value, 'strftime') and not hasattr(time_value, 'hour'):
                # Convertir date en datetime (minuit)
                return datetime.combine(time_value, datetime.min.time())
            
            # Si c'est une chaîne de caractères
            if isinstance(time_value, str):
                # Essayer format ISO "2025-12-29T07:17:55"
                if 'T' in time_value:
                    return datetime.fromisoformat(time_value.replace('Z', '+00:00'))
                # Essayer format simple "2025-12-29 07:41:59"
                else:
                    # Essayez plusieurs formats courants
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
                        try:
                            return datetime.strptime(time_value, fmt)
                        except ValueError:
                            continue
            
            # Si on arrive ici, c'est un type non géré
            _logger.warning(f"Type non géré pour le tri: {type(time_value)} - {time_value}")
            return datetime.min
            
        except Exception as e:
            _logger.warning(f"Erreur de conversion time: {time_value} (type: {type(time_value)}) - {str(e)}")
            return datetime.min
    
    
    
    
    
    
    
    
    
    
    
    
    @http.route('/mail/get_suggested_recipients', type='json', auth='user')
    def message_get_suggested_recipients(self, model, res_ids):
        records = request.env[model].browse(res_ids)
        try:
            records.check_access_rule('read')
            records.check_access_rights('read')
        except:
            return {}
        return records._message_get_suggested_recipients()
    
    @http.route('/mail/channel/seen', type='json', auth='user', methods=['POST'])
    def channel_seen(self, channel_id=None, last_message_id=None, uuid=None):
        """
        Mark messages in a channel as seen up to last_message_id for the current user.
        """
        try:
            user = request.env.user
            partner = user.partner_id
            
            # 🔹 Cas 1 : groupe de notifications
            if uuid and uuid.startswith("group_"):
                model = uuid.replace("group_", "", 1)

                if not last_message_id:
                    return {
                        'jsonrpc': '2.0',
                        'error': {'code': 400, 'message': 'Missing last_message_id for notifications'}
                    }

                # Marquer toutes les notifs du modèle comme lues jusqu’à last_message_id
                domain = [
                    ('res_partner_id', '=', partner.id),
                    ('is_read', '=', False),
                    ('mail_message_id.model', '=', model),
                    ('mail_message_id.id', '<=', int(last_message_id))
                ]
                notifications = request.env['mail.notification'].sudo().search(domain)
                notifications.write({'is_read': True})

                # Recalcul du unread_count
                unread_count = request.env['mail.notification'].sudo().search_count([
                    ('res_partner_id', '=', partner.id),
                    ('is_read', '=', False),
                    ('mail_message_id.model', '=', model),
                ])

                return {
                    'jsonrpc': '2.0',
                    'result': {
                        'success': True,
                        'uuid': uuid,
                        'last_message_id': last_message_id,
                        'unreadCount': unread_count
                    }
                }
                
            # 🔹 Cas 2 : channel normal
            if not channel_id or not last_message_id:
                return {
                    'jsonrpc': '2.0',
                    'error': {'code': 400, 'message': 'Missing channel_id or last_message_id'}
                }

            # Fetch the channel
            channel = request.env['mail.channel'].sudo().browse(int(channel_id)).exists()
            if not channel:
                return {'jsonrpc': '2.0', 'error': {'code': 404, 'message': 'Channel not found'}}

            # Ensure user is a member
            if partner.id not in channel.channel_partner_ids.mapped('id'):
                return {'jsonrpc': '2.0', 'error': {'code': 403, 'message': 'User not a member of the channel'}}

            # Fetch the last message
            message = request.env['mail.message'].sudo().browse(int(last_message_id)).exists()
            if not message or message.model != 'mail.channel' or message.res_id != channel.id:
                return {'jsonrpc': '2.0', 'error': {'code': 404, 'message': 'Invalid message_id for this channel'}}

            # Update seen_message_id
            channel_partner = request.env['mail.channel.partner'].sudo().search([
                ('channel_id', '=', channel.id),
                ('partner_id', '=', partner.id)
            ], limit=1)
            if channel_partner:
                channel_partner.write({'seen_message_id': last_message_id})
            else:
                return {'jsonrpc': '2.0', 'error': {'code': 404, 'message': 'Channel partner record not found'}}

            # Update notifications in one query
            notifications = request.env['mail.notification'].sudo().search([
                ('res_partner_id', '=', partner.id),
                ('is_read', '=', False),
                ('mail_message_id.model', '=', 'mail.channel'),
                ('mail_message_id.res_id', '=', channel.id),
                ('mail_message_id.id', '<=', last_message_id)
            ])
            notifications.write({'is_read': True})

            # Recalculate unread_count
            unread_count = request.env['mail.message'].sudo().search_count([
                ('model', '=', 'mail.channel'),
                ('res_id', '=', channel.id),
                ('id', '>', last_message_id)
            ])

            return {
                'jsonrpc': '2.0',
                'result': {
                    'success': True,
                    'channel_id': channel.id,
                    'last_message_id': last_message_id,
                    'unreadCount': unread_count
                }
            }

        except (AccessError, ValidationError) as e:
            return {'jsonrpc': '2.0', 'error': {'code': 403, 'message': f'Access error: {str(e)}'}}
        except Exception as e:
            _logger.error(f"Erreur dans channel_seen: {str(e)}")
            return {'jsonrpc': '2.0', 'error': {'code': 500, 'message': f'Internal server error: {str(e)}'}}
        