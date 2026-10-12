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

    # Recuperer la reference si presente dans l'URL (apres paiement)
    reference = request.args.get("ref", "")

    return render_template("vente.html",
        produit=produit, lien=lien, slug=slug,
        soleaspay_pk=SOLEASPAY_API_KEY,
        reference=reference)


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

    # === NOTIFIER L'ADMIN DE LA NOUVELLE VENTE ===
    try:
        from app.models.mailer import email_admin_nouvelle_vente
        from app.models.database import get_profile as _get_profile
        vendeur = _get_profile(lien["user_id"])
        email_admin_nouvelle_vente(
            nom_produit=produit["nom"],
            montant=prix_vente,
            acheteur_email=acheteur_email,
            vendeur_email=vendeur.get("email") if vendeur else "?",
            reference=reference,
            gain_affilie=gain_affilie
        )
    except Exception as e:
        logger.error(f"email_admin_nouvelle_vente: {e}")

    return redirect(url_for("vente.voir_produit", slug=slug) + f"?payer=1&montant={int(prix_vente)}&order={reference}")


@vente_bp.route("/p/<slug>/retour")
def retour(slug):
    import json
    raw = request.args.get("soleaspay_data", "")
    status = ""
    reference = request.args.get("ref", "")
    if raw:
        try:
            data = json.loads(raw)
            status = data.get("status", "")
            reference = data.get("orderId") or data.get("invoice_reference") or reference
        except Exception as e:
            logger.error(f"retour vente parse: {e}")

    if status in ("SUCCESS", "COMPLETED"):
        flash("✅ Paiement recu ! Votre achat sera confirme dans quelques instants.", "success")
    else:
        flash("Paiement non confirme. Si le montant a ete debite, contactez le support.", "error")

    # Rediriger vers la page de vente avec la reference pour afficher le suivi
    if reference:
        return redirect(url_for("vente.voir_produit", slug=slug) + f"?ref={reference}")
    return redirect(url_for("vente.voir_produit", slug=slug))


@vente_bp.route("/p/<slug>/echec")
def echec(slug):
    flash("Paiement annule ou echoue. Vous pouvez reessayer.", "error")
    return redirect(url_for("vente.voir_produit", slug=slug))


@vente_bp.route("/p/<slug>/statut")
def statut_vente(slug):
    """Verifie le statut d'une vente (appele en AJAX par la page apres paiement)."""
    from flask import jsonify
    from app.models.database import get_vente_by_reference

    reference = request.args.get("ref", "")
    if not reference:
        return jsonify({"erreur": "reference manquante"}), 400

    vente = get_vente_by_reference(reference)
    if not vente:
        return jsonify({"erreur": "vente introuvable"}), 404

    produit = get_produit_by_id(vente.get("produit_id"))
    lien_livraison = produit.get("lien_livraison") if produit else None

    return jsonify({
        "statut": vente.get("statut"),
        "reference": vente.get("reference"),
        "montant": vente.get("montant_paye"),
        "produit": produit.get("nom") if produit else "?",
        "lien_livraison": lien_livraison,
        "acheteur_email": vente.get("acheteur_email"),
    })