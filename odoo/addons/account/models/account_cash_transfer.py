from odoo import _, models, fields, api
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class AccountCashTransfer(models.Model):
    _name = 'account.cash.transfer'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Cash Transfer'

    name = fields.Char(string='Transfer Name', required=True, copy=False, readonly=True, default='/', tracking=True)
    
    source_cashier = fields.Many2one(
        'res.users',
        string="Caissier",
        default=lambda self: self.env.user,
        readonly=True,
        required=True,
    )
    source_cash_register = fields.Many2one(
        'account.bank.statement',
        string="Numéro de Caisse",
        domain="[('date_done', '=', False), ('user_id', '=', uid)]",
        readonly=True,
    )
    source_total_amount = fields.Monetary(string="Montant Total", readonly=True, currency_field='currency_id')
    source_date_ending = fields.Datetime(string="Date/Heure de clôture", readonly=True)
    
    destination_cash_register = fields.Many2one(
        'account.journal',
        string="Caisse",
        domain="[('type', '=', 'cash'), ('id', '!=', source_cash_register)]",
        ondelete='set null'
    )
    destination_cashbox_id = fields.Many2one(
        'account.bank.statement.cashbox',
        string="Destination Cashbox",
    )
    date_reception = fields.Datetime(string="Reception Date")
    destination_total_amount = fields.Monetary(string="Total Amount Received")

    # The `state` field in the `AccountCashTransfer` model is a selection field that allows the user
    # to choose between two options: 'posted' and 'done'.
    state = fields.Selection([('posted', 'Processing'), ('done', 'Validated')], default='posted',tracking=True)
    
    # destination_cashier = fields.Many2one('res.users', string="Destination Cashier")
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    cashbox_start_id = fields.Many2one('account.bank.statement.cashbox', string="Starting Cashbox")
    cashbox_end_id = fields.Many2one('account.bank.statement.cashbox', string="Ending Cashbox")
    
    show_mismatch_alert = fields.Boolean(
        compute='_compute_show_mismatch_alert',
        string="Show Mismatch Alert"
    )

    @api.model
    def create(self, vals):
        if vals.get('name', '/') == '/':
            vals['name'] = self.env['ir.sequence'].next_by_code('account.cash.transfer') or '/'
        return super(AccountCashTransfer, self).create(vals)

    # mila averina nouveau aloha ilay statement
    # inserer-na ilay ligne 
    # averina en cours de traitement ilay statement 
    # raikitra fa validé avy eo
    def action_validate(self):
        for rec in self:
            if not rec.destination_cash_register:
                raise UserError(_("You must choose a Destination Cash Register before validating."))
            
            if not rec.destination_total_amount:
                raise UserError(_("Please enter the Total Amount Received."))
            
            if rec.source_total_amount != rec.destination_total_amount:
                raise UserError(_("Warning: Source and Destination amounts are different!"))
            
            origin_statement = self.env['account.bank.statement'].search([
                ('id', '=', rec.source_cash_register.id),
                ('state', '!=', 'confirm')
            ], limit=1)
            
            if not origin_statement:
                raise UserError(_("No open bank statement found for source cash register: %s") % rec.source_cash_register.name)

            # # MANIPULATION DE L'ORIGIN STATEMENT (account_bank_statement)
            if origin_statement.state != 'open':
                origin_statement.write({'state': 'open'})
                
            self.env['account.bank.statement.line'].create({
                'statement_id': origin_statement.id,
                'payment_ref': f"{rec.name} ADC {rec.source_cash_register.name}",
                'amount': -rec.destination_total_amount,
            })
            
            origin_statement.write({'state': 'confirm'})

            # # MANIPULATION DE DESTINATION STATEMENT (account_bank_statement)
            # Rechercher ou créer le relevé de caisse de destination
            dest_statement = self.env['account.bank.statement'].search([
                ('journal_id', '=', rec.destination_cash_register.id),
                ('state', '=', 'open')
            ], limit=1)

            if not dest_statement:
                dest_statement = self.env['account.bank.statement'].create({
                    'journal_id': rec.destination_cash_register.id,
                    'name': f"ADC {fields.Date.today()}",
                    'date': fields.Date.today(),
                })
                # Si nouveau statement : on synchronise avec balance_end
                dest_statement.balance_end_real = dest_statement.balance_end

            # # Création ligne destination : montant positif
            self.env['account.bank.statement.line'].create({
                'statement_id': dest_statement.id,
                'payment_ref': f"{rec.name} ADC {rec.source_cash_register.name}",
                'amount': rec.destination_total_amount,
            })
            
            # Ajout montant à balance_end_real
            dest_statement.balance_end_real += rec.destination_total_amount
            
            rec.source_date_ending = fields.Datetime.now()
            rec.state = 'done'

    def action_reset_draft(self):
        for rec in self:
            # 1. Récupérer le dernier statement lié au source_cash_register
            origin_statement = self.env['account.bank.statement'].search([
                ('id', '=', rec.source_cash_register.id)
            ], order="date desc, id desc", limit=1)

            # _logger.info(" account bank statement id origin : %s", rec.source_cash_register.id)
            # _logger.info(" ----------------- ORIGIN STATEMENT -------------- ")
            # _logger.info(" caisse source statement : %s", origin_statement)
            
            if origin_statement:
                # 2. Revenir à l’état "posted"
                origin_statement.write({'state': 'posted'})

                # 3. Supprimer la ligne qui a été ajoutée avec ce transfert (par son libellé)
                line_to_remove = self.env['account.bank.statement.line'].search([
                    ('statement_id', '=', origin_statement.id),
                    ('payment_ref', '=', f"{rec.name} ADC {rec.source_cash_register.name}"),
                    ('amount', '=', -rec.destination_total_amount)
                ], limit=1)

                if line_to_remove:
                    line_to_remove.unlink()
                    
            # --- DESTINATION CASH REGISTER ---
            dest_statement = self.env['account.bank.statement'].search([
                ('journal_id', '=', rec.destination_cash_register.id),
                ('state', '=', 'open')
            ], order="date desc, id desc", limit=1)

            if dest_statement:
                dest_line = self.env['account.bank.statement.line'].search([
                    ('statement_id', '=', dest_statement.id),
                    ('payment_ref', '=', f"{rec.name} ADC {rec.source_cash_register.name}"),
                    ('amount', '=', rec.destination_total_amount)
                ], limit=1)

                if dest_line:
                    dest_line.unlink()

                    # S'il ne reste aucune autre ligne, on supprime le statement aussi
                    remaining_lines = self.env['account.bank.statement.line'].search_count([
                        ('statement_id', '=', dest_statement.id)
                    ])
                    if remaining_lines == 0:
                        dest_statement.unlink()

            # 4. Revenir à l'état "posted" pour le modèle principal
            rec.state = 'posted'
    
    def open_cashbox_id(self):
        self.ensure_one()
        context = dict(self.env.context or {})

        context.update({
            'statement_id': self.source_cash_register.id,
            'cash_transfer_id': self.id,
            'from_cash_transfer': True,
            'balance': context.get('balance'),
        })

        # if context['balance'] == 'start':
        #     cashbox_id = self.cashbox_start_id.id
        # elif context['balance'] == 'close':
        #     cashbox_id = self.cashbox_end_id.id
        # else:
        cashbox_id = False
        
        return {
            'name': _('Cash Control'),
            'view_mode': 'form',
            'res_model': 'account.bank.statement.cashbox',
            'view_id': self.env.ref('account.view_account_bnk_stmt_cashbox_footer').id,
            'type': 'ir.actions.act_window',
            'res_id': cashbox_id,
            'context': context,
            'target': 'new'
        }
        
    def write(self, vals):
        res = super(AccountCashTransfer, self).write(vals)
        if 'destination_cashbox_id' in vals:
            self._compute_destination_total_amount()
        return res
    
    @api.depends('source_total_amount', 'destination_total_amount')
    def _compute_show_mismatch_alert(self):
        for rec in self:
            rec.show_mismatch_alert = (
                bool(rec.source_total_amount and rec.destination_total_amount) and
                rec.source_total_amount != rec.destination_total_amount
            )
            
    #== POUR IMPRIMER BILLETAGE ==
    def print_start_report_cashbox(self):
        if not self.cashbox_start_id.id:
            raise ValueError(_("Invalid cashbox ID"))

        cashbox = self.env['account.bank.statement.cashbox'].browse(self.cashbox_start_id.id)
        if not cashbox.exists():
            raise ValueError(_("Cashbox record does not exist"))

        return self.env.ref('account.action_report_bank_statement_cashbox').report_action(cashbox)

    def print_end_report_cashbox(self):
        if not self.cashbox_end_id.id:
            raise ValueError(_("Invalid cashbox ID"))
        cashbox = self.env['account.bank.statement.cashbox'].browse(self.cashbox_end_id.id)
        if not cashbox.exists():
            raise ValueError(_("Cashbox record does not exist"))
        return self.env.ref('account.action_report_bank_statement_cashbox').report_action(cashbox)
    