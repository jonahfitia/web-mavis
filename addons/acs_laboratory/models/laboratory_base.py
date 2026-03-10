# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression
from datetime import date, datetime
from odoo.tools.float_utils import float_compare

import logging
_logger = logging.getLogger(__name__)


class ACSLabTestUom(models.Model):
    _name = "acs.lab.test.uom"
    _description = "Lab Test UOM"
    _order = 'sequence asc'
    _rec_name = 'code'

    name = fields.Char(string='UOM Name', required=True)
    code = fields.Char(string='Code', required=True, index=True, help="Short name - code for the test UOM")
    sequence = fields.Integer("Sequence", default="100")

    _sql_constraints = [('code_uniq', 'unique (name)', 'The Lab Test code must be unique')]


class AcsLaboratory(models.Model):
    _name = 'acs.laboratory'
    _description = 'Laboratory'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin']
    _inherits = {
        'res.partner': 'partner_id',
    }

    description = fields.Text()
    is_collection_center = fields.Boolean('Is Collection Center')
    partner_id = fields.Many2one('res.partner', 'Partner', ondelete='restrict', required=True)
    group_techlab = fields.Many2many(comodel_name='res.partner', string="Technicien de laboratoire",
                                   domain=[('type_prof', '=', 'is_techlab')])
    group_medlab = fields.Many2many('hms.physician', string="Biologiste")


class LabTest(models.Model):
    _name = "acs.lab.test"
    _description = "Lab Test Type"

    name = fields.Char(string='Name', help="Test type, eg X-Ray, hemogram,biopsy...", index=True)
    code = fields.Char(string='Code', help="Short name - code for the test")
    description = fields.Text(string='Description')
    product_id = fields.Many2one('product.product',string='Service', required=True)
    critearea_ids = fields.One2many('lab.test.critearea','test_id', string='Test Cases')
    remark = fields.Char(string='Remark')
    report = fields.Text (string='Test Report')
    company_id = fields.Many2one('res.company', ondelete='restrict',
        string='Company' ,default=lambda self: self.env.user.company_id.id)
    consumable_line_ids = fields.One2many('hms.consumable.line', 'lab_test_id',
        string='Consumable Line')
    acs_tat = fields.Char(string='Turnaround Time')
    test_type = fields.Selection([
        ('pathology','Pathology'),
        ('radiology','Radiology'),
    ], string='Test Type', default='pathology')
    result_value_type = fields.Selection([
        ('quantitative','Quantitative'),
        ('qualitative','Qualitative'),
    ], string='Result Type', default='quantitative')
    sample_type_id = fields.Many2one('acs.laboratory.sample.type', string='Sample Type')
    cat_analyse = fields.Selection([
        ('hematologie', 'HEMATOLOGIE'),
        ('bacteriologie', 'BACTERIOLOGIE'),
        ('parasitologie', 'PARASITOLOGIE'),
        ('biochimie', 'BIOCHIMIE'),
        ('hormonologie', 'HORMONOLOGIE'),
        ('immunologie', 'IMMUNOLOGIE'),
        ('anatomopathologie', 'ANATOMOPATHOLOGIE'),
        ('serologie', 'SEROLOGIE'),
        ('marqueurs_tumoraux', 'MARQUEURS TUMORAUX'),
        ('biochimie_utinaire', 'BIOCHIMIE UTINAIRE'),
    ], string='catégorie analyse')

    _sql_constraints = [
        ('code_company_uniq', 'unique (code,company_id)', 'The code of the account must be unique per company !')
    ]

    def name_get(self):
        res = []
        for rec in self:
            name = rec.name
            if rec.code:
                name = "%s [%s]" % (rec.name, rec.code)
            res += [(rec.id, name)]
        return res

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('code', operator, name)]
        return self._search(expression.AND([domain, args]), limit=limit, access_rights_uid=name_get_uid)


