from odoo import http, fields
from odoo.http import request
import logging
import json



# from collections import defaultdict
_logger = logging.getLogger(__name__)
import functools


def restrict_to_inventory_sale_purchase(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        user = request.env.user
        # Vérifier si l'utilisateur a accès à l'un des modules requis
        has_access = (
            user.has_group('stock.group_stock_user') or
            user.has_group('sales_team.group_sale_salesman') or
            user.has_group('purchase.group_purchase_user')
        )
        if not has_access:
            return {
                'error': 'Access Denied',
                'message': 'Vous n\'avez pas accès aux modules inventaire, vente ou achat.'
            }
        return func(*args, **kwargs)
    return wrapper


class PickingAPI(http.Controller):

    def _get_available_qty(self, product, location=None):
        domain = [('product_id', '=', product.id)]
        if location:
            domain.append(('location_id', 'child_of', location.id))
        quants = request.env['stock.quant'].sudo().search_read(domain, ['quantity', 'reserved_quantity'])   # type: ignore

        reserved_qty = sum(
            ml.qty_done for ml in request.env['stock.move.line'].sudo().search([   # type: ignore
                ('product_id', '=', product.id),
                ('state', 'in', ['assigned', 'partially_available']),
                ('location_id', '=', location.id) if location else ('location_id', '!=', False)
            ])
        )

        qty = sum(q['quantity'] for q in quants) - reserved_qty
        return max(qty, 0)
    
    def _get_product_stock(self, product, location=None):
        """Retourne stock disponible et manquant pour un produit."""
        env = request.env

        if not product or not product.id:
            return {
                'stock_disponible': 0,
                'stock_manquant': 0,
                'stock_physique': 0,
                'reserved': 0,
            }

        # --- 1. Stock physique (quantités dans stock.quant)
        domain = [('product_id', '=', product.id)]
        if location:
            domain.append(('location_id', 'child_of', location.id))

        quants = env['stock.quant'].sudo().search_read(domain, ['quantity'])   # type: ignore
        qty_physical = sum(q['quantity'] for q in quants)

        # --- 2. Quantité réservée (dans les moves en cours)
        reserved_qty = sum(
            ml.product_uom_qty for ml in env['stock.move.line'].sudo().search([   # type: ignore
                ('product_id', '=', product.id),
                ('state', 'in', ['assigned', 'partially_available']),
                ('location_id', '=', location.id) if location else ('location_id', '!=', False)
            ])
        )

        # --- 3. Stock disponible
        stock_disponible = max(qty_physical - reserved_qty, 0)

        # --- 4. Stock manquant (si la demande dépasse le disponible)
        total_demand = sum(
            move.product_uom_qty for move in env['stock.move'].sudo().search([   # type: ignore
                ('product_id', '=', product.id),
                ('state', 'in', ['confirmed', 'assigned', 'partially_available'])
            ])
        )
        stock_manquant = max(total_demand - stock_disponible, 0)
        checks = {
            'product_id': product.id,
            'stock_disponible': stock_disponible,
            'stock_manquant': stock_manquant,
            'stock_physique': qty_physical,
            'reserved': reserved_qty,
        }

        _logger.info("Vérification du stock ***** %s", checks)
        return stock_disponible



#_TAKING SALE MOVES#     
    @http.route('/api/stock_move_sale_new', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def get_stock_move_sale_new(self, **kwargs):        
        stock_picking = request.env['stock.picking'].sudo().search([('state', '=', 'assigned'),('name','ilike', '/OUT/')])   # type: ignore
        moves = request.env['stock.move'].sudo().search([('state', 'in', ['assigned', 'partially_available','confirmed']),('reference', 'ilike', '/OUT/'),('picking_id', 'in', stock_picking.ids), ('product_id.type', '=', 'product')])   # type: ignore
        check_moves = []
        for move in moves:
            self._get_product_stock(move.product_id)
            check_moves.append({
                'id': move.id,
                'name': move.name,
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'location_id': move.location_id.complete_name if move.location_id else '',
                'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                'state': move.state,
                'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                'stock_disponible': (
                    self._get_product_stock(move.product_id, move.location_id)
                )
            })

        move_lines = request.env['stock.move.line'].sudo().search([('move_id', 'in', moves.ids)])   # type: ignore
        lot = request.env['stock.production.lot'].sudo().search([('product_id', 'in', moves.mapped('product_id').ids)])   # type: ignore
        result = {}
        result_picking = []
        picking_list = []
        if stock_picking:
            for picking in stock_picking:
                # filtrer les move_lines de ce picking
                picking_move_lines = [line for line in move_lines if line.picking_id.id == picking.id]
                picking_moves = [move for move in moves if move.picking_id.id == picking.id]

                # récupérer les messages liés à ce picking
                picking_messages = request.env['mail.message'].sudo().search([   # type: ignore
                    ('model', '=', 'stock.picking'),
                    ('res_id', '=', picking.id),
                    ('message_type', '=', 'comment')
                ], order='date desc')

                messages_data = [{
                    'id': msg.id,
                    'author': msg.author_id.name if msg.author_id else '',
                    'date': msg.date,
                    'body': msg.body,
                } for msg in picking_messages]

                # si pas de move_lines ET pas de moves → on passe au suivant
                if not picking_move_lines and not picking_moves:
                    continue  

                picking_list.append({
                    'id': picking.id,
                    'name': picking.name,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_done': picking.date_done,
                    'move_lines': [{
                        'id': line.id,
                        'product_name': line.product_id.name,
                        'product_uom_qty': line.product_uom_qty,
                        'qty_done': line.qty_done,
                        'state': line.state,
                        'package_id': line.package_id.name if line.package_id else '',
                    } for line in picking_move_lines],  # ton code existant pour move_lines
                    'messages': messages_data,  # ajout des messages
                })             

                result_picking.append({
                    'id': picking.id,
                    'name': picking.name,
                    'origin': picking.origin,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_deadline': picking.date_deadline,
                    'date_done': picking.date_done,
                    'partner': picking.partner_id.name,                                       
                    'messages': messages_data,  # ajout des messages
                    'moves': [{
                        'id': move.id,
                        'name': move.name,
                        'product_id': move.product_id.id,
                        'product_uom_qty': move.product_uom_qty,
                        'location_id': move.location_id.complete_name if move.location_id else '',
                        'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                        'state': move.state,
                        'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                        'require_lot': move.product_id.product_tmpl_id.tracking != 'none',
                        'stock_disponible': (
                                self._get_product_stock(move.product_id, move.location_id)
                            ),
                        'move_lines': [{
                            'id': move_line.id,
                            'product_id': move_line.product_id.id,
                            'product_uom_qty': move_line.product_uom_qty,
                            'qty_done': move_line.qty_done,
                            'state': move_line.state,
                            'package_id': move_line.package_id.name if move_line.package_id else '',
                            'production_lot': [{
                                'id': lt.id,
                                'name': lt.name,
                                'product_id': lt.product_id.id,
                                'expiration_date': lt.expiration_date,
                            }for lt in lot if lt.product_id.id == move.product_id.id],
                        } for move_line in move_lines if move_line.move_id.id == move.id]
                    } for move in picking_moves]
                })

        result['picking'] = picking_list
        result['result_picking'] = result_picking
        return {'status': 200, 'response': result, 'message': 'Success'}    
    
    
    
#_TAKING PURCHASE MOVES# 
    @http.route('/api/stock_move_purchase_new', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def get_stock_move_purchase_new(self, **kwargs):        
        stock_picking = request.env['stock.picking'].sudo().search([('state', '=', 'assigned'),('name','ilike', '/IN/')])       # type: ignore   
        # ('product_id.type', '=', 'product') Article stockable uniquement
        moves = request.env['stock.move'].sudo().search([('state', 'in', ['assigned', 'partially_available','confirmed']),('reference', 'ilike', '/IN/'),('picking_id', 'in', stock_picking.ids), ('product_id.type', '=', 'product')])   # type: ignore
        check_moves = []
        for move in moves:
            self._get_product_stock(move.product_id)
            check_moves.append({
                'id': move.id,
                'name': move.name,
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'location_id': move.location_id.complete_name if move.location_id else '',
                'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                'state': move.state,
                'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                'stock_disponible': (
                    self._get_product_stock(move.product_id, move.location_id)
                )
            })

        move_lines = request.env['stock.move.line'].sudo().search([('move_id', 'in', moves.ids)])   # type: ignore
        lot = request.env['stock.production.lot'].sudo().search([('product_id', 'in', moves.mapped('product_id').ids)])   # type: ignore
        result = {}
        result_picking = []
        picking_list = []
        if stock_picking:
            for picking in stock_picking:
                # filtrer les move_lines de ce picking
                picking_move_lines = [line for line in move_lines if line.picking_id.id == picking.id]
                picking_moves = [move for move in moves if move.picking_id.id == picking.id]

                # récupérer les messages liés à ce picking
                picking_messages = request.env['mail.message'].sudo().search([   # type: ignore
                    ('model', '=', 'stock.picking'),
                    ('res_id', '=', picking.id),
                    ('message_type', '=', 'comment')
                ], order='date desc')

                messages_data = [{
                    'id': msg.id,
                    'author': msg.author_id.name if msg.author_id else '',
                    'date': msg.date,
                    'body': msg.body,
                } for msg in picking_messages]

                # si pas de move_lines ET pas de moves → on passe au suivant
                if not picking_move_lines and not picking_moves:
                    continue  

                picking_list.append({
                    'id': picking.id,
                    'name': picking.name,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_done': picking.date_done,
                    'move_lines': [{
                        'id': line.id,
                        'product_name': line.product_id.name,
                        'product_uom_qty': line.product_uom_qty,
                        'qty_done': line.qty_done,
                        'state': line.state,
                        'package_id': line.package_id.name if line.package_id else '',
                    } for line in picking_move_lines],  # ton code existant pour move_lines
                    'messages': messages_data,  # ajout des messages
                })             

                result_picking.append({
                    'id': picking.id,
                    'name': picking.name,
                    'origin': picking.origin,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_deadline': picking.date_deadline,
                    'date_done': picking.date_done,
                    'partner': picking.partner_id.name,                                       
                    'messages': messages_data,  # ajout des messages
                    'moves': [{
                        'id': move.id,
                        'name': move.name,
                        'product_id': move.product_id.id,
                        'product_uom_qty': move.product_uom_qty,
                        'location_id': move.location_id.complete_name if move.location_id else '',
                        'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                        'state': move.state,
                        'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                        'require_lot': move.product_id.product_tmpl_id.tracking != 'none',
                        'stock_disponible': (
                                self._get_product_stock(move.product_id, move.location_id)
                            ),
                        'move_lines': [{
                            'id': move_line.id,
                            'product_id': move_line.product_id.id,
                            'product_uom_qty': move_line.product_uom_qty,
                            'qty_done': move_line.qty_done,
                            'state': move_line.state,
                            'package_id': move_line.package_id.name if move_line.package_id else '',
                            'production_lot': [{
                                'id': lt.id,
                                'name': lt.name,
                                'product_id': lt.product_id.id,
                                'expiration_date': lt.expiration_date,
                            }for lt in lot if lt.product_id.id == move.product_id.id],
                        } for move_line in move_lines if move_line.move_id.id == move.id]
                    } for move in picking_moves]
                })
    
        result['picking'] = picking_list
        result['result_picking'] = result_picking
        return {'status': 200, 'response': result, 'message': 'Success'}    

   
    
#_TAKING INTERNAL MOVES# 
    @http.route('/api/stock_move_internal_new', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def get_stock_move_internal_new(self, **kwargs):
        # Récupération des pickings internes
        stock_picking = request.env['stock.picking'].sudo().search([   # type: ignore
            ('state', '=', 'assigned'),
            ('name', 'ilike', '/INT/')
        ])

        # Récupération des moves liés
        moves = request.env['stock.move'].sudo().search([   # type: ignore
            ('state', 'in', ['assigned', 'partially_available', 'confirmed']),
            ('reference', 'ilike', '/INT/'),
            ('picking_id', 'in', stock_picking.ids),
            ('product_id.type', '=', 'product')
        ])

        # On vérifie les quantités disponibles
        check_moves = []
        for move in moves:
            self._get_product_stock(move.product_id)  # update stock dispo
            check_moves.append({
                'id': move.id,
                'name': move.name,
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_uom_qty,
                'location_id': move.location_id.complete_name if move.location_id else '',
                'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                'state': move.state,
                'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                'stock_disponible': self._get_product_stock(move.product_id, move.location_id),
            })

        move_lines = request.env['stock.move.line'].sudo().search([('move_id', 'in', moves.ids)])   # type: ignore
        lot = request.env['stock.production.lot'].sudo().search([   # type: ignore
            ('product_id', 'in', moves.mapped('product_id').ids)
        ])

        result = {}
        result_picking = []
        picking_list = []

        if stock_picking:
            for picking in stock_picking:
                # filtrer les move_lines et moves de ce picking
                picking_move_lines = [line for line in move_lines if line.picking_id.id == picking.id]
                picking_moves = [move for move in moves if move.picking_id.id == picking.id]

                # récupérer les messages liés à ce picking
                picking_messages = request.env['mail.message'].sudo().search([   # type: ignore
                    ('model', '=', 'stock.picking'),
                    ('res_id', '=', picking.id),
                    ('message_type', '=', 'comment')
                ], order='date desc')

                messages_data = [{
                    'id': msg.id,
                    'author': msg.author_id.name if msg.author_id else '',
                    'date': msg.date,
                    'body': msg.body,
                } for msg in picking_messages]

                # si pas de move_lines ET pas de moves → on passe au suivant
                if not picking_move_lines and not picking_moves:
                    continue  

                # picking minimal (comme "picking_list")
                picking_list.append({
                    'id': picking.id,
                    'name': picking.name,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_done': picking.date_done,
                    'move_lines': [{
                        'id': line.id,
                        'product_name': line.product_id.name,
                        'product_uom_qty': line.product_uom_qty,
                        'qty_done': line.qty_done,
                        'state': line.state,
                        'package_id': line.package_id.name if line.package_id else '',
                    } for line in picking_move_lines],
                    'messages': messages_data,
                })

                # picking détaillé (comme "result_picking")
                result_picking.append({
                    'id': picking.id,
                    'name': picking.name,
                    'origin': picking.origin,
                    'location_id': picking.location_id.complete_name if picking.location_id else '',
                    'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
                    'state': picking.state,
                    'date_deadline': picking.date_deadline,
                    'date_done': picking.date_done,
                    'partner': picking.partner_id.name,
                    'messages': messages_data,
                    'moves': [{
                        'id': move.id,
                        'name': move.name,
                        'product_id': move.product_id.id,
                        'product_uom_qty': move.product_uom_qty,
                        'location_id': move.location_id.complete_name if move.location_id else '',
                        'location_dest_id': move.location_dest_id.complete_name if move.location_dest_id else '',
                        'state': move.state,
                        'qty_done_online': sum(move.move_line_ids.mapped('qty_done')),
                        'require_lot': move.product_id.product_tmpl_id.tracking != 'none',
                        'stock_disponible': self._get_product_stock(move.product_id, move.location_id),
                        'move_lines': [{
                            'id': move_line.id,
                            'product_id': move_line.product_id.id,
                            'product_uom_qty': move_line.product_uom_qty,
                            'qty_done': move_line.qty_done,
                            'state': move_line.state,
                            'package_id': move_line.package_id.name if move_line.package_id else '',
                            'production_lot': [{
                                'id': lt.id,
                                'name': lt.name,
                                'product_id': lt.product_id.id,
                                'expiration_date': lt.expiration_date,
                            } for lt in lot if lt.product_id.id == move.product_id.id],
                        } for move_line in move_lines if move_line.move_id.id == move.id]
                    } for move in picking_moves]
                })

        result['picking'] = picking_list
        result['result_picking'] = result_picking

        return {'status': 200, 'response': result, 'message': 'Success'}
    

    # @http.route('/api/stock_move_internal', type='json', auth='user', methods=['POST'], csrf=False)
    # @restrict_to_inventory_sale_purchase
    # def get_stock_move_internal(self, **kwargs):
    #     moves = request.env['stock.move'].sudo().search([('state', '=', 'assigned'),('reference', 'ilike', '/INT/')])
    #     moves_lines = request.env['stock.move.line'].sudo().search([('move_id', 'in', moves.ids)])
    #     stock_picking = request.env['stock.picking'].sudo().search([('state', '=', 'assigned'),('name','ilike', '/INT/')])

    #     result = {}
    #     result_picking = []
    #     move_list = []
    #     if stock_picking:
    #         for picking in stock_picking:
    #             picking_move_lines = request.env['stock.move.line'].sudo().search([('picking_id', '=', picking.id)])

    #             result_picking.append({
    #                 'id': picking.id,
    #                 'name': picking.name,
    #                 'location_id': picking.location_id.complete_name if picking.location_id else '',
    #                 'location_dest_id': picking.location_dest_id.complete_name if picking.location_dest_id else '',
    #                 'state': picking.state,
    #                 'date_done': picking.date_done,                    
    #                 'move_lines': [{
    #                     'id': line.id,
    #                     'product_name': line.product_id.name,
    #                     'product_uom_qty': line.product_uom_qty,
    #                     'qty_done': line.qty_done,
    #                     'state': line.state,
    #                     'package_id': line.package_id.name if line.package_id else '',
    #                 } for line in picking_move_lines]
    #             })

    #     for move in moves:
    #         move_line = moves_lines.filtered(lambda line: line.move_id.id == move.id)

    #         move_list.append({
    #             'id': move.id,
    #             'name': move.name,
    #             'partner': move.partner_id.name if move.partner_id else '',
    #             'origin': move.picking_id.location_id.complete_name if move.picking_id.location_id else '',
    #             'destination': move.picking_id.location_dest_id.complete_name if move.picking_id.location_dest_id else '',
    #             'picking_id': move.picking_id.id,
    #             'stock_picking': move.picking_id.name if move.picking_id else '',
    #             'ref': move.reference,
    #             'qty': move.product_qty,
    #             'state': move.state,            
    #             'qty_done_online': move_line.qty_done if move_line else 0,
    #         })
    #     result['picking'] = result_picking
    #     result['moves'] = move_list
    #     return {
    #         'status': 200,
    #         'response': result,
    #         'message': 'Success'
    #     }

     
#_INTERNAL MOVES SYNC# 
    @http.route('/api/stock_internal_transfer_move_sync', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def sync_internal_transfer_moves(self, moves, **kwargs):
        received_moves = moves
        errors = []

        _logger.info("Données de synchronisation des mouvements de stock reçues (API: /api/stock_internal_transfer_move_sync):")
        _logger.info("stock_internal_transfer_move_sync_")
        _logger.info(f"MOVES: {received_moves}")
        _logger.info("stock_internal_transfer_move_sync_")

        if not received_moves:
            _logger.info("Aucun mouvement de stock reçu pour la synchronisation.")
            return {
                'status': 200,
                'response': "Aucun mouvement reçu à synchroniser.",
                'message': 'Succès (aucune modification de la base de données).'
            }
        for move_data in received_moves:
            stock_move = request.env['stock.move'].sudo().search([('id', '=', move_data.get('id'))], limit=1) # type: ignore
            stock_move_line = request.env['stock.move.line'].sudo().search([('move_id', '=', move_data.get('id')),('picking_id','=',stock_move.picking_id.id)], limit=1) # type: ignore
            if not stock_move:
                msg = f"Mouvement de stock avec ID {move_data.get('id')} non trouvé dans la base de données."
                _logger.info(msg)
                errors.append(msg)  
                continue
            try:
                stock_move_line.write({
                    'qty_done': stock_move_line.qty_done + move_data.get('qty_delivered', stock_move_line.qty_done),
                })
                user = request.env.user
                stock_move.picking_id.message_post(
                    body=f"""
                        <div style="padding:10px; border-left:3px solid #4caf50; background:#f9f9f9; margin:5px 0; border-radius:6px;">
                            <b>{user.name}</b> a livré 
                            <span style="color:#1976d2; font-weight:bold;">{move_data.get('qty_delivered', stock_move_line.qty_done)}</span> unités 
                            du produit <i>{stock_move.product_id.display_name}</i>.
                        </div>
                    """,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note"
                )


                _logger.info(f"Le mouvement de stock ID {move_data.get('id')} a été mis à jour avec succès.")

                _logger.info(f"Le mouvement de stock ID {move_data.get('id')} a été mis à jour avec succès.")
            except Exception as e:
                _logger.error(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")
                errors.append(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")
        if errors:
            return {
                'status': 500,
                'response': "Une erreur s'est produite lors de la synchronisation des mouvements de stock.",
                'message': 'Echec de la synchronisation des mouvements de stock.'
            }
        else:
            return {
                'status': 200,
                'response': "Synchronisation des mouvements de stock reussie.",
                'message': 'Succès (modification de la base de données).',
                'errors': errors if errors else None
            }
                        
    
    
#_SALE MOVES SYNC# 
    @http.route('/api/stock_sale_move_sync', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def sync_stock_sale_moves(self, moves, **kwargs): 
        received_moves = moves
        errors = []

        _logger.info("Données de synchronisation des mouvements de stock reçues (API: /api/stock_internal_transfer_move_sync):")
        _logger.info("sale_transfer_move_sync_")
        _logger.info(f"MOVES: {received_moves}")
        _logger.info("sale_transfer_move_sync_")

        if not received_moves:
            _logger.info("Aucun mouvement de stock reçu pour la synchronisation.")
            return {
                'status': 200,
                'response': "Aucun mouvement reçu à synchroniser.",
                'message': 'Succès (aucune modification de la base de données).'
            }
        for move_data in received_moves:
            stock_move = request.env['stock.move'].sudo().search([('id', '=', move_data.get('id'))], limit=1)   # type: ignore
            stock_move_line = request.env['stock.move.line'].sudo().search([   # type: ignore
                ('move_id', '=', move_data.get('id')),
                ('picking_id', '=', stock_move.picking_id.id)
            ], limit=1)

            if not stock_move:
                msg = f"Mouvement de stock avec ID {move_data.get('id')} non trouvé dans la base de données."
                _logger.info(msg)
                errors.append(msg)  
                continue

            try:
                qty_before = stock_move_line.qty_done
                qty_to_add = move_data.get('qty_delivered', stock_move_line.qty_done)
                stock_move_line.write({
                    'qty_done': qty_before + qty_to_add,
                })

                user = request.env.user
                stock_move.picking_id.message_post(
                    body=f"""
                        <div style="padding:10px; border-left:3px solid #4caf50; background:#f9f9f9; margin:5px 0; border-radius:6px;">
                            <b>{user.name}</b> a livré 
                            <span style="color:#1976d2; font-weight:bold;">{qty_to_add}</span> unités 
                            du produit <i>{stock_move.product_id.display_name}</i>.
                        </div>
                    """,
                    message_type="comment",
                    subtype_xmlid="mail.mt_note"
                )


                _logger.info(f"Le mouvement de stock ID {move_data.get('id')} a été mis à jour avec succès.")

            except Exception as e:
                _logger.error(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")
                errors.append(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")

        if errors:
            return {
                'status': 500,
                'response': "Une erreur s'est produite lors de la synchronisation des mouvements de stock.",
                'message': 'Echec de la synchronisation des mouvements de stock.'
            }
        else:
            return {
                'status': 200,
                'response': "Synchronisation des mouvements de stock reussie.",
                'message': 'Succès (modification de la base de données).',
                'errors': errors if errors else None
            }
   
#_PURCHASE MOVES SYNC# 
    @http.route('/api/stock_purchase_move_sync', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def sync_stock_purchase_moves(self, moves, **kwargs): 
        received_moves = moves
        errors = []

        if not received_moves:
            _logger.info("Aucun mouvement de stock reçu pour la synchronisation.")
            return {
                'status': 200,
                'response': "Aucun mouvement reçu à synchroniser.",
                'message': 'Succès (aucune modification de la base de données).'
            }
        for move_data in received_moves:
            stock_move = request.env['stock.move'].sudo().search([('id', '=', move_data.get('id'))], limit=1)   # type: ignore
            stock_move_line = request.env['stock.move.line'].sudo().search([('move_id', '=', move_data.get('id')),('picking_id','=',stock_move.picking_id.id)], limit=1)   # type: ignore
            if not stock_move:
                msg = f"Mouvement de stock avec ID {move_data.get('id')} non trouvé dans la base de données."
                _logger.info(msg)
                errors.append(msg)  
                continue
            try:
                stock_move_line.create({
                    'move_id': stock_move.id,
                    'picking_id': stock_move.picking_id.id,
                    'company_id': stock_move.company_id.id,
                    'product_id': stock_move.product_id.id,
                    'product_uom_qty': 0,
                    'product_uom_id': stock_move_line.product_uom_id.id,
                    'date': fields.Datetime.now(),
                    'qty_done': move_data.get('qty_delivered', stock_move_line.qty_done),                    
                    'location_id': move_data.get('location_id') if move_data.get('location_id') else stock_move_line.location_id.id,
                    'location_dest_id': move_data.get('location_dest_id') if move_data.get('location_dest_id') else stock_move_line.location_dest_id.id,
                    'lot_name': move_data.get('delivered_lot') if move_data.get('delivered_lot') else None,
                })               
                _logger.info(f"Le mouvement de stock ID {move_data.get('id')} a été mis à jour avec succès.")
            except Exception as e:
                _logger.error(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")
                errors.append(f"Une erreur s'est produite lors du traitement du mouvement de stock ID {move_data.get('id')}: {str(e)}")
        if errors:
            return {
                'status': 500,
                'response': "Une erreur s'est produite lors de la synchronisation des mouvements de stock.",
                'message': 'Echec de la synchronisation des mouvements de stock.'
            }
        else:
            return {
                'status': 200,
                'response': "Synchronisation des mouvements de stock reussie.",
                'message': 'Succès (modification de la base de données).',
                'errors': errors if errors else None
            }
        


#PICKING VALIDATION#
    @http.route('/api/stock_picking_validation', type='json', auth='user', methods=['POST'], csrf=False)
    @restrict_to_inventory_sale_purchase
    def get_stock_move_picking_validation(self, pickingid, backorder, signature_image=None, recipient_name=None, notes=None,type='sale', **kwargs):
        picking = request.env['stock.picking'].sudo().browse(pickingid)   # type: ignore
        errors = []
        if not picking.exists():
            return {
                'status': 500,
                'response': "Une erreur s'est produite lors de la validation de la picking.",
                'message': 'Echec de la validation de la picking.'
            }

        # ✅ Enregistrement de la signature si fournie
        try:
            if signature_image:
                try:
                    # Nettoyage du base64
                    if signature_image.startswith("data:image"):
                        signature_image = signature_image.split(",")[1]
                        
                    signature_vals = {
                        'signature': signature_image,
                        'signed_by': recipient_name or "Inconnu",
                        'signed_on': fields.Datetime.now(),
                        'require_signature': True,  # au cas où
                    }
                    
                    if picking.sale_id:
                        picking.sale_id.sudo().write(signature_vals)
                        _logger.info(f"Signature appliquée sur le bon de commande {picking.sale_id.name}")
                        
                    body = f"""
                        <strong>Signature reçue via application mobile</strong><br/>
                        <strong>Signé par :</strong> {recipient_name or "Inconnu"}<br/>
                        <strong>Date :</strong> {fields.Datetime.now().strftime('%d/%m/%Y %H:%M')}<br/>
                        """
                    if notes:
                        body += f"<strong>Observations :</strong><br/>{notes}<br/>"
                        
                    attachment = request.env['ir.attachment'].sudo().create({   # type: ignore
                        'name': f"Signature_{picking.name}_{recipient_name or 'signataire'}.png",
                        'type': 'binary',
                        'datas': signature_image,
                        'res_model': 'stock.picking',
                        'res_id': picking.id,
                        'public': False,
                    })    
                    
                    picking.sudo().message_post(
                        body=body,
                        attachment_ids=[attachment.id],
                        message_type='comment',
                        subtype_xmlid='mail.mt_comment',
                    )                    

                    # Optionnel : garder aussi ton modèle personnalisé si tu en as besoin ailleurs
                    request.env['x_delivery.signature'].sudo().create({   # type: ignore
                        'picking_id': picking.id,
                        'signature_image': signature_image,
                        'recipient_name': recipient_name or "Inconnu",
                        'notes': notes or "",
                    })

                except Exception as e:
                    _logger.error(f"Erreur lors de l'ajout de la signature au sale.order: {str(e)}")
                    errors.append("Signature non ajoutée au bon de commande: %s" % str(e))
        except Exception as e:
            _logger.error(f"Erreur lors de l'enregistrement de la signature: {str(e)}")
            errors.append("Signature non enregistrée: %s" % str(e))

        if backorder:
            try:
                new_picking = picking.copy(default={
                    'backorder_id': picking.id,
                    'state': 'assigned',
                    'move_lines': [(5, 0, 0)],
                })
                for move in picking.move_lines:
                    qty_done_total = sum(move.move_line_ids.mapped('qty_done'))
                    if qty_done_total < move.product_uom_qty:
                        remaining_qty = move.product_uom_qty - qty_done_total
                        move.write({'product_uom_qty': qty_done_total, 'state': 'done'})
                        new_move = move.copy(default={
                            'picking_id': new_picking.id,
                            'product_uom_qty': remaining_qty,
                            'state': 'assigned',
                        })
                        request.env['stock.move.line'].sudo().create({   # type: ignore
                            'picking_id': new_picking.id,
                            'move_id': new_move.id,
                            'product_id': new_move.product_id.id,
                            'product_uom_qty': remaining_qty,
                            'product_uom_id': new_move.product_uom.id,
                            'qty_done': 0,
                            'location_id': new_move.location_id.id,
                            'location_dest_id': new_move.location_dest_id.id,
                            'lot_id': False,
                        })
                        _logger.info(f"Move {move.id} scindé -> Done: {qty_done_total}, Assigned: {remaining_qty}")
                    else:
                        move.write({'state': 'done'})
            except Exception as e:
                errors.append(str(e))
                return {
                    'status': 500,
                    'errors': errors,
                    'response': "Erreur lors de la validation avec backorder.",
                    'message': 'Echec de la validation.',
                }

            picking._action_done()
            return {
                'status': 200,
                'message': 'Picking validé avec backorder simulé (scission assigned).',
                'backorder_ids': [],
                'errors': errors,
            }
        else:
            _logger.info("Validation directe sans backorder -> scission + annulation reliquat")
            for move in picking.move_lines:
                qty_done_total = sum(move.move_line_ids.mapped('qty_done'))
                if qty_done_total < move.product_uom_qty:
                    remaining_qty = move.product_uom_qty - qty_done_total
                    move.write({'product_uom_qty': qty_done_total, 'state': 'done'})
                    move.copy(default={
                        'product_uom_qty': remaining_qty,
                        'state': 'cancel',
                    })
                    _logger.info(f"Move {move.id} scindé -> Done: {qty_done_total}, Cancel: {remaining_qty}")

            picking._action_done()
            return {
                'status': 200,
                'response': "Validation sans backorder avec annulation du reliquat.",
                'message': 'Succès (pas de backorder créé).',
                'errors': errors,
            }
             
    # @http.route('/api/stock_picking_validation', type='json', auth='user', methods=['POST'], csrf=False)
    # @restrict_to_inventory_sale_purchase
    # def get_stock_move_internal_picking_validation(self, pickingid, backorder, **kwargs):
    #     picking = request.env['stock.picking'].sudo().browse(pickingid)
    #     errors = []
    #     if not picking.exists():
    #         return {
    #             'status': 500,
    #             'response': "Une erreur s'est produite lors de la validation de la picking.",
    #             'message': 'Echec de la validation de la picking.'
    #         }
    #     if backorder:
    #         try:
    #             new_picking = picking.copy(default={
    #                             'backorder_id': picking.id,
    #                             'state': 'assigned',
    #                             'move_lines': [(5, 0, 0)],
    #                         })
    #             for move in picking.move_lines:
    #                 qty_done_total = sum(move.move_line_ids.mapped('qty_done'))
    #                 if qty_done_total < move.product_uom_qty:
    #                     remaining_qty = move.product_uom_qty - qty_done_total
                        

    #                     move.write({'product_uom_qty': qty_done_total, 'state': 'done'})

    #                     new_move = move.copy(default={
    #                         'picking_id': new_picking.id,
    #                         'product_uom_qty': remaining_qty,
    #                         'state': 'assigned',
    #                     })

    #                     request.env['stock.move.line'].sudo().create({
    #                         'picking_id': new_picking.id,
    #                         'move_id': new_move.id,
    #                         'product_id': new_move.product_id.id,
    #                         'product_uom_qty': remaining_qty,
    #                         'product_uom_id': new_move.product_uom.id,
    #                         'qty_done': 0,
    #                         'location_id': new_move.location_id.id,
    #                         'location_dest_id': new_move.location_dest_id.id,
    #                         'lot_id': False,  
    #                     })

    #                     _logger.info(f"Move {move.id} scindé -> Done: {qty_done_total}, Assigned (backorder simulé): {remaining_qty}")
                        
    #                 else:
    #                     move.write({'state': 'done'})
    #         except Exception as e:
    #             errors.append(str(e))
    #             return {
    #                 'status': 500,
    #                 'errors': errors,
    #                 'response': "Une erreur s'est produite lors de la validation de la picking.",
    #                 'message': 'Echec de la validation de la picking.'
    #             }

    #         picking._action_done()

    #         return {
    #             'status': 200,
    #             'message': 'Picking validé avec backorder simulé (scission assigned).',
    #             'backorder_ids': [], 
    #         }
    #     else:
    #         _logger.info("")
    #         _logger.info("Validation directe sans backorder -> scission + annulation reliquat")
            
    #         for move in picking.move_lines:
    #             qty_done_total = sum(move.move_line_ids.mapped('qty_done'))
    #             if qty_done_total < move.product_uom_qty:
    #                 remaining_qty = move.product_uom_qty - qty_done_total

    #                 move.write({'product_uom_qty': qty_done_total, 'state': 'done'})

    #                 new_move = move.copy(default={
    #                     'product_uom_qty': remaining_qty,
    #                     'state': 'cancel',
    #                 })
    #                 _logger.info(f"Move {move.id} scindé -> Done: {qty_done_total}, Cancel: {remaining_qty}")

    #         picking._action_done()

    #         return {
    #             'status': 200,
    #             'response': "Validation sans backorder avec annulation du reliquat.",
    #             'message': 'Succès (pas de backorder créé).',
    #         }

           
# En cas de changement d'avis sur la validation directe par le mobile, on modifie juste le stock_move_line : le product_uom_qty reste à sa valeur
# mais le qty_done est mis à jour avec la quantité livrée.