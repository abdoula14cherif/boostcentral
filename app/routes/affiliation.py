import secrets
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.security import login_required, get_current_user
from app.models.database import (get_profile, get_active_produits, get_produit_by_id,
    get_lien_user_produit, create_lien, update_lien_prix, get_user_liens)

logger = logging.getLogger(__name__)
affiliation_bp = Blueprint("affiliation", __name__)

TAUX_COMMISSION_BASE = 0.02  # 2% du prix plateforme, toujours garanti a l'affilie


@affiliation_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    produits = get_active_produits()
    mes_liens = {l["produit_id"]: l for l in get_user_liens(user["id"])}

    return render_template("dashboard/affiliation.html",
        user=user, profile=profile, produits=produits, mes_liens=mes_liens,
        taux_commission=int(TAUX_COMMISSION_BASE * 100))


@affiliation_bp.route("/vendre", methods=["POST"])
@login_required
def vendre():
    user = get_current_user()
    produit_id = request.form.get("produit_id", "")
    prix_vente_raw = request.form.get("prix_vente", "").strip()

    try:
        produit_id = int(produit_id)
    except:
        flash("Produit invalide.", "error")
        return redirect(url_for("affiliation.index"))

    produit = get_produit_by_id(produit_id)
    if not produit or not produit.get("actif"):
        flash("Produit introuvable ou inactif.", "error")
        return redirect(url_for("affiliation.index"))

    prix_plateforme = float(produit["prix_plateforme"])

    try:
        prix_vente = float(prix_vente_raw) if prix_vente_raw else prix_plateforme
    except:
        flash("Prix invalide.", "error")
        return redirect(url_for("affiliation.index"))

    if prix_vente < prix_plateforme:
        flash(f"Votre prix ne peut pas etre inferieur au prix plateforme ({prix_plateforme:,.0f} FCFA).", "error")
        return redirect(url_for("affiliation.index"))

    lien_existant = get_lien_user_produit(user["id"], produit_id)
    if lien_existant:
        update_lien_prix(lien_existant["id"], prix_vente)
        flash("Prix mis a jour !", "success")
    else:
        slug = secrets.token_urlsafe(5).replace("_", "").replace("-", "")[:7].lower()
        create_lien({
            "user_id": user["id"], "produit_id": produit_id,
            "slug": slug, "prix_vente": prix_vente
        })
        flash("Votre lien de vente a ete genere !", "success")

    return redirect(url_for("affiliation.index"))
