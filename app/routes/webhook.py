import logging
from flask import Blueprint, request, jsonify, current_app
from app.models.database import credit_balance, create_recharge, get_recharge_by_hash, update_recharge
from app.routes.parrainage import crediter_commission_recharge
from app.models.promo import valider_code
from app.models.database import enregistrer_utilisation_code

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/webhook", methods=["POST"])
def soina_webhook():
    """Ancien webhook (LeekPay / SoinaPay) - conserve pour compatibilite, plus utilise activement."""
    try:
        data = request.get_json()
        logger.info(f"Webhook recu: {data}")
        event_type = data.get("type", "")
        if event_type != "payment.succeeded":
            return jsonify({"ok": True}), 200

        payment = data.get("data", {})
        amount = float(payment.get("amount", 0))
        currency = payment.get("currency", "XAF")
        metadata = payment.get("metadata", {})
        user_id = metadata.get("user_id", "")
        user_email = metadata.get("user_email", "")

        if not user_id or amount <= 0:
            return jsonify({"ok": False}), 400

        amount_fcfa = amount * 600 if currency == "USD" else amount

        credit_balance(user_id, amount_fcfa)
        create_recharge({"user_id": user_id, "user_email": user_email, "montant_fcfa": amount_fcfa, "methode": "soinapay", "hash_tx": payment.get("id", ""), "capture_url": None, "statut": "valide"})

        try:
            crediter_commission_recharge(user_id, amount_fcfa)
        except Exception as e:
            logger.error(f"commission parrainage webhook: {e}")

        logger.info(f"Credite: {amount_fcfa} FCFA -> {user_email}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"Webhook erreur: {e}")
        return jsonify({"error": str(e)}), 500


@webhook_bp.route("/webhook-soleaspay", methods=["POST"])
def soleaspay_webhook():
    """
    Webhook serveur-a-serveur SoleasPay. C'est LUI qui credite reellement le
    solde - jamais la confirmation cote client (recharge.success). URL a
    configurer sur le dashboard marchand SoleasPay :
    https://<ton-domaine>/recharge/webhook-soleaspay
    """
    try:
        data = request.get_json(force=True, silent=True) or {}
        logger.info(f"Webhook SoleasPay recu: {data}")

        status = data.get("status", "")
        invoice_reference = data.get("invoice_reference", "")
        transaction_reference = data.get("transaction_reference", "")

        try:
            amount = float(data.get("amount", 0))
        except:
            amount = 0

        # Toujours repondre 200 rapidement, meme si on ignore l'evenement -
        # SoleasPay rejoue les webhooks non confirmes.
        if status not in ("COMPLETED", "SUCCESS") or not invoice_reference or amount <= 0:
            return jsonify({"received": True}), 200

        recharge = get_recharge_by_hash(invoice_reference)
        if not recharge:
            logger.warning(f"Webhook SoleasPay: aucune recharge trouvee pour la reference {invoice_reference}")
            return jsonify({"received": True}), 200

        # Idempotence : si deja validee (webhook rejoue), on ne credite pas deux fois
        if recharge.get("statut") == "valide":
            return jsonify({"received": True}), 200

        user_id = recharge["user_id"]
        montant_fcfa = recharge.get("montant_fcfa") or amount
        montant_credite = montant_fcfa
        promo_code = recharge.get("promo_code")

        if promo_code:
            ok, message, promo = valider_code(promo_code, user_id)
            if ok:
                bonus = round(montant_fcfa * promo["bonus_pct"])
                montant_credite = montant_fcfa + bonus
                enregistrer_utilisation_code(promo["id"], user_id, recharge["id"])
                logger.info(f"Bonus promo {promo_code} applique: +{bonus} FCFA pour user {user_id}")
            else:
                logger.warning(f"Code promo {promo_code} devenu invalide au moment du credit: {message}")

        credit_balance(user_id, montant_credite)
        update_recharge(recharge["id"], {
            "statut": "valide",
            "capture_url": transaction_reference
        })

        try:
            crediter_commission_recharge(user_id, montant_fcfa)
        except Exception as e:
            logger.error(f"commission parrainage webhook soleaspay: {e}")

        logger.info(f"SoleasPay credite: {montant_credite} FCFA -> user {user_id} (ref {invoice_reference})")
        return jsonify({"received": True}), 200
    except Exception as e:
        logger.error(f"Webhook SoleasPay erreur: {e}")
        # On repond quand meme 200 pour eviter un rejeu en boucle sur une erreur
        # de notre cote ; l'erreur est loggee pour investigation manuelle.
        return jsonify({"received": True}), 200
