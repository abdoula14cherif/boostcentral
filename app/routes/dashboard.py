import logging
from flask import Blueprint, render_template, redirect, url_for, flash, session, jsonify, current_app, request
from app.models.security import login_required, get_current_user
from app.models.database import (get_profile, get_active_services, get_user_orders,
    get_service_by_id, create_order, debit_balance, update_order)
from app.models.forms import OrderForm
from app.models.boostci import add_order as boostci_add, get_balance as boostci_balance

logger = logging.getLogger(__name__)
dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    services = get_active_services()
    orders = get_user_orders(user["id"], limit=20)
    services_by_network = {}
    for svc in services:
        net = svc["reseau"]
        if net not in services_by_network:
            services_by_network[net] = []
        services_by_network[net].append(svc)
    form = OrderForm()
    return render_template("dashboard/index.html",
        user=user, profile=profile,
        services_by_network=services_by_network,
        orders=orders, form=form,
        whatsapp=current_app.config["WHATSAPP_NUMBER"],
        currency=session.get("currency", "FCFA"))

@dashboard_bp.route("/order", methods=["POST"])
@login_required
def place_order():
    user = get_current_user()
    network = request.form.get("network", "")
    service_id = request.form.get("service_id", "")
    link = request.form.get("link", "").strip()
    quantity = request.form.get("quantity", "0")

    if not network or not service_id or not link:
        flash("Tous les champs sont requis.", "error")
        return redirect(url_for("dashboard.index"))

    try:
        quantity = int(quantity)
        service_id = int(service_id)
    except:
        flash("Donnees invalides.", "error")
        return redirect(url_for("dashboard.index"))

    if not link.startswith("http"):
        flash("Le lien doit commencer par http.", "error")
        return redirect(url_for("dashboard.index"))

    service = get_service_by_id(service_id)
    if not service or not service.get("actif"):
        flash("Service invalide.", "error")
        return redirect(url_for("dashboard.index"))

    if quantity < service["min_qte"]:
        flash(f"Quantite minimum : {service['min_qte']:,}.", "error")
        return redirect(url_for("dashboard.index"))

    if quantity > service["max_qte"]:
        flash(f"Quantite maximum : {service['max_qte']:,}.", "error")
        return redirect(url_for("dashboard.index"))

    unit_price = float(service["prix_fcfa"])
    total_price = round(unit_price * quantity * 0.99)

    profile = get_profile(user["id"])
    balance = profile.get("balance", 0) if profile else 0

    if balance < total_price:
        flash(f"Solde insuffisant. Solde : {balance:,.0f} FCFA — Requis : {total_price:,.0f} FCFA.", "error")
        return redirect(url_for("dashboard.index"))

    # Creer la commande en BDD
    order = create_order({
        "user_id": user["id"],
        "user_email": user["email"],
        "reseau": service["reseau"],
        "service": service["categorie"],
        "service_id": service["id"],
        "quantite": quantity,
        "lien": link,
        "prix_unitaire": unit_price,
        "prix_total": total_price,
        "statut": "en_attente",
        "progression": 0,
        "note_admin": ""
    })

    if not order:
        flash("Erreur lors de la commande.", "error")
        return redirect(url_for("dashboard.index"))

    # Debiter le solde
    new_balance = debit_balance(user["id"], total_price)
    if new_balance is None:
        flash("Erreur lors du debit.", "error")
        return redirect(url_for("dashboard.index"))

    # Envoyer chez BOOSTCI si service lie
    boostci_id = service.get("boostci_service_id")
    if boostci_id:
        try:
            # Verifier solde BOOSTCI
            solde = boostci_balance()
            if solde < 0.05:
                note = f"⚠️ SOLDE BOOSTCI INSUFFISANT ({solde}$) - Traiter manuellement"
                update_order(order["id"], {"statut": "en_attente", "note_admin": note})
                logger.warning(note)
                flash(f"Commande passee ! ✅ {total_price:,.0f} FCFA debites. Notre equipe traite votre commande.", "success")
                return redirect(url_for("dashboard.index") + "#orders")

            result = boostci_add(
                service_id=int(boostci_id),
                link=link,
                quantity=quantity
            )

            if "order" in result:
                boostci_order_id = result["order"]
                update_order(order["id"], {
                    "statut": "en_cours",
                    "progression": 0,
                    "note_admin": f"✅ BOOSTCI order ID: {boostci_order_id}"
                })
                logger.info(f"BOOSTCI OK: order={boostci_order_id} user={user['email']}")
                flash(f"Commande passee ! ✅ {total_price:,.0f} FCFA debites. Notre equipe traite votre commande.", "success")
            else:
                error = result.get("error", "Erreur inconnue")
                note = f"❌ BOOSTCI ECHEC: {error} - Traiter manuellement"
                update_order(order["id"], {
                    "statut": "en_attente",
                    "note_admin": note
                })
                logger.error(f"BOOSTCI erreur: {error} pour {user['email']}")
                flash(f"Commande passee ! ✅ {total_price:,.0f} FCFA debites. Notre equipe traite votre commande.", "success")

        except Exception as e:
            note = f"❌ EXCEPTION BOOSTCI: {str(e)} - Traiter manuellement"
            update_order(order["id"], {"note_admin": note})
            logger.error(f"BOOSTCI exception: {e}")
            flash(f"Commande passee ! ✅ {total_price:,.0f} FCFA debites. Notre equipe traite votre commande.", "success")
    else:
        flash(f"Commande passee ! ✅ {total_price:,.0f} FCFA debites. Notre equipe traite votre commande.", "success")

    return redirect(url_for("dashboard.index") + "#orders")

@dashboard_bp.route("/api/services/<string:network>")
@login_required
def api_services(network):
    allowed = {"facebook","tiktok","instagram","youtube","twitter","telegram","spotify","whatsapp"}
    if network not in allowed:
        return jsonify([])
    services = get_active_services(network=network)
    return jsonify([{
        "id": s["id"],
        "categorie": s["categorie"],
        "prix_fcfa": s["prix_fcfa"],
        "min_qte": s["min_qte"],
        "max_qte": s["max_qte"],
        "description": s.get("description", "")
    } for s in services])
