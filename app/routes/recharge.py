import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session, jsonify
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge, update_recharge
import requests as req

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

LEEKPAY_PK = "pk_live_h0RQu365IhnhdXkW2YeWZiDmKQGo7Pn1"

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    return render_template("dashboard/recharge.html",
        user=user, profile=profile, history=history,
        leekpay_pk=LEEKPAY_PK,
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

    # Enregistrer EN ATTENTE immediatement
    result = create_recharge({
        "user_id": user["id"],
        "user_email": user["email"],
        "montant_fcfa": montant_fcfa,
        "methode": "soinapay",
        "hash_tx": None,
        "capture_url": None,
        "statut": "en_attente"
    })

    if result:
        recharge_id = result.get("id", "")
        logger.info(f"Recharge {recharge_id} creee en attente: {user['email']} - {montant_fcfa} FCFA")
        # Stocker l'ID dans la session pour mise a jour apres paiement
        session["pending_recharge_id"] = recharge_id
        session["pending_recharge_amount"] = montant_fcfa
        flash(f"Paiement de {montant_fcfa:,.0f} FCFA initie. Completez le paiement.", "info")
    else:
        flash("Erreur lors de l'enregistrement.", "error")
        return redirect(url_for("recharge.index"))

    return redirect(url_for("recharge.index") + "?payer=1&montant=" + str(int(montant_fcfa)))

@recharge_bp.route("/success", methods=["POST"])
@login_required
def success():
    """Appele par LeekPay JS apres paiement reussi."""
    user = get_current_user()
    payment_id = request.form.get("payment_id", "")
    montant = request.form.get("montant", "0")
    recharge_id = session.get("pending_recharge_id", "")

    if recharge_id:
        # Mettre a jour avec le hash de transaction
        update_recharge(recharge_id, {"hash_tx": payment_id})
        logger.info(f"Paiement reussi: {payment_id} pour recharge {recharge_id}")
        session.pop("pending_recharge_id", None)
        session.pop("pending_recharge_amount", None)

    flash(f"Paiement confirme ! Votre solde sera credite apres validation admin.", "success")
    return redirect(url_for("recharge.index"))
