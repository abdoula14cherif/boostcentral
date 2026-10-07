import os
import uuid
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.database import get_lien_by_slug, get_produit_by_id, create_vente

logger = logging.getLogger(__name__)
vente_bp = Blueprint("vente", __name__)

SOLEASPAY_API_KEY = os.environ.get("SOLEASPAY_API_KEY", "")
TAUX_COMMISSION_BASE = 0.02


@vente_bp.route("/p/<slug>")
def voir_produit(slug):
    lien = get_lien_by_slug(slug)
    if not lien:
        flash("Ce lien de vente n'existe pas ou n'est plus actif.", "error")
        return redirect(url_for("vitrine.preuves_publiques"))

    produit = get_produit_by_id(lien["produit_id"])
    if not produit or not produit.get("actif"):
        flash("Ce produit n'est plus disponible.", "error")
        return redirect(url_for("vitrine.preuves_publiques"))

    return render_template("vente.html",
        produit=produit, lien=lien, slug=slug, soleaspay_pk=SOLEASPAY_API_KEY)


@vente_bp.route("/p/<slug>/initier", methods=["POST"])
def initier_achat(slug):
    lien = get_lien_by_slug(slug)
    if not lien:
        flash("Lien invalide.", "error")
        return redirect(url_for("vitrine.preuves_publiques"))

    produit = get_produit_by_id(lien["produit_id"])
    if not produit or not produit.get("actif"):
        flash("Produit indisponible.", "error")
        return redirect(url_for("vitrine.preuves_publiques"))

    acheteur_email = request.form.get("email", "").strip()
    if not acheteur_email or "@" not in acheteur_email:
        flash("Email valide requis.", "error")
        return redirect(url_for("vente.voir_produit", slug=slug))

    reference = str(uuid.uuid4())
    prix_vente = float(lien["prix_vente"])
    prix_plateforme = float(produit["prix_plateforme"])
    gain_base = prix_plateforme * TAUX_COMMISSION_BASE
    gain_marge = max(0, prix_vente - prix_plateforme)
    gain_affilie = round(gain_base + gain_marge)

    vente = create_vente({
        "lien_id": lien["id"], "user_id": lien["user_id"], "produit_id": produit["id"],
        "acheteur_email": acheteur_email, "montant_paye": prix_vente,
        "gain_affilie": gain_affilie, "reference": reference, "statut": "en_attente"
    })

    if not vente:
        flash("Erreur lors de l'enregistrement de la commande.", "error")
        return redirect(url_for("vente.voir_produit", slug=slug))

    logger.info(f"Vente initiee {reference}: produit={produit['nom']} prix={prix_vente} acheteur={acheteur_email}")
    return redirect(url_for("vente.voir_produit", slug=slug) + f"?payer=1&montant={int(prix_vente)}&order={reference}")


@vente_bp.route("/p/<slug>/retour")
def retour(slug):
    import json
    raw = request.args.get("soleaspay_data", "")
    status = ""
    if raw:
        try:
            data = json.loads(raw)
            status = data.get("status", "")
        except Exception as e:
            logger.error(f"retour vente parse: {e}")

    if status in ("SUCCESS", "COMPLETED"):
        flash("✅ Paiement recu ! Votre achat sera confirme dans quelques instants.", "success")
    else:
        flash("Paiement non confirme. Si le montant a ete debite, contactez le support.", "error")
    return redirect(url_for("vente.voir_produit", slug=slug))


@vente_bp.route("/p/<slug>/echec")
def echec(slug):
    flash("Paiement annule ou echoue. Vous pouvez reessayer.", "error")
    return redirect(url_for("vente.voir_produit", slug=slug))
