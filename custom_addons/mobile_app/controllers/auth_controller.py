from odoo import http
from odoo.http import request

class AuthController(http.Controller):
    @http.route('/api/check_user_groups', type='json', auth='user', methods=['POST'])
    def check_user_groups(self, **kwargs):
        user = request.env.user
        return {
            'has_access': (
                user.has_group('stock.group_stock_user') or
                user.has_group('sales_team.group_sale_salesman') or
                user.has_group('purchase.group_purchase_user')
            ),
            'message': (
                'Vous n\'avez pas accès aux modules inventaire, vente ou achat.'
                if not (
                    user.has_group('stock.group_stock_user') or
                    user.has_group('sales_team.group_sale_salesman') or
                    user.has_group('purchase.group_purchase_user')
                )
                else 'Accès autorisé.'
            )
        }