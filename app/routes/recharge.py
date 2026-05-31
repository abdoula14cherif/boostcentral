import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

CRYPTO_WALLETS = {
    "crypto_btc": {"label": "Bitcoin (BTC)", "address": "bc1pygygqdjmj60mph9yrn05extn3n4h22fv5ynt3w72hjd7arx64l4qdkp32x"},
    "crypto_bnb": {"label": "BNB (BSC)", "address": "0x44C9170272c7eA2c99f5dC28d955AdFE8b4AA3CB"},
    "crypto_sol": {"label": "Solana (SOL)", "address": "JBe5kePCCj3tG5RciCaNCEaJjtziycdrtKwz64Csx2VJ"},
}

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    return render_template("dashboard/recharge.html", user=user, profile=profile, history=history, crypto_wallets=CRYPTO_WALLETS, whatsapp=current_app.config["WHATSAPP_NUMBER"])

@recharge_bp.route("/mobile", methods=["POST"])
@login_required
def submit_mobile():
    user = get_current_user()
    method = request.form.get("method", "")
    amount = request.form.get("amount", "0")
    phone = request.form.get("phone_number", "").strip()
    if method not in ("mtn", "orange"):
        flash("Methode invalide.", "error")
        return redirect(url_for("recharge.index"))
    try:
        amount = float(amount)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))
    if amount < 500:
        flash("Montant minimum : 500 FCFA.", "error")
        return redirect(url_for("recharge.index"))
    if not phone:
        flash("Numero requis.", "error")
        return redirect(url_for("recharge.index"))
    result = create_recharge({"user_id": user["id"], "user_email": user["email"], "montant_fcfa": amount, "methode": method, "capture_url": phone, "hash_tx": None, "statut": "en_attente"})
    if result:
        flash("Demande envoyee !", "success")
    else:
        flash("Erreur lors de l'envoi.", "error")
    return redirect(url_for("recharge.index"))

@recharge_bp.route("/crypto", methods=["POST"])
@login_required
def submit_crypto():
    user = get_current_user()
    method = request.form.get("method", "")
    amount = request.form.get("amount", "0")
    txid = request.form.get("txid", "").strip()
    if method not in CRYPTO_WALLETS:
        flash("Methode invalide.", "error")
        return redirect(url_for("recharge.index"))
    try:
        amount = float(amount)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))
    if amount < 1000:
        flash("Montant minimum : 1000 FCFA.", "error")
        return redirect(url_for("recharge.index"))
    if not txid:
        flash("TXID requis.", "error")
        return redirect(url_for("recharge.index"))
    result = create_recharge({"user_id": user["id"], "user_email": user["email"], "montant_fcfa": amount, "methode": method, "hash_tx": txid, "capture_url": None, "statut": "en_attente"})
    if result:
        flash("Demande envoyee !", "success")
    else:
        flash("Erreur lors de l'envoi.", "error")
    return redirect(url_for("recharge.index"))
