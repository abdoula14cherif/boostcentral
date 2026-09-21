import logging
from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.models.database import get_profile_by_slug, get_active_services, get_revendeur_prix_all

logger = logging.getLogger(__name__)
boutique_bp = Blueprint("boutique", __name__)


@boutique_bp.route("/r/<slug>")
def visiter(slug):
    """
    Lien public d'un revendeur (boostcentral.app/r/<slug>).
    Affiche une page boutique avec les services au prix de CE revendeur, et
    memorise le revendeur en session pour rattacher automatiquement le
    visiteur s'il cree un compte (meme mecanisme que le parrainage).
    """
    revendeur = get_profile_by_slug(slug)
    if not revendeur:
        flash("Ce lien revendeur n'existe pas ou n'est plus actif.", "error")
        return redirect(url_for("auth.login"))

    session["revendeur_slug"] = slug

    services = get_active_services()
    modele = revendeur.get("revendeur_modele")

    if modele == "marge":
        mes_prix = {p["service_id"]: p["prix_fcfa"] for p in get_revendeur_prix_all(revendeur["id"])}
        # N'afficher que les services pour lesquels le revendeur a fixe un prix
        services_affiches = []
        for s in services:
            if s["id"] in mes_prix:
                s2 = dict(s)
                s2["prix_affiche"] = mes_prix[s["id"]]
                services_affiches.append(s2)
    else:
        # Mode commission (ou revendeur sans prix personnalises) : prix standard affiches
        services_affiches = []
        for s in services:
            s2 = dict(s)
            s2["prix_affiche"] = s["prix_fcfa"]
            services_affiches.append(s2)

    services_par_reseau = {}
    for s in services_affiches:
        net = s["reseau"]
        services_par_reseau.setdefault(net, []).append(s)

    return render_template("boutique.html",
        revendeur=revendeur, services_par_reseau=services_par_reseau, slug=slug)
