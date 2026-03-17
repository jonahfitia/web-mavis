# -*- coding: utf-8 -*-
from odoo import http
from odoo.http import request
import traceback
import logging

_logger = logging.getLogger(__name__)


class AIReportController(http.Controller):

    @http.route('/api/ai/process_phrase', type='json', auth='user', methods=['POST'], csrf=False)
    def process_phrase_mobile(self, **kwargs):
        """
        Endpoint pour exécuter une phrase naturelle et obtenir un résultat AI (list ou stat).
        Accessible via React Native ou toute app externe.
        """
        try:
            # ✅ Récupération des paramètres JSON envoyés par le client
            phrase = kwargs.get('phrase')
            access_level = kwargs.get('access_level', 'standard')

            if not phrase:
                _logger.warning("Aucune phrase reçue dans la requête mobile.")
                return {
                    "status": 400,
                    "message": "La clé 'phrase' est requise."
                }

            # ✅ Appel à la fonction principale du modèle
            ai_report = request.env["ai.report"].sudo() # type: ignore
            result = ai_report.process_phrase(phrase, acc=access_level)

            # ✅ Réponse standardisée
            return {
                "status": 200,
                "success": True,
                "data": result,
                "message": "Traitement réussi"
            }

        except Exception as e:
            # Capture du stacktrace complet pour debug
            trace = traceback.format_exc()
            _logger.error(f"Erreur dans /api/ai/process_phrase: {e}\n{trace}")

            return {
                "status": 500,
                "success": False,
                "message": str(e),
                "trace": trace
            }
