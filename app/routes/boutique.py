import logging
from flask import Blueprint, redirect, url_for, session, flash
from app.models.database import get_profile_by_slug

logger = logging.getLogger(__name__)
boutique_bp = Blueprint("boutique", __name__)


@boutique_bp.route("/r/<slug>")
def visiter(slug):
    """
    Lien public d'un revendeur (boostcentral.app/r/<slug>).
    Memorise le revendeur en session pour rattacher automatiquement le
    visiteur s'il cree un compte (meme mecanisme que le parrainage).
    """
    revendeur = get_profile_by_slug(slug)
    if not revendeur:
        flash("Ce lien revendeur n'existe pas ou n'est plus actif.", "error")
        return redirect(url_for("auth.login"))

    session["revendeur_slug"] = slug
    return redirect(url_for("auth.login"))
