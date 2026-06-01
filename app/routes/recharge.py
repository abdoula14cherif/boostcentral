import logging
import requests as req
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

LEEKPAY_URL = "https://leekpay.fr/api/v1/checkout"
LEEKPAY_PK = "pk_live_h0RQu365IhnhdXkW2YeWZiDmKQGo7Pn1"

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    return render_template("dashboard/recharge.html",
        user=user, profile=profile, history=history,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])

@recharge_bp.route("/initier", methods=["POST"])
@login_required
def initier():
    user = get_current_user()
    montant = request.form.get("montant", "").strip()

    try:
        montant_fcfa = float(montant)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))

    if montant_fcfa < 500:
        flash("Montant minimum : 500 FCFA.", "error")
        return redirect(url_for("recharge.index"))

    try:
        # Creer le checkout LeekPay
        return_url = url_for("recharge.retour", _external=True)
        r = req.post(LEEKPAY_URL,
            headers={
                "Authorization": f"Bearer {LEEKPAY_PK}",
                "Content-Type": "application/json"
            },
            json={
                "amount": int(montant_fcfa),
                "currency": "XOF",
                "description": f"Recharge Boost Central - {user['email']}",
                "return_url": return_url,
                "customer_email": user["email"],
                "metadata": {
                    "user_id": user["id"],
                    "user_email": user["email"]
                }
            },
            timeout=15
        )
        data = r.json()
        logger.info(f"LeekPay response: {data}")

        if data.get("success") and data.get("data", {}).get("payment_url"):
            payment_id = data["data"]["payment_id"]
            payment_url = data["data"]["payment_url"]

            # Enregistrer en attente
            create_recharge({
                "user_id": user["id"],
                "user_email": user["email"],
                "montant_fcfa": montant_fcfa,
                "methode": "soinapay",
                "hash_tx": payment_id,
                "capture_url": None,
                "statut": "en_attente"
            })

            return redirect(payment_url)
        else:
            msg = data.get("message", str(data))
            flash(f"Erreur LeekPay : {msg}", "error")
            return redirect(url_for("recharge.index"))

    except Exception as e:
        logger.error(f"LeekPay erreur: {e}")
        flash(f"Erreur de connexion au service de paiement.", "error")
        return redirect(url_for("recharge.index"))

@recharge_bp.route("/retour")
@login_required
def retour():
    flash("Paiement effectue ! Votre solde sera credite apres validation.", "success")
    return redirect(url_for("recharge.index"))
