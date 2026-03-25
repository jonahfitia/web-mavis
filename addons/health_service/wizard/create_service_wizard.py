# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError
import pprint


class HeatlhServiceCreationWizard(models.TransientModel):
    _name = 'health.service.create.wizard'
    _description = "Create Health Service from this wizard"

    patient_code = fields.Char(string="Code d'identification")
    patient_name = fields.Char('Patient', required=True)
    patient_birthday = fields.Date(string="Date de naissance", required=True)
    patient_gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
        ('other', 'Autre')], string='Gender', required=True)
    patient_phone = fields.Char('Mobile')
    patient_mail = fields.Char('E-mail')
    patient_adress = fields.Char('Adresse')
    patient_person_contact = fields.Char('Personne de contact')
    patient_marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married')], string='Marital Status', tracking=True)
    similar_patient_list = fields.Many2many('hms.patient', string="Patient Similaire", readonly="1")
    is_btn_create_visible = fields.Boolean(compute="_onchange_similar_patient_list")
    #===GESTION ASSURANCE
    profil_type = fields.Selection(
        [('fonc_activity', 'Fonctionnaire en activité'),
         ('fonc_pensioner', 'Fonctionnaire retraité'),
         ('pec_privee', 'Assurance Privée'),
         ('other', 'Client divers'),
         ('arovy', 'AROVY'),
         ('smi', 'SMI'),
         ('pecgr', 'PECGR'),
         ('remboursement', 'Tarif remboursé'),
        ], string='Type profil',
        help="Utilisé pour le choix de profil du patient")
    patient_assurance = fields.Many2one('res.partner',string='Assurance')
    #property_product_pricelist = fields.Many2one(related='patient_assurance.property_product_pricelist')
    property_product_pricelist = fields.Many2one(
        'product.pricelist', 'Pricelist', 
        domain=lambda self: [('company_id', 'in', (self.env.company.id, False))])
    patient_pension = fields.Char("Numéro pension")
    gov_code = fields.Char(string='CIN')


    @api.onchange('patient_code','patient_name', 'patient_birthday', 'patient_gender', 'patient_phone', 
                    'patient_mail', 'patient_person_contact', 'patient_adress', 'patient_marital_status',
                    'patient_assurance', 'patient_pension','gov_code')
    def _onchange_search_patients(self):
        domain = []
        if self.patient_code:
            domain.append(('code', 'ilike', self.patient_code))
        if self.patient_name:
            domain.append(('name', 'ilike', self.patient_name))
        if self.patient_birthday:
            domain.append(('birthday', '=', self.patient_birthday))
        if self.patient_gender:
            domain.append(('gender', 'ilike', self.patient_gender))
        if self.patient_phone:
            domain.append(('mobile', 'ilike', self.patient_phone))
        if self.patient_mail:
            domain.append(('email', 'ilike', self.patient_mail))
        if self.patient_person_contact:
            domain.append(('preson_contact', 'ilike', self.patient_person_contact))
        if self.patient_adress:
            domain.append(('street', 'ilike', self.patient_adress))
        if self.patient_marital_status:
            domain.append(('marital_status', 'ilike', self.patient_marital_status))
        if self.gov_code:
            domain.append(('gov_code', 'ilike', self.gov_code))
        if self.patient_assurance:
            domain.append(('assurance', 'ilike', self.patient_assurance.id))
        if self.patient_pension:
            domain.append(('pension', 'ilike', self.patient_pension))

        similar_patients = self.env['hms.patient'].search(domain,order='create_date desc', limit=10)
        self.similar_patient_list = [(6, 0, similar_patients.ids)]

    @api.onchange('similar_patient_list')
    def _onchange_similar_patient_list(self):
        self.is_btn_create_visible = not self.similar_patient_list

    def confirm_patient_creation_from_hs(self):
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmer la creation du patient',
            'res_model': 'create.patient.health.service',
            'view_mode': 'form',
            'view_id': self.env.ref('health_service.patient_creation_confirmation_from_hs_view_form').id,
            'target': 'new',
            'context': {
                'default_patient_code': self.patient_code,
                'default_patient_name': self.patient_name,
                'default_patient_birthday': self.patient_birthday,
                'default_patient_gender': self.patient_gender,
                'default_patient_phone': self.patient_phone,
                'default_patient_mail': self.patient_mail,
                'default_patient_adress': self.patient_adress,
                'default_patient_person_contact': self.patient_person_contact,
                'default_patient_marital_status': self.patient_marital_status,
                'default_gov_code': self.gov_code,
                'default_patient_assurance': self.patient_assurance.id,
                'default_patient_pension': self.patient_pension,
                'default_property_product_pricelist': self.property_product_pricelist.id,
            }
        }

class CreatePatientandHealthService(models.TransientModel):
    _name = 'create.patient.health.service'
    _description = "This wizard aims to ask a confirmation from user for patient creation"

    patient_name = fields.Char('Patient', readonly=True)
    patient_birthday = fields.Date(string="Date de naissance", readonly=True)
    patient_gender = fields.Selection([
        ('male', 'Homme'),
        ('female', 'Femme'),
        ('other', 'Autre')], string='Gender', required=True, readonly=True)
    patient_phone = fields.Char('Mobile', readonly=True)
    patient_mail = fields.Char('E-mail', readonly=True)
    patient_adress = fields.Char('Adresse', readonly=True)
    patient_person_contact = fields.Char('Personne de contact', readonly=True)
    patient_marital_status = fields.Selection([
        ('single', 'Single'),
        ('married', 'Married')], string='Marital Status', readonly=True)
    #===GESTION ASSURANCE
    profil_type = fields.Selection(
        [('fonc_activity', 'Fonctionnaire en activité'),
         ('fonc_pensioner', 'Fonctionnaire retraité'),
         ('pec_privee', 'Assurance Privée'),
         ('other', 'Client divers'),
         ('arovy', 'AROVY'),
         ('smi', 'SMI'),
         ('pecgr', 'PECGR'),
         ('remboursement', 'Tarif remboursé'),
        ], string='Type profil',
        help="Utilisé pour le choix de profil du patient")
    patient_assurance = fields.Many2one('res.partner',string='Assurance')
    #property_product_pricelist = fields.Many2one(related='patient_assurance.property_product_pricelist')
    property_product_pricelist = fields.Many2one(
        'product.pricelist', 'Pricelist', 
        domain=lambda self: [('company_id', 'in', (self.env.company.id, False))])
    patient_pension = fields.Char("Numéro pension")
    gov_code = fields.Char(string='CIN')

    def action_create_patient_hs(self):
        values = {
            'name': self.patient_name or False,
            'birthday': self.patient_birthday or False,
            'gender': self.patient_gender or False,
            'mobile': self.patient_phone or False,
            'email': self.patient_mail or False,
            'street': self.patient_adress or False,
            'preson_contact': self.patient_person_contact or False,
            'marital_status': self.patient_marital_status or False,
            'pension': self.patient_pension or False,
            'gov_code': self.gov_code or False,
        }
        partner_values = {
            'assurance': self.patient_assurance.id or False,
            'property_product_pricelist': self.property_product_pricelist.id or False,
        }
        new_patient = self.env['hms.patient'].sudo().create(values)
        partner = self.env['res.partner'].sudo().search([('id', '=',new_patient.partner_id.id)])
        partner.write(partner_values)
        new_patient_id = new_patient.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'acs.health_service',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_patient_id': new_patient_id,
            },
        }



# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: