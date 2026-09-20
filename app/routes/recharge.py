import logging
import os
import uuid
import json
import io
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session, jsonify, send_file
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge, update_recharge, get_recharge_by_hash, get_recharge_by_id_for_user
from app.models.promo import valider_code

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


@recharge_bp.route("/verifier-code", methods=["POST"])
@login_required
def verifier_code():
    """Verification AJAX d'un code promo pendant la saisie (avant paiement)."""
    user = get_current_user()
    code = request.form.get("code", "").strip()
    ok, message, promo = valider_code(code, user["id"])
    return jsonify({"ok": ok, "message": message, "bonus_pct": promo["bonus_pct"] if promo else 0})


@recharge_bp.route("/initier", methods=["POST"])
@login_required
def initier():
    """Enregistre la recharge EN ATTENTE, puis redirige vers Checkout v4 SoleasPay."""
    user = get_current_user()
    montant = request.form.get("montant", "0").strip()
    code_promo = request.form.get("code_promo", "").strip().upper()

    try:
        montant_fcfa = float(montant)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("recharge.index"))

    if montant_fcfa < 100:
        flash("Montant minimum : 100 FCFA.", "error")
        return redirect(url_for("recharge.index"))

    # Revalidation cote serveur du code promo (ne jamais faire confiance au JS seul)
    promo_valide = None
    if code_promo:
        ok, message, promo = valider_code(code_promo, user["id"])
        if ok:
            promo_valide = code_promo
        else:
            flash(f"Code promo ignore : {message}", "warning")

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
        "statut": "en_attente",
        "promo_code": promo_valide
    })

    if not result:
        flash("Erreur lors de l'enregistrement.", "error")
        return redirect(url_for("recharge.index"))

    recharge_id = result.get("id", "")
    logger.info(f"Recharge {recharge_id} creee en attente ({order_ref}): {user['email']} - {montant_fcfa} FCFA" + (f" [promo {promo_valide}]" if promo_valide else ""))
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


@recharge_bp.route("/facture/<recharge_id>")
@login_required
def facture(recharge_id):
    """Genere et telecharge la facture PDF d'une recharge validee."""
    user = get_current_user()
    rch = get_recharge_by_id_for_user(recharge_id, user["id"])

    if not rch:
        flash("Facture introuvable.", "error")
        return redirect(url_for("recharge.index"))

    if rch.get("statut") != "valide":
        flash("Cette recharge n'est pas encore validee.", "warning")
        return redirect(url_for("recharge.index"))

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.pdfgen import canvas as pdfcanvas

    buf = io.BytesIO()
    c = pdfcanvas.Canvas(buf, pagesize=A4)
    width, height = A4

    bleu = colors.HexColor("#0066FF")
    orange = colors.HexColor("#FF6600")
    gris = colors.HexColor("#64748B")
    fond = colors.HexColor("#F1F5F9")

    # En-tete
    c.setFillColor(bleu)
    c.rect(0, height - 32 * mm, width, 32 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(20 * mm, height - 18 * mm, "BOOST CENTRAL")
    c.setFont("Helvetica", 9)
    c.drawString(20 * mm, height - 25 * mm, "Facture de recharge")

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(width - 20 * mm, height - 18 * mm, f"N° {str(rch.get('id'))[:10]}")
    date_str = (rch.get("created_at") or "")[:10]
    c.setFont("Helvetica", 9)
    c.drawRightString(width - 20 * mm, height - 25 * mm, f"Date : {date_str}")

    y = height - 45 * mm

    # Bloc client
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20 * mm, y, "Facture etablie pour")
    c.setFont("Helvetica", 10)
    c.setFillColor(gris)
    c.drawString(20 * mm, y - 6 * mm, rch.get("user_email", ""))

    y -= 20 * mm

    # Tableau
    c.setFillColor(fond)
    c.rect(20 * mm, y - 8 * mm, width - 40 * mm, 8 * mm, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(23 * mm, y - 5.5 * mm, "Description")
    c.drawRightString(width - 23 * mm, y - 5.5 * mm, "Montant")

    y -= 8 * mm
    ml = {"mtn": "MTN Mobile Money", "orange": "Orange Money", "leekpay": "LeekPay",
          "soinapay": "LeekPay", "soleaspay": "SoleasPay", "crypto_btc": "Bitcoin",
          "crypto_bnb": "BNB", "crypto_sol": "Solana"}
    methode = ml.get(rch.get("methode"), rch.get("methode", ""))
    montant = rch.get("montant_fcfa", 0) or 0

    c.setFont("Helvetica", 9)
    y -= 8 * mm
    c.drawString(23 * mm, y, f"Recharge de solde — {methode}")
    c.drawRightString(width - 23 * mm, y, f"{montant:,.0f} FCFA")

    if rch.get("promo_code"):
        y -= 7 * mm
        c.setFillColor(gris)
        c.drawString(23 * mm, y, f"Code promo applique : {rch.get('promo_code')}")
        c.setFillColor(colors.black)

    y -= 5 * mm
    c.setStrokeColor(colors.HexColor("#E2E8F0"))
    c.line(20 * mm, y, width - 20 * mm, y)

    y -= 10 * mm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(23 * mm, y, "Total credite")
    c.setFillColor(orange)
    c.drawRightString(width - 23 * mm, y, f"{montant:,.0f} FCFA")

    y -= 8 * mm
    c.setFillColor(colors.HexColor("#059669"))
    c.setFont("Helvetica-Bold", 9)
    c.drawString(23 * mm, y, "STATUT : VALIDEE")

    # Pied de page
    c.setFillColor(gris)
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 15 * mm, "Boost Central — Cette facture confirme le credit de votre solde interne.")
    c.drawCentredString(width / 2, 11 * mm, "Support WhatsApp : https://wa.me/237689011185")

    c.showPage()
    c.save()
    buf.seek(0)

    return send_file(buf, mimetype="application/pdf", as_attachment=True,
                      download_name=f"facture-boostcentral-{str(rch.get('id'))[:8]}.pdf")
