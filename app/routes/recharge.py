import logging
import os
import uuid
import json
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge, update_recharge, get_recharge_by_hash

logger = logging.getLogger(__name__)

recharge_bp = Blueprint("recharge", __name__)

# Cle marchand SoleasPay - definie sur Vercel (Project Settings -> Environment Variables)
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
    """Enregistre la recharge EN ATTENTE, puis redirige vers Checkout v4 SoleasPay."""
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
    # SoleasPay redirigera vers receivePayment / appellera le webhook
    # (invoice_reference = cette valeur). Format UUID standard.
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

    if not result:
        flash("Erreur lors de l'enregistrement.", "error")
        return redirect(url_for("recharge.index"))

    recharge_id = result.get("id", "")
    logger.info(f"Recharge {recharge_id} creee en attente ({order_ref}): {user['email']} - {montant_fcfa} FCFA")
    session["pending_recharge_id"] = recharge_id

    return redirect(url_for("recharge.index") + f"?payer=1&montant={int(montant_fcfa)}&order={order_ref}")


@recharge_bp.route("/receivePayment")
@login_required
def receive_payment():
    """
    URL de retour apres un paiement REUSSI via Checkout v4 SoleasPay.
    Affichage/confirmation cote client uniquement - le CREDIT REEL du solde
    se fait via le webhook serveur-a-serveur (/recharge/webhook-soleaspay).
    """
    raw = request.args.get("soleaspay_data", "")
    data = {}
    if raw:
        try:
            data = json.loads(raw)
        except Exception as e:
            logger.error(f"receive_payment: erreur parsing soleaspay_data: {e}")

    invoice_reference = data.get("invoice_reference", "")
    status = data.get("status", "")
    transaction_reference = data.get("transaction_reference", "")

    if invoice_reference:
        recharge = get_recharge_by_hash(invoice_reference)
        if recharge and transaction_reference:
            update_recharge(recharge["id"], {"capture_url": transaction_reference})

    session.pop("pending_recharge_id", None)

    if status in ("SUCCESS", "COMPLETED"):
        flash("Paiement soumis ! Votre solde sera credite automatiquement des confirmation.", "success")
    else:
        flash("Paiement non confirme. Si le montant a ete debite, contactez le support.", "error")

    return redirect(url_for("recharge.index"))


@recharge_bp.route("/paymentFailed")
@login_required
def payment_failed():
    """URL de retour apres un paiement ECHOUE ou ANNULE via Checkout v4 SoleasPay."""
    session.pop("pending_recharge_id", None)
    flash("Paiement annule ou echoue. Vous pouvez reessayer.", "error")
    return redirect(url_for("recharge.index"))
