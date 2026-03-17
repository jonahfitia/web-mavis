from odoo import models, fields

class MobileDevice(models.Model):
    _name = 'mobile.device'
    _description = 'Mobile Device registered for push notifications'

    user_id = fields.Many2one('res.users', string='User', required=True)
    fcm_token = fields.Char('FCM Token', required=True)
    device_id = fields.Char('Device Unique ID', required=True)
    device_name = fields.Char('Device Name')
    os = fields.Char('Operating System')
    logged_in = fields.Boolean('Logged In', default=True)
    last_seen = fields.Datetime('Last Seen', default=fields.Datetime.now)
    create_date = fields.Datetime(readonly=True)
    write_date = fields.Datetime(readonly=True)

    # def init(self):
    #     # Ajoute les droits d'accès automatiquement à l'installation
    #     self.env.ref('base.group_user').write({
    #         'implied_ids': [(4, self.env.ref('base.group_user').id)]
    #     })
    #     # Ou plus simplement : on donne les droits à tout le monde en lecture/écriture
    #     self.env['ir.model.access'].create({
    #         'name': 'access_mobile_device_full',
    #         'model_id': self.env['ir.model']._get('mobile.device').id,
    #         'perm_read': True,
    #         'perm_write': True,
    #         'perm_create': True,
    #         'perm_unlink': True,
    #     })
