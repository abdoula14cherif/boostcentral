import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge

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

@recharge_bp.route("/enregistrer", methods=["POST"])
@login_required
def enregistrer():
    """Enregistre la recharge en attente apres paiement LeekPay."""
    user = get_current_user()
    montant = request.form.get("montant", "0")
    payment_id = request.form.get("payment_id", "")

    try:
        montant_fcfa = float(montant)
    except:
        return "Erreur", 400

    result = create_recharge({
        "user_id": user["id"],
        "user_email": user["email"],
        "montant_fcfa": montant_fcfa,
        "methode": "soinapay",
        "hash_tx": payment_id,
        "capture_url": None,
        "statut": "en_attente"
    })

    if result:
        logger.info(f"Recharge enregistree: {user['email']} - {montant_fcfa} FCFA - {payment_id}")
        flash(f"Paiement de {montant_fcfa:,.0f} FCFA recu ! Votre solde sera credite apres validation.", "success")
    else:
        flash("Erreur enregistrement. Contactez le support.", "error")

    return redirect(url_for("recharge.index"))
