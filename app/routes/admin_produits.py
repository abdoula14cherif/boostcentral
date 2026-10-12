import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.security import admin_required
from app.models.database import (
    get_all_produits, create_produit, update_produit,
    get_produit_by_id
)
from app.models.storage import upload_image

logger = logging.getLogger(__name__)
admin_produits_bp = Blueprint("admin_produits", __name__)


@admin_produits_bp.route("/produits")
@admin_required
def produits_page():
    produits = get_all_produits()
    return render_template("admin/produits.html", produits=produits)


@admin_produits_bp.route("/produits/ajouter", methods=["POST"])
@admin_required
def ajouter_produit():
    nom = request.form.get("nom", "").strip()
    description = request.form.get("description", "").strip()
    prix_str = request.form.get("prix_plateforme", "").strip()
    lien_livraison = request.form.get("lien_livraison", "").strip()
    image_file = request.files.get("image")

    if not nom or not prix_str:
        flash("Nom et prix sont requis.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    try:
        prix = float(prix_str)
        if prix <= 0:
            raise ValueError
    except ValueError:
        flash("Prix invalide.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    image_url = None
    if image_file and image_file.filename:
        image_url = upload_image(image_file, prefix="produit_")
        if not image_url:
            flash("Erreur upload image. Verifie le bucket Supabase.", "warning")

    data = {
        "nom": nom,
        "description": description or None,
        "prix_plateforme": prix,
        "lien_livraison": lien_livraison or None,
        "image_url": image_url,
        "actif": True,
    }

    result = create_produit(data)
    if result:
        flash(f"Produit '{nom}' cree !", "success")
    else:
        flash("Erreur lors de la creation du produit.", "error")

    return redirect(url_for("admin_produits.produits_page"))


@admin_produits_bp.route("/produits/modifier", methods=["POST"])
@admin_required
def modifier_produit():
    """Modifie un produit existant (nom, description, prix, lien livraison, image, actif)."""
    produit_id = request.form.get("produit_id", "")
    if not produit_id:
        flash("ID produit manquant.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    produit = get_produit_by_id(produit_id)
    if not produit:
        flash("Produit introuvable.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    data = {}

    # Nom
    nom = request.form.get("nom", "").strip()
    if nom:
        data["nom"] = nom

    # Description
    description = request.form.get("description", "").strip()
    data["description"] = description or None

    # Prix plateforme
    prix_str = request.form.get("prix_plateforme", "").strip()
    if prix_str:
        try:
            prix = float(prix_str)
            if prix > 0:
                data["prix_plateforme"] = prix
        except ValueError:
            pass

    # Lien de livraison
    lien_livraison = request.form.get("lien_livraison", "").strip()
    data["lien_livraison"] = lien_livraison or None

    # Image (upload si nouvelle image fournie)
    image_file = request.files.get("image")
    if image_file and image_file.filename:
        new_url = upload_image(image_file, prefix="produit_")
        if new_url:
            data["image_url"] = new_url

    ok = update_produit(produit_id, data)
    if ok:
        flash("Produit mis a jour.", "success")
    else:
        flash("Erreur lors de la mise a jour.", "error")

    return redirect(url_for("admin_produits.produits_page"))


@admin_produits_bp.route("/produits/toggle", methods=["POST"])
@admin_required
def toggle_produit():
    produit_id = request.form.get("produit_id", "")
    actif = request.form.get("actif") == "1"
    if not produit_id:
        flash("ID produit manquant.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    ok = update_produit(produit_id, {"actif": not actif})
    if ok:
        flash("Produit mis a jour.", "success")
    else:
        flash("Erreur mise a jour.", "error")
    return redirect(url_for("admin_produits.produits_page"))


@admin_produits_bp.route("/produits/supprimer", methods=["POST"])
@admin_required
def supprimer_produit():
    produit_id = request.form.get("produit_id", "")
    if not produit_id:
        flash("ID produit manquant.", "error")
        return redirect(url_for("admin_produits.produits_page"))

    # On ne supprime pas vraiment : on desactive (pour garder l'historique des ventes)
    ok = update_produit(produit_id, {"actif": False})
    if ok:
        flash("Produit desactive.", "success")
    else:
        flash("Erreur lors de la desactivation.", "error")
    return redirect(url_for("admin_produits.produits_page"))