class UsualReference(models.Model):
    _name= "lab.usual.reference"
    _description = "Valeur de référence par tranche âge"

    critearea_id = fields.Many2one('lab.test.critearea', string='Service', readonly=True)
    range_age = fields.Char('Catégorie âge')
    age_unite = fields.Selection([
        ('Days', "Jours"),
        ('Month', "Mois"),
        ('Year', "Années"),
    ], default='_Year', string="Unité âge")
    normal_range_male = fields.Char('Normal Range (Male)')
    normal_range_female = fields.Char('Normal Range (Female)')
    reference_spec_male = fields.Char('Valeur de référence spécifique (Homme)',
                                      help="Valeur pour afficher plusieurs interprétions")
    reference_spec_female = fields.Char('Valeur de référence spécifique (Femme)',
                                        help="Valeur pour afficher plusieurs interprétions")
    # result_type = fields.Selection([
    #     ('low', "Low"),
    #     ('normal', "Normal"),
    #     ('high', "High"),
    #     ('positive', "Positive"),
    #     ('negative', "Negative"),
    #     ('warning', "Warning"),
    #     ('danger', "Danger"),
    # ], default='normal', string="Result Type", help="Technical field for UI purpose.")
    # interpretation = fields.Char("Interpretation")


class LabTestCritearea(models.Model):
    _name = "lab.test.critearea"
    _description = "Lab Test Criteria"
    _order="sequence, id asc"

    name = fields.Char('Parameter')
    code = fields.Char('Code')
    sequence = fields.Integer('Sequence')
    group_sequence = fields.Integer('Groupe')
    result = fields.Char('Resultat')
    prev_result = fields.Char('Résultat antérieur')
    lab_uom_id = fields.Many2one('acs.lab.test.uom', string='UOM')
    remark = fields.Char('Remark')
    normal_range = fields.Char('Normal Range')
    normal_range_male = fields.Char('Normal Range (Male)')
    normal_range_female = fields.Char('Normal Range (Female)')
    test_id = fields.Many2one('acs.lab.test','Test type', ondelete='cascade')
    patient_lab_id = fields.Many2one('patient.laboratory.test','Lab Test', ondelete='cascade')
    request_id = fields.Many2one('acs.laboratory.request', 'Lab Request', ondelete='cascade')
    company_id = fields.Many2one('res.company', ondelete='restrict',
        string='Company',default=lambda self: self.env.user.company_id.id)
    display_type = fields.Selection([
        ('line_section', "Section"),
        ('line_note', 'Note'),
        ('line_conclusion', "Conclusion"),], default=False, help="Technical field for UX purpose.")
    #ACS: in doo15 warning and danger can be removed. After checkinging need
    result_type = fields.Selection([
        ('low', "Low"),
        ('normal', "Normal"),
        ('high', "High"),
        ('positive', "Positive"),
        ('negative', "Negative"),
        ('warning', "Warning"),
        ('danger', "Danger"),
        ], default='normal', string="Result Type", help="Technical field for UI purpose.")
    result_value_type = fields.Selection([
        ('quantitative','Quantitative'),
        ('qualitative','Qualitative'),
    ], string='Result Value Type', default='quantitative')
    sample_type_id = fields.Many2one(related="test_id.sample_type_id", string='Sample Type', store=True, readonly=True)
    ref_sample = fields.Char(string="Référence échantillon")
    patient_id = fields.Many2one('hms.patient', string='Patient')
    date_result = fields.Date(string='Date insertion resultat')
    date_anterieur = fields.Date(string='Date examen antérieur')
    pourcentage = fields.Char(string='%')
    usual_reference_line = fields.One2many('lab.usual.reference', 'critearea_id', string='Ligne de valeur de référence')
    reference_per_age = fields.Boolean('Valeurs de référence par âge')
    #=== Interpreation résultat ===
    interp_si_low = fields.Char("Résultat basse")
    interp_si_normal = fields.Char("Résultat normal")
    interp_not_normal = fields.Char("Résultat anormal")
    interp_si_high = fields.Char("Résultat élevé")
    interp_range_1 = fields.Char("Résultat intervalle 1")
    interp_range_2 = fields.Char("Résultat intervalle 2")
    reference_spec = fields.Char('Valeur de référence spécifique',
                                      help="Valeur pour afficher plusieurs interprétions")
    reference_spec_male = fields.Char('Valeur de référence spécifique (Homme)', help="Valeur pour afficher plusieurs interprétions")
    reference_spec_female = fields.Char('Valeur de référence spécifique (Femme)',
                                      help="Valeur pour afficher plusieurs interprétions")
    advice_low = fields.Char("Recommandation seuil basse")
    advice_high = fields.Char("Recommandation seuil élevé")
    section_warning = fields.Boolean("Présence anomalie")

    @api.onchange('normal_range_male')
    def onchange_normal_range_male(self):
        if self.normal_range_male and not self.normal_range_female:
            self.normal_range_female = self.normal_range_male

    @api.onchange('result')
    def onchange_result(self):
        if self.result:
            self.date_result = date.today()
            if self.code == 'BLOOD':
                self.patient_lab_id.check_print_card = True
                data = str(self.patient_lab_id.date_analysis.strftime('%d/%m/%Y')) + ' n° ' + str(self.request_id.name)
                if not self.patient_id.first_determination:
                    self.patient_id.first_determination = data
                elif not self.patient_id.second_determination and self.patient_id.first_determination != data:
                    self.patient_id.second_determination = str(self.patient_lab_id.date_analysis.strftime('%d/%m/%Y')) + ' n° ' + str(self.request_id.name)
                else:
                    pass

        if self.result and self.result_value_type=='quantitative':
            fraction = self.result.find("/")
            if fraction >=0:
                if self.normal_range == self.result:
                   # self.result_type = 'normal'
                    self.remark = self.interp_si_normal
                    indice = self.remark.find('*')
                    if indice >=0:
                        self.result_type = 'warning'
                    else:
                        self.result_type = 'normal'

                else:
                    #self.result_type = 'danger'
                    self.remark = self.interp_not_normal
                    indice = self.remark.find('*')
                    if indice >= 0:
                        self.result_type = 'warning'
                    else:
                        self.result_type = 'normal'
            else:
                if self.result and self.result_value_type=='quantitative' and self.normal_range and not self.reference_spec:
                    try:
                        available0perators = {
                            '-': 'INTERVALLE',
                            '<': 'INFERIEUR',
                            '≤': 'INF_OU_EGUAL',
                            '⩽': 'INF_OU_EGUAL',
                            '>': 'SUPERIEUR',
                            '≥': 'SUP_OU_EGUAL',
                            '⩾': 'SUP_OU_EGUAL',
                        }
                        usedOperator = ''
                        usedOperatorSymbol = ''
                        start = end = 0
                        bornes = []
                        result = float(self.result)
                        for key, value in available0perators.items():
                            if key in self.normal_range:
                                usedOperatorSymbol = key
                                usedOperator = value
                                bornes = self.normal_range.split(usedOperatorSymbol)

                        if len(bornes) > 1:
                            print(bornes)
                            if usedOperator == 'INTERVALLE':
                                start = float(bornes[0].strip().replace(',', '.'))
                                end = float(bornes[1].strip().replace(',', '.'))
                                if result < start:
                                    #self.result_type = 'low'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result == start:
                                    self.remark = self.advice_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result == end:
                                    self.remark = self.advice_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result > start and result < end:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_range_1
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result > end:
                                    #self.result_type = 'high'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            elif usedOperator == 'INFERIEUR':
                                start = float(bornes[1].strip().replace(',', '.'))
                                # if result == start:
                                #     #self.result_type = 'warning'
                                #     self.remark = self.interp_si_doute
                                #     indice = self.remark.find('*')
                                #     if indice >= 0:
                                #         self.result_type = 'warning'
                                #     else:
                                #         self.result_type = 'normal'
                                if result >= start:
                                    #self.result_type = 'high'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result < start:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            elif usedOperator == 'INF_OU_EGUAL':
                                start = float(bornes[1].strip().replace(',', '.'))
                                if result < start or result == start:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result > start:
                                    #self.result_type = 'high'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            elif usedOperator == 'SUPERIEUR':
                                end = float(bornes[1].strip().replace(',', '.'))
                                if result > end:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                # if result == end:
                                #     #self.result_type = 'warning'
                                #     self.remark = self.interp_si_doute
                                #     indice = self.remark.find('*')
                                #     if indice >= 0:
                                #         self.result_type = 'warning'
                                #     else:
                                #         self.result_type = 'normal'
                                if result < end or result == end:
                                    #self.result_type = 'low'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            elif usedOperator == 'SUP_OU_EGUAL':
                                end = float(bornes[1].strip().replace(',', '.'))
                                if result < end:
                                    #self.result_type = 'low'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                if result == end or result > end:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            else:
                                pass
                    except:
                        pass

                if self.result and self.result_value_type=='quantitative'and self.reference_spec:
                    try:
                        split_value = self.reference_spec.split('%')
                        low_range = high_range = doute1 = 0
                        result = float(self.result)
                        if len(split_value) == 2:
                            low_range = float(split_value[0])
                            high_range = float(split_value[1])
                        elif len(split_value) == 3:
                            low_range = float(split_value[0])
                            doute1 = float(split_value[1])
                            high_range = float(split_value[2])

                        if low_range or high_range:
                            if doute1 !=0:
                                if result < low_range:
                                    #self.result_type = 'danger'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                elif result > high_range:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                elif result > low_range and result <= doute1:
                                    #self.result_type = 'warning'
                                    self.remark = self.interp_range_1
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                elif result > doute1 and result <= high_range:
                                    #self.result_type = 'warning'
                                    self.remark = self.interp_range_2
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                            else:
                                if result < low_range:
                                    #self.result_type = 'normal'
                                    self.remark = self.interp_si_low
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                elif result > high_range:
                                    #self.result_type = 'high'
                                    self.remark = self.interp_si_high
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                                elif result >= low_range and result <= high_range:
                                    #self.result_type = 'warning'
                                    self.remark = self.interp_range_1
                                    indice = self.remark.find('*')
                                    if indice >= 0:
                                        self.result_type = 'warning'
                                    else:
                                        self.result_type = 'normal'
                    except:
                        pass

                # split_value = self.normal_range.split('-')
                # low_range = high_range = 0
                # result = float(self.result)
                # if len(split_value)==2:
                #     low_range = float(split_value[0])
                #     high_range = float(split_value[1])
                # elif len(split_value)==2:
                #     low_range = float(split_value[0])
                #     high_range = float(split_value[0])

                # if low_range or high_range:
                #     if result < low_range:
                #         self.result_type = 'low'
                #     elif result > high_range:
                #         self.result_type = 'high'
                #     elif result > low_range and result < high_range:
                #         self.result_type = 'normal'
                #     elif result==low_range or result==high_range:
                #         self.result_type = 'warning'
        else:
            pass



