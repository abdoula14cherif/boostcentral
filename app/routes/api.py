import logging
from flask import Blueprint, request, jsonify
from app.models.database import (get_profile_by_api_key, get_active_services, get_service_by_id,
    create_order, debit_balance, update_order, get_order_by_id_for_user)
from app.models.boostci import add_order as boostci_add

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__)


@api_bp.route("", methods=["POST"])
def handle():
    key = request.values.get("key", "").strip()
    action = request.values.get("action", "").strip()

    if not key:
        return jsonify({"error": "Cle API manquante."}), 401

    profile = get_profile_by_api_key(key)
    if not profile:
        return jsonify({"error": "Cle API invalide."}), 401

    user_id = profile["id"]

    if action == "balance":
        return jsonify({"balance": str(profile.get("balance", 0)), "currency": "FCFA"})

    if action == "services":
        services = get_active_services()
        return jsonify([{
            "service": s["id"],
            "name": s["categorie"],
            "category": s["reseau"],
            "rate": s["prix_fcfa"],
            "min": s["min_qte"],
            "max": s["max_qte"],
            "type": "Custom Comments" if s.get("custom_comments") else "Default"
        } for s in services])

    if action == "add":
        service_id = request.values.get("service", "")
        link = request.values.get("link", "").strip()
        quantity_raw = request.values.get("quantity", "0")
        comments_raw = request.values.get("comments", "").strip()

        try:
            service_id = int(service_id)
        except:
            return jsonify({"error": "Parametre service invalide."}), 400

        if not link or not link.startswith("http"):
            return jsonify({"error": "Parametre link invalide."}), 400

        service = get_service_by_id(service_id)
        if not service or not service.get("actif"):
            return jsonify({"error": "Service introuvable."}), 400

        is_custom = bool(service.get("custom_comments"))
        comments_list = []
        if is_custom:
            comments_list = [l.strip() for l in comments_raw.splitlines() if l.strip()]
            if not comments_list:
                return jsonify({"error": "Parametre comments requis pour ce service (1 par ligne)."}), 400
            quantity = len(comments_list)
        else:
            try:
                quantity = int(quantity_raw)
            except:
                return jsonify({"error": "Parametre quantity invalide."}), 400

        if quantity < service["min_qte"] or quantity > service["max_qte"]:
            return jsonify({"error": f"quantity doit etre entre {service['min_qte']} et {service['max_qte']}."}), 400

        unit_price = float(service["prix_fcfa"])
        total_price = round(unit_price * quantity * 0.99)

        balance = profile.get("balance", 0) or 0
        if balance < total_price:
            return jsonify({"error": "Solde insuffisant."}), 402

        order = create_order({
            "user_id": user_id,
            "user_email": profile.get("email", ""),
            "reseau": service["reseau"],
            "service": service["categorie"],
            "service_id": service["id"],
            "quantite": quantity,
            "lien": link,
            "commentaires": "\n".join(comments_list) if is_custom else None,
            "prix_unitaire": unit_price,
            "prix_total": total_price,
            "statut": "en_attente",
            "progression": 0,
            "note_admin": "Commande via API"
        })
        if not order:
            return jsonify({"error": "Erreur lors de la creation de la commande."}), 500

        new_balance = debit_balance(user_id, total_price)
        if new_balance is None:
            return jsonify({"error": "Erreur lors du debit du solde."}), 500

        boostci_id = service.get("boostci_service_id")
        if boostci_id:
            try:
                result = boostci_add(
                    service_id=int(boostci_id), link=link, quantity=quantity,
                    comments="\n".join(comments_list) if is_custom else None
                )
                if "order" in result:
                    update_order(order["id"], {"statut": "en_cours", "note_admin": f"API - BOOSTCI order ID: {result['order']}"})
                else:
                    update_order(order["id"], {"note_admin": f"API - BOOSTCI echec: {result.get('error','?')}"})
            except Exception as e:
                logger.error(f"API add BOOSTCI exception: {e}")
                update_order(order["id"], {"note_admin": f"API - exception BOOSTCI: {e}"})

        return jsonify({"order": order["id"]})

    if action == "status":
        order_id = request.values.get("order", "")
        try:
            order_id = int(order_id)
        except:
            return jsonify({"error": "Parametre order invalide."}), 400
        order = get_order_by_id_for_user(order_id, user_id)
        if not order:
            return jsonify({"error": "Commande introuvable."}), 404
        progression = order.get("progression") or 0
        quantite = order.get("quantite") or 0
        return jsonify({
            "charge": str(order.get("prix_total")),
            "start_count": "0",
            "status": order.get("statut"),
            "remains": str(max(0, quantite - (quantite * progression // 100))),
            "currency": "FCFA"
        })

    return jsonify({"error": "Action invalide. Actions disponibles : balance, services, add, status."}), 400
