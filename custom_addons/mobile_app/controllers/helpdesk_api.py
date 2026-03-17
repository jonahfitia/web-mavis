from odoo import http, fields
from odoo.http import request
import logging
import json



# from collections import defaultdict
_logger = logging.getLogger(__name__)
import functools



class HelpdeskAPI(http.Controller):

#_TAKING SALE MOVES#     
    @http.route('/api/helpdesk_support', type='json', auth='user', methods=['POST'], csrf=False)
    def get_helpdesk_support(self, **kwargs):        
        helpdesk_support = request.env['helpdesk.support'].sudo().search([]) # type: ignore
        stages = request.env['helpdesk.stage.config'].sudo().search([]) # type: ignore
        _logger.info("helpdesk_support: %s", helpdesk_support)
        result = {}       
        helpdesk_support_list = []
        stage_list = []
        if stages:
            for rec in stages:
                stage_list.append({
                    'id': rec.id,
                    'name': rec.name,
                    'sequence': rec.sequence,
                    'stage_type': rec.stage_type,                                        
                })
        if helpdesk_support:
            for rec in helpdesk_support:
                helpdesk_support_list.append({
                    'id': rec.id,
                    'name': rec.name,
                    'subject': rec.subject,
                    'custom_customer_name': rec.custom_customer_name,
                    'category': rec.category,
                    'type_ticket_id': rec.type_ticket_id.name,
                    'priority': rec.priority,
                    'email': rec.email,
                    'close_date': rec.close_date,
                    'user_id': rec.user_id.name,
                    'team_id': rec.team_id.name,
                    'is_closed': rec.is_close,
                    'is_invoice_created': rec.is_invoice_created,                    
                    'stage_name': rec.stage_id.name,             
                    'stage_id': rec.stage_id.id,      
                })
            
        result['helpdesk_support'] = helpdesk_support_list
        result['stages'] = stage_list
        return {'status': 200, 'response': result, 'message': 'Success'}    
    
    @http.route('/api/helpdesk_assign_stage', type='json', auth='user', methods=['POST'], csrf=False)
    def assign_stage(self, ticket_id, stage_id, **kwargs):
        """
        Endpoint JSON pour assigner un ticket à un stage.
        Reçoit ticket_id et stage_id dans le body JSON.
        """        

        if not ticket_id or not stage_id:
            _logger.warning("Paramètres manquants: ticket_id=%s, stage_id=%s", ticket_id, stage_id)
            return {'status': 400, 'message': 'ticket_id et stage_id requis'}

        try:
            ticket_id = int(ticket_id)
            stage_id = int(stage_id)
        except ValueError:
            _logger.warning("IDs invalides: ticket_id=%s, stage_id=%s", ticket_id, stage_id)
            return {'status': 400, 'message': 'ticket_id et stage_id doivent être des entiers'}

        ticket = request.env['helpdesk.support'].sudo().search([('id', '=', ticket_id)]) # type: ignore
        stage = request.env['helpdesk.stage.config'].sudo().search([('id', '=', stage_id)]) # type: ignore
        if not ticket.exists() or not stage.exists():
            _logger.warning("Ticket ou Stage introuvable: ticket_id=%s, stage_id=%s", ticket_id, stage_id)
            return {'status': 404, 'message': 'Ticket ou Stage introuvable'}

        _logger.info("Ticket trouvé: %s (%s), Stage trouvé: %s (%s)", ticket.id, ticket.name, stage.id, stage.name)
        _logger.info("Avant write: stage_id=%s, stage_type=%s", ticket.stage_id.id, ticket.stage_type)

        try:
            ticket.write({
                'stage_id': stage.id,
                'stage_type': stage.stage_type
            })
            # request.env.cr.commit()

            _logger.info("Après write: stage_id=%s, stage_type=%s", ticket.stage_id.id, ticket.stage_type)
            _logger.info("Ticket %s assigné au stage %s avec succès", ticket.name, stage.name)
            return {
                'status': 200,
                'message': 'Stage mis à jour avec succès',
                'ticket': {
                    'id': ticket.id,
                    'name': ticket.name,
                    'stage_id': ticket.stage_id.id,
                    'stage_name': ticket.stage_id.name,
                    'stage_type': ticket.stage_type
                }
            }

        except Exception as e:
            _logger.error("Erreur lors de l'assignation du stage: %s", e, exc_info=True)
            return {'status': 500, 'message': 'Erreur serveur'}
    
    @http.route('/api/helpdesk/form', type='json', auth='user', methods=['POST'], csrf=False)
    def get_helpdesk_form_data(self, ticket_id=None, **kwargs):
        """
        JSON-RPC endpoint pour récupérer les métadonnées du formulaire et les données d'un ticket.        
        """

        try:
            # Vérifier l'accès utilisateur
            if not request.env.user:
                return {'error': 'Authentification requise'}

            # Modèle cible
            ticket_model = request.env['helpdesk.support'].sudo() # type: ignore

            # Liste des champs à exposer, basée sur la vue XML
            form_fields = [
                'name', 'subject', 'company_id', 'subject_type_id', 'type_ticket_id', 'user_id', 'team_id', 'priority', 'email', 'stage_id', 'category', 'custom_customer_name'
            ]
        except Exception as e:
            _logger.error("Erreur lors de la recherche des métadonnées du formulaire: %s", e, exc_info=True)            
    # @http.route('/api/helpdesk/form', type='json', auth='user', methods=['POST'], csrf=False)
    # def get_helpdesk_form_data(self, ticket_id=None, **kwargs):
    #     """
    #     JSON-RPC endpoint pour récupérer les métadonnées du formulaire et les données d'un ticket.
    #     :param ticket_id: ID du ticket à modifier (facultatif).
    #     :return: Dictionnaire JSON avec métadonnées, valeurs par défaut ou données du ticket.
    #     """
    #     try:
    #         # Vérifier l'accès utilisateur
    #         if not request.env.user:
    #             return {'error': 'Authentification requise'}

    #         # Modèle cible
    #         ticket_model = request.env['helpdesk.support'].sudo()

    #         # Liste des champs à exposer, basée sur la vue XML
    #         form_fields = [
    #             'name', 'subject', 'company_id', 'subject_type_id', 'type_ticket_id', 'user_id',
    #             'email', 'custome_client_user_id', 'custom_project_task_ids', 'patient_id',
    #             'partner_id', 'custom_customer_name', 'phone', 'allow_user_ids', 'team_id',
    #             'project_id', 'department_id', 'team_leader_id', 'analytic_account_id',
    #             'priority', 'crra_priority', 'crra_urgence', 'category', 'request_date',
    #             'is_close', 'helpdesk_duration_timer', 'helpdesk_duration', 'close_date',
    #             'total_spend_hours', 'total_consumed_hours', 'total_purchase_hours',
    #             'remaining_hours', 'balanced_remaining_hours', 'description',
    #             'timesheet_line_ids', 'invoice_line_ids', 'invoice_id', 'journal_id',
    #             'rating', 'comment', 'type_request_id', 'number_ticket', 'objet',
    #             'date_intervention', 'heure_debut', 'heure_dep_imm', 'patient_name',
    #             'age', 'patient_gender', 'date_naissance', 'pat_phone', 'pat_mail',
    #             'pat_adresse', 'tiers_name', 'tiers_age', 'tiers_gender', 'tiers_naissance',
    #             'tiers_phone', 'tiers_mail', 'tiers_adresse', 'tiers_paiement',
    #             'chauffeur', 'vehicule', 'lieu_intervention', 'geoloc', 'trajet',
    #             'motif', 'resume_hdm', 'medoc_pathologie', 'medo_cours', 'antecedent',
    #             'allergies'
    #         ]

    #         # Obtenir les métadonnées des champs
    #         fields_info = ticket_model.fields_get(allfields=form_fields)

    #         # Construire la structure du formulaire
    #         form_data = {
    #             'fields': {},
    #             'defaults': {},
    #             'values': {},
    #             'domains': {},
    #             'attrs': {},
    #             'groups': {},
    #         }

    #         # Vérifier les groupes d'accès
    #         user_groups = request.env.user.groups_id.mapped('full_name')
    #         has_crra_access = 'website_helpdesk_support_ticket.group_helpdesk_crra' in user_groups
    #         has_manager_access = 'website_helpdesk_support_ticket.group_helpdesk_manager' in user_groups
    #         has_analytic_access = 'analytic.group_analytic_accounting' in user_groups

    #         # Remplir les métadonnées
    #         for field in form_fields:
    #             if field in fields_info:
    #                 field_def = fields_info[field]
    #                 # Vérifier les permissions
    #                 if field in ['patient_id', 'crra_priority', 'crra_urgence', 'type_request_id',
    #                             'number_ticket', 'objet', 'date_intervention', 'heure_debut',
    #                             'heure_dep_imm', 'patient_name', 'age', 'patient_gender',
    #                             'date_naissance', 'pat_phone', 'pat_mail', 'pat_adresse',
    #                             'tiers_name', 'tiers_age', 'tiers_gender', 'tiers_naissance',
    #                             'tiers_phone', 'tiers_mail', 'tiers_adresse', 'tiers_paiement',
    #                             'chauffeur', 'vehicule', 'lieu_intervention', 'geoloc', 'trajet',
    #                             'motif', 'resume_hdm', 'medoc_pathologie', 'medo_cours',
    #                             'antecedent', 'allergies'] and not has_crra_access:
    #                     continue
    #                 if field in ['invoice_line_ids', 'journal_id'] and not has_manager_access:
    #                     continue
    #                 if field == 'analytic_account_id' and not has_analytic_access:
    #                     continue

    #                 form_data['fields'][field] = {
    #                     'type': field_def['type'],
    #                     'string': field_def['string'],
    #                     'required': field_def.get('required', False),
    #                     'help': field_def.get('help', ''),
    #                 }
    #                 if field_def['type'] == 'selection':
    #                     form_data['fields'][field]['selection'] = field_def['selection']
    #                 elif field_def['type'] == 'many2one':
    #                     form_data['fields'][field]['relation'] = field_def['relation']
    #                     form_data['fields'][field]['domain'] = field_def.get('domain', [])
    #                     related_model = request.env[field_def['relation']].sudo()
    #                     options = related_model.search_read([], ['id', 'name'], limit=100)
    #                     form_data['fields'][field]['options'] = options
    #                 # Attributs dynamiques
    #                 form_data['attrs'][field] = {
    #                     'readonly': [('stage_type', '=', 'closed')]
    #                 }
    #                 # Groupes d'accès
    #                 form_data['groups'][field] = {
    #                     'crra': field in ['patient_id', 'crra_priority', 'crra_urgence', 'type_request_id',
    #                                      'number_ticket', 'objet', 'date_intervention', 'heure_debut',
    #                                      'heure_dep_imm', 'patient_name', 'age', 'patient_gender',
    #                                      'date_naissance', 'pat_phone', 'pat_mail', 'pat_adresse',
    #                                      'tiers_name', 'tiers_age', 'tiers_gender', 'tiers_naissance',
    #                                      'tiers_phone', 'tiers_mail', 'tiers_adresse', 'tiers_paiement',
    #                                      'chauffeur', 'vehicule', 'lieu_intervention', 'geoloc', 'trajet',
    #                                      'motif', 'resume_hdm', 'medoc_pathologie', 'medo_cours',
    #                                      'antecedent', 'allergies'],
    #                     'manager': field in ['invoice_line_ids', 'journal_id'],
    #                     'analytic': field == 'analytic_account_id',
    #                 }

    #         # Données du ticket
    #         if ticket_id:
    #             ticket = ticket_model.browse(int(ticket_id))
    #             if ticket.exists():
    #                 form_data['values'] = ticket.read(form_fields)[0]
    #                 for field in form_fields:
    #                     if field in fields_info and fields_info[field]['type'] == 'many2one' and form_data['values'].get(field):
    #                         form_data['values'][field] = [form_data['values'][field], ticket[field].name]
    #                 form_data['values']['stage_type'] = ticket.stage_id.stage_type
    #             else:
    #                 return {'error': 'Ticket non trouvé'}
    #         else:
    #             form_data['defaults'] = ticket_model.default_get(form_fields)

    #         # Domaines dynamiques
    #         subject_type_id = form_data['values'].get('subject_type_id') or form_data['defaults'].get('subject_type_id')
    #         form_data['domains']['type_ticket_id'] = [('subject_type_id', '=', subject_type_id)]
    #         form_data['domains']['stage_id'] = ['|', ('team_id', '=', False), ('team_id', '=', form_data['values'].get('team_id') or form_data['defaults'].get('team_id'))]

    #         # Structure de réponse JSON-RPC
    #         return {
    #             'response': {
    #                 'form_data': form_data,
    #                 'stages': request.env['helpdesk.stage.config'].sudo().search_read([], ['id', 'name', 'stage_type'])
    #             }
    #         }
    #     except Exception as e:
    #         _logger.error("Erreur dans get_helpdesk_form_data: %s", str(e))
    #         return {'error': str(e)}

    # @http.route('/api/helpdesk/submit', type='json', auth='user', methods=['POST'], csrf=False)
    # def submit_helpdesk_form(self, ticket_data, ticket_id=None, **kwargs):
    #     """
    #     Soumet les données du formulaire pour créer ou mettre à jour un ticket.
    #     :param ticket_data: Dictionnaire des données du formulaire.
    #     :param ticket_id: ID du ticket à mettre à jour (facultatif).
    #     """
    #     try:
    #         ticket_model = request.env['helpdesk.support'].sudo()

    #         # Filtrer les champs selon les groupes d'accès
    #         user_groups = request.env.user.groups_id.mapped('full_name')
    #         has_crra_access = 'website_helpdesk_support_ticket.group_helpdesk_crra' in user_groups
    #         has_manager_access = 'website_helpdesk_support_ticket.group_helpdesk_manager' in user_groups
    #         has_analytic_access = 'analytic.group_analytic_accounting' in user_groups

    #         allowed_fields = [
    #             field for field in ticket_data.keys()
    #             if field not in [
    #                 'patient_id', 'crra_priority', 'crra_urgence', 'type_request_id',
    #                 'number_ticket', 'objet', 'date_intervention', 'heure_debut',
    #                 'heure_dep_imm', 'patient_name', 'age', 'patient_gender',
    #                 'date_naissance', 'pat_phone', 'pat_mail', 'pat_adresse',
    #                 'tiers_name', 'tiers_age', 'tiers_gender', 'tiers_naissance',
    #                 'tiers_phone', 'tiers_mail', 'tiers_adresse', 'tiers_paiement',
    #                 'chauffeur', 'vehicule', 'lieu_intervention', 'geoloc', 'trajet',
    #                 'motif', 'resume_hdm', 'medoc_pathologie', 'medo_cours',
    #                 'antecedent', 'allergies'
    #             ] or has_crra_access
    #             and field not in ['invoice_line_ids', 'journal_id'] or has_manager_access
    #             and field != 'analytic_account_id' or has_analytic_access
    #         ]
    #         filtered_data = {k: v for k, v in ticket_data.items() if k in allowed_fields}

    #         if ticket_id:
    #             ticket = ticket_model.browse(int(ticket_id))
    #             if ticket.exists():
    #                 ticket.write(filtered_data)
    #                 return {'response': {'status': 'success', 'ticket_id': ticket.id}}
    #             else:
    #                 return {'error': 'Ticket non trouvé'}
    #         else:
    #             ticket = ticket_model.create(filtered_data)
    #             return {'response': {'status': 'success', 'ticket_id': ticket.id}}
    #     except Exception as e:
    #         _logger.error("Erreur dans submit_helpdesk_form: %s", str(e))
    #         return {'error': str(e)}

    # @http.route('/api/helpdesk/options/<string:model>', type='json', auth='user', methods=['POST'], csrf=False)
    # def get_related_options(self, model, domain=None, **kwargs):
    #     """
    #     Récupère les options pour un champ many2one.
    #     :param model: Nom du modèle (ex: 'res.partner', 'ticket.type').
    #     :param domain: Domaine de recherche au format JSON.
    #     """
    #     try:
    #         related_model = request.env[model].sudo()
    #         domain = json.loads(domain) if domain else []
    #         options = related_model.search_read(domain, ['id', 'name'], limit=100)
    #         return {'response': {'options': options}}
    #     except Exception as e:
    #         _logger.error("Erreur dans get_related_options: %s", str(e))
    #         return {'error': str(e)}