class PatientLabSample(models.Model):
    _name = "acs.patient.laboratory.sample"
    _description = "Patient Laboratory Sample"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'acs.hms.mixin', 'acs.qrcode.mixin']
    _order = 'date desc, id desc'

    STATES = {'cancel': [('readonly', True)], 'examine': [('readonly', True)], 'collect': [('readonly', True)]}

    def _picking_status(self):
        for rec in self:
            picking_count = self.env['stock.picking'].search_count([('origin','=', rec.name)])
            picking_done = self.env['stock.picking'].search_count([('origin','=', rec.name),('state','=','done')])
            rec.picking_status = str(picking_done) + '/' + str(picking_count)

    name = fields.Char(string='Name', help="Sample Name", readonly=True,copy=False, index=True)
    patient_id = fields.Many2one('hms.patient', string='Patient', required=True, tracking=True)
    user_id = fields.Many2one('res.users',string='User', default=lambda self: self.env.user, states=STATES, tracking=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, states=STATES, tracking=True)
    request_id = fields.Many2one('acs.laboratory.request', string='Lab Request', ondelete='restrict', required=True, states=STATES, tracking=True)
    company_id = fields.Many2one('res.company', ondelete='restrict',
        string='Company',default=lambda self: self.env.user.company_id.id, states=STATES, tracking=True)
    state = fields.Selection([
        ('draft','Draft'),
        ('collect', 'Collected'),
        ('examine', 'Examined'),
        ('cancel','Cancel'),
    ], string='State',readonly=True, default='draft', tracking=True)
    sample_type_id = fields.Many2one('acs.laboratory.sample.type', string='Sample Type', required=True, states=STATES, tracking=True)
    container_name = fields.Char(string='Sample Container Code', help="If using preprinted sample tube/slide/box no can be updated here.", copy=False, index=True)

    notes = fields.Text(string='Notes', states=STATES, tracking=True)

    #Just to make object selectable in selction field this is required: Waiting Screen
    acs_show_in_wc = fields.Boolean(default=True)

    #=== CONSOMMABLE====
    consumable_line_ids = fields.One2many('hms.consumable.line', 'lab_sample_id', string='Consumable Line', states=STATES, tracking=True)
    collection_center_id = fields.Many2one('acs.laboratory', string='Centre de prélèvement', states=STATES, tracking=True)
    # Harnetprod
    health_service_id = fields.Many2one('acs.health_service', string='Service santé', readonly=True)
    liste_analyte = fields.Char("Analytes")
    file_patient = fields.Char(string="Ticket patient", readonly=True)
    external_collect = fields.Boolean(string="Prélèvement externe" , default= False)

    picking_status = fields.Char(compute='_picking_status', string='# Nombre de BL fait')
    # department_id = fields.Many2one('hr.department', ondelete='restrict', string='Unité', tracking=True)
    department_id = fields.Many2one(
        'hr.department',
        string='Département',
        ondelete='restrict',
        tracking=True
    )
    # allowed_department_ids = fields.Many2many(
    #     'hr.department',
    #     string='Départements autorisés',
    #     related='user_id.department_ids',
    #     readonly=True
    # )

    _sql_constraints = [
        ('name_company_uniq', 'unique (name,company_id)', 'Sample Name must be unique per company !')
    ]

    @api.model
    def create(self, vals):
        vals['name'] = self.env['ir.sequence'].next_by_code('acs.patient.laboratory.sample')
        return super(PatientLabSample, self).create(vals)

    def unlink(self):
        for rec in self:
            if rec.state not in ['draft']:
                raise UserError(_("Record can be delete only in Draft state."))
        return super(PatientLabSample, self).unlink()

    @api.onchange('request_id')
    def onchange_request_id(self):
        if self.request_id:
            self.patient_id = self.request_id.patient_id.id

    def action_collect(self):
        _logger.info("Starting action_collect . . . %s" , self.department_id.id)
        self.consume_lab_material()
        self.state = 'collect'

    def action_examine(self):
        self.state = 'examine'

    def action_cancel(self):
        self.state = 'cancel'

    # injecter les départements autorisés dans le context
    # def action_open_sample(self):
    #     user = self.env.user
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': 'Lab Sample',
    #         'res_model': 'acs.patient.laboratory.sample',
    #         'view_mode': 'form',
    #         'context': {
    #             'allowed_department_ids': user.department_ids.ids
    #             if hasattr(user, 'department_ids') else [],
    #         }
    #     }


    # def consume_lab_material(self):
    #     for rec in self:
    #         if not rec.company_id.laboratory_usage_location:
    #             raise UserError(
    #                 _('Please define a location where the consumables will be used during the Laboratory test in company.'))
    #         if not rec.collection_center_id.partner_id.dest_location_id:
    #             raise UserError(_('Please define a Laboratory location from where the consumables will be taken.'))

    #         dest_location_id = rec.company_id.laboratory_usage_location.id
    #         source_location_id = rec.collection_center_id.partner_id.dest_location_id.id
    #         for line in rec.consumable_line_ids:
    #             if not line.lot_id:
    #                 self.consume_material(source_location_id, dest_location_id,
    #                                             {
    #                                                 'product': line.product_id,
    #                                                 'qty': line.qty,
    #                                             })
    #             else:
    #                 self.consume_material(source_location_id, dest_location_id,
    #                                             {
    #                                                 'product': line.product_id,
    #                                                 'qty': line.qty,
    #                                                 'lot_id':line.lot_id,
    #                                             })

    #=== SORTIE DE STOCK
    def consume_lab_material(self):
        self.ensure_one()

        unprocessed_lines = self.consumable_line_ids.filtered(lambda l: not l.move_id)
        if not unprocessed_lines:
            raise UserError(_("Aucun nouveau produit consommable pour créer un bon de livraison."))

        # if not self.department_id.source_location_id:
        #     raise UserError(_("Veuillez définir l'emplacement d'origine pour le département."))
    
        # Destination
        dest_location = self.company_id.hospitalization_usage_location
        if not dest_location:
            raise UserError(_("La société n'a pas d'emplacement de destination pour l'hospitalization."))

        # source_location_id = self.department_id.source_location_id.id
        # Source
        _logger.info("---/-/-Department: %s", self.department_id.name if self.department_id else "No Department")
        _logger.info("---/-/-Department ID: %s", self.department_id.id if self.department_id else "No Department ID")
        _logger.info("---/-/-Department source location: %s", self.department_id.source_location_id.name if self.department_id and self.department_id.source_location_id else "No Department Source Location")
        
        source_location = self.department_id.source_location_id
        _logger.info("---/--/-Source Location: %s, Destination Location: %s", source_location.name if source_location else "No Source Location", dest_location.name)
        if not source_location:
            raise UserError(_("Le département n'a pas d'emplacement source configuré."))

        _logger.info("---//-Source Location Company: %s, Self Company : %s", source_location.company_id.name if source_location.company_id else "No Company", self.company_id.name if self.company_id else "No Company")
        if source_location.company_id and source_location.company_id != self.company_id:
            _logger.info("Source location company: %s, Sample company: %s", source_location.company_id.name, self.company_id.name)
            raise UserError(_("L'emplacement source appartient à une autre société."))
        
        _logger.info("---//-Destination Location Company: %s, Self Company : %s", dest_location.company_id.name if dest_location.company_id else "No Company", self.company_id.name if self.company_id else "No Company")
        if dest_location.company_id and dest_location.company_id != self.company_id:
            raise UserError(_("L'emplacement destination appartient à une autre société."))

        # Création du picking
        move_lines = []
        insufficient_products = []
        for line in unprocessed_lines:
            uom_id = line.product_uom.id if line.product_uom else line.product_id.uom_id.id
            available_qty = line.product_id.with_context(
                location=source_location.id
            ).free_qty

            if available_qty < line.qty:
                _logger.warning("Stock insuffisant pour le produit %s: Disponible %s, Demandé %s",
                    line.product_id.display_name, available_qty, line.qty)
                insufficient_products.append(
                    "%s %s (%s dispo)\n" % (
                        int(line.qty),
                        line.product_id.display_name,
                        int(available_qty)
                    )
                )

                
            move_lines.append((0, 0, {
                'name': line.product_id.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty,
                'product_uom': uom_id,
                'location_id': source_location.id,
                'location_dest_id': dest_location.id,
            }))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            #  si on a plusieurs entrepôts
            #  ('warehouse_id', '=', self.warehouse_id.id),
            ('company_id', '=', self.company_id.id),
        ], limit=1)

        if not picking_type:
            raise UserError(_("Aucun type de picking sortant trouvé pour cette société."))
        
        if insufficient_products:
            raise UserError(_(
                "Stock insuffisant pour :\n\n%s"
            ) % "\n".join(insufficient_products))
            
        picking_vals = {
            'partner_id': self.patient_id.partner_id.id,
            'picking_type_id': picking_type.id,
            'location_id': source_location.id,
            'location_dest_id': dest_location.id,
            'scheduled_date': datetime.now(),
            'origin': self.name,
            'move_ids_without_package': move_lines,
            'department_id': self.department_id.id if self.department_id else False,
            'company_id': self.company_id.id,
        }

        picking = self.env['stock.picking'].create(picking_vals)
        picking.action_confirm()
        picking.action_assign()

        for line in unprocessed_lines:
            move = self.env['stock.move'].search([
                ('picking_id','=',picking.id),
                ('product_id', '=', line.product_id.id)], limit = 1 )
            _logger.info("Found move for product %s: %s", line.product_id.name, move)
            
            if not move:
                continue
            
            move_line = self.env['stock.move.line'].search([
                ('move_id', '=', move.id),
            ], limit=1)

            if not move_line:
                move_line = self.env['stock.move.line'].create({
                    'move_id': move.id,
                    'picking_id': picking.id,
                    'product_id': move.product_id.id,
                    'product_uom_id': move.product_uom.id,
                    'location_id': move.location_id.id,
                    'location_dest_id': move.location_dest_id.id,
                    'qty_done': line.qty,
                })
            else:
                move_line.qty_done = line.qty
            
            if move.product_id.tracking != 'none':
                lot = self.env['stock.production.lot'].create({
                    'name': f'LOT-{self.name}-{line.id}',
                    'product_id': move.product_id.id,
                    'company_id': self.company_id.id,
                })
                move_line.lot_id = lot.id

            _logger.info("finalizing action_collect ...")
            line.move_id = move.id
            
        _logger.info("Before validation: state=%s", picking.state)
        try:
            _logger.info("Validating picking...")
            
            res = picking.button_validate()
            if isinstance(res, dict):
                # Wizard returned → process it automatically
                wizard = self.env[res['res_model']].browse(res['res_id'])
                wizard.process()

            # _logger.info("Total qty_done: %s", sum(picking.move_line_ids.mapped('qty_done')))
            _logger.info("Picking validated successfully. Current state: %s", picking.state)
        except Exception as e:
            _logger.error("VALIDATION ERROR: %s", str(e))
            raise

    def show_picking(self):
        for rec in self:
            res = self.env.ref('stock.action_picking_tree_all')
            res = res.read()[0]
            res['domain'] = str([('origin','=',rec.name)])
        return res

    def list_analyte(self):
        for rec in self:
            if not rec.company_id.laboratory_usage_location:
                raise UserError(
                    _('Please define a location where the consumables will be used during the Laboratory test in company.'))
            if not rec.collection_center_id.partner_id.dest_location_id:
                raise UserError(_('Please define a Laboratory location from where the consumables will be taken.'))

            dest_location_id = rec.company_id.laboratory_usage_location.id
            source_location_id = rec.collection_center_id.partner_id.dest_location_id.id
            for line in rec.consumable_line_ids:
                self.consume_material(source_location_id, dest_location_id,
                                            {
                                                'product': line.product_id,
                                                'qty': line.qty,
                                            })

    def action_print_sample(self):
        active_ids = self.env.context.get("active_ids", [])
        lab_samples = self.env['acs.patient.laboratory.sample'].browse(active_ids)
        for lab in lab_samples:
                return lab.env.ref('acs_laboratory.acs_lab_sample_report').report_action(self)

