import logging
import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session, jsonify
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge, update_recharge

logger = logging.getLogger(__name__)

recharge_bp = Blueprint("recharge", __name__)

# Cle marchand SoleasPay (Button v4) - definie sur Vercel (Project Settings -> Environment Variables)
# Nom de la variable : SOLEASPAY_API_KEY
SOLEASPAY_API_KEY = os.environ.get("SOLEASPAY_API_KEY", "")


@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    return render_template("dashboard/recharge.html",
        user=user, profile=profile, history=history,
        soleaspay_pk=SOLEASPAY_API_KEY,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])


@recharge_bp.route("/initier", methods=["POST"])
@login_required
def initier():
    """Enregistre la recharge EN ATTENTE avant de lancer le paiement."""
    user = get_current_user()
    montant = request.form.get("montant", "0").strip()

    try:
        montant_fcfa = float(montant)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))

    if montant_fcfa < 100:
        flash("Montant minimum : 100 FCFA.", "error")
        return redirect(url_for("recharge.index"))

    # Reference unique qui servira a retrouver cette recharge quand
    # SoleasPay appellera le webhook (invoice_reference = cette valeur).
    # Format UUID standard : valide que hash_tx soit type "uuid" ou "text" en base.
    order_ref = str(uuid.uuid4())

    result = create_recharge({
        "user_id": user["id"],
        "user_email": user["email"],
        "montant_fcfa": montant_fcfa,
        "methode": "soleaspay",
        "hash_tx": order_ref,
        "capture_url": None,
        "statut": "en_attente"
    })

    if result:
        recharge_id = result.get("id", "")
        logger.info(f"Recharge {recharge_id} creee en attente ({order_ref}): {user['email']} - {montant_fcfa} FCFA")
        session["pending_recharge_id"] = recharge_id
        session["pending_recharge_amount"] = montant_fcfa
        flash(f"Paiement de {montant_fcfa:,.0f} FCFA initie. Completez le paiement.", "info")
    else:
        flash("Erreur lors de l'enregistrement.", "error")
        return redirect(url_for("recharge.index"))

    return redirect(url_for("recharge.index") + f"?payer=1&montant={int(montant_fcfa)}&order={order_ref}")


@recharge_bp.route("/success", methods=["POST"])
@login_required
def success():
    """
    Appele par le plugin SoleasPay (cote client) juste apres le paiement,
    pour affichage immediat. Le CREDIT REEL du solde se fait uniquement via
    le webhook serveur-a-serveur (/recharge/webhook-soleaspay), jamais ici -
    cet appel client n'est pas fiable a lui seul pour crediter de l'argent.
    """
    payment_id = request.form.get("payment_id", "")
    recharge_id = session.get("pending_recharge_id", "")

    if recharge_id and payment_id:
        update_recharge(recharge_id, {"capture_url": payment_id})
        logger.info(f"Confirmation client SoleasPay: {payment_id} pour recharge {recharge_id}")

    session.pop("pending_recharge_id", None)
    session.pop("pending_recharge_amount", None)
    flash("Paiement soumis ! Votre solde sera credite automatiquement des confirmation.", "success")
    return redirect(url_for("recharge.index"))
