import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    soina_url = current_app.config.get("SOINA_PAY_URL", "https://soinapay.com/pay/zmnmqbap")
    return render_template("dashboard/recharge.html",
        user=user, profile=profile, history=history,
        soina_url=soina_url,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])

@recharge_bp.route("/initier", methods=["POST"])
@login_required
def initier():
    """
    Enregistre la recharge en attente AVANT de rediriger vers SoinaPay.
    Comme ca l admin voit la transaction meme si le webhook echoue.
    """
    user = get_current_user()
    montant = request.form.get("montant", "").strip()

    if not montant:
        flash("Veuillez entrer un montant.", "error")
        return redirect(url_for("recharge.index"))

    try:
        montant_fcfa = float(montant)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))

    if montant_fcfa < 500:
        flash("Montant minimum : 500 FCFA.", "error")
        return redirect(url_for("recharge.index"))

    # Enregistrer en attente
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
        flash(f"Demande de {montant_fcfa:,.0f} FCFA enregistree. Completez le paiement.", "info")
        logger.info(f"Recharge initiee: {user['email']} - {montant_fcfa} FCFA")
    else:
        flash("Erreur lors de l'enregistrement.", "error")

    # Rediriger vers SoinaPay
    soina_url = current_app.config.get("SOINA_PAY_URL", "https://soinapay.com/pay/zmnmqbap")
    return redirect(soina_url)