class LaboratoryGroupLine(models.Model):
    _name = "laboratory.group.line"
    _description = "Laboratory Group Line"

    group_id = fields.Many2one('laboratory.group', ondelete='restrict', string='Laboratory Group')
    test_id = fields.Many2one('acs.lab.test',string='Test', ondelete='cascade', required=True)
    acs_tat = fields.Char(related='test_id.acs_tat', string='Turnaround Time', readonly=True)
    instruction = fields.Char(string='Special Instructions')
    sale_price = fields.Float(string='Sale Price')
    test_type = fields.Selection([
        ('pathology','Pathology'),
        ('radiology','Radiology'),
    ], string='Test Type', default='pathology')

    @api.onchange('test_id')
    def onchange_test(self):
        if self.test_id:
            self.sale_price = self.test_id.product_id.lst_price


class LaboratoryGroup(models.Model):
    _name = "laboratory.group"
    _description = "Laboratory Group"

    name = fields.Char(string='Group Name', required=True)
    line_ids = fields.One2many('laboratory.group.line', 'group_id', string='Medicament line')
    test_type = fields.Selection([
        ('pathology','Pathology'),
        ('radiology','Radiology'),
    ], string='Test Type', default='pathology')


class LabSampleType(models.Model):
    _name = "acs.laboratory.sample.type"
    _description = "Laboratory Sample Type"
    _order = 'sequence asc'

    name = fields.Char(string='Name', required=True)
    sequence = fields.Integer("Sequence", default="100")
    description = fields.Text("Description")

    # product_id = fields.Many2one('product.product', string='Product')
    product_ids = fields.Many2many(
        'product.product',        # modèle cible
        string='Products'         # nom du champ affiché
    )

class Department(models.Model):
    _name = 'hr.department'
    _inherit = 'hr.department'
    source_location_id = fields.Many2one('stock.location', string='Source Location')

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: