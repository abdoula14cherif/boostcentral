import logging
from flask import Blueprint, request, jsonify, current_app
from app.models.database import credit_balance, create_recharge

logger = logging.getLogger(__name__)
webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/webhook", methods=["POST"])
def soina_webhook():
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
        logger.info(f"Credite: {amount_fcfa} FCFA -> {user_email}")
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"Webhook erreur: {e}")
        return jsonify({"error": str(e)}), 500
