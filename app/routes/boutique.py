import logging
from flask import Blueprint, render_template, redirect, url_for, session, flash
from app.models.database import get_profile_by_slug, get_active_services, get_revendeur_prix_all

logger = logging.getLogger(__name__)
boutique_bp = Blueprint("boutique", __name__)


# Themes predefinis (nom -> (couleur principale, couleur secondaire))
THEMES = {
    "bleu":   ("#0066FF", "#0047CC"),
    "violet": ("#7C3AED", "#4C1D95"),
    "vert":   ("#059669", "#047857"),
    "orange": ("#F97316", "#EA580C"),
    "noir":   ("#0F172A", "#1E293B"),
    "rouge":  ("#DC2626", "#991B1B"),
}


@boutique_bp.route("/r/<slug>")
def visiter(slug):
    """
    Lien public d'un revendeur (boostcentral.app/r/<slug>).
    Affiche une page boutique personnalisee avec les services au prix de CE revendeur.
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
        services_affiches = []
        for s in services:
            if s["id"] in mes_prix:
                s2 = dict(s)
                s2["prix_affiche"] = mes_prix[s["id"]]
                services_affiches.append(s2)
    else:
        services_affiches = []
        for s in services:
            s2 = dict(s)
            s2["prix_affiche"] = s["prix_fcfa"]
            services_affiches.append(s2)

    services_par_reseau = {}
    for s in services_affiches:
        net = s["reseau"]
        services_par_reseau.setdefault(net, []).append(s)

    # === PERSONNALISATION DE LA BOUTIQUE ===
    # Nom de la boutique : personnalise sinon fallback sur le slug
    boutique_nom = revendeur.get("boutique_nom") or f"Boutique {slug.capitalize()}"

    # Slogan par defaut si non renseigne
    boutique_slogan = revendeur.get("boutique_slogan") or "Boostez vos reseaux sociaux des aujourd'hui"

    # Message d'accueil par defaut
    message_accueil = revendeur.get("boutique_message_accueil") or \
        "Followers, vues, likes, commentaires — livraison rapide, paiement Mobile Money, suivi en temps reel de vos commandes."

    # Theme et couleurs
    theme = revendeur.get("boutique_theme") or "bleu"
    couleur_principale, couleur_secondaire = THEMES.get(theme, THEMES["bleu"])

    # Surcharge manuelle des couleurs si definies
    if revendeur.get("boutique_couleur_principale"):
        couleur_principale = revendeur["boutique_couleur_principale"]
    if revendeur.get("boutique_couleur_secondaire"):
        couleur_secondaire = revendeur["boutique_couleur_secondaire"]

    # Infos de personnalisation
    boutique = {
        "nom": boutique_nom,
        "slogan": boutique_slogan,
        "logo_url": revendeur.get("boutique_logo_url"),
        "banniere_url": revendeur.get("boutique_banniere_url"),
        "theme": theme,
        "couleur_principale": couleur_principale,
        "couleur_secondaire": couleur_secondaire,
        "whatsapp": revendeur.get("boutique_whatsapp"),
        "email": revendeur.get("boutique_email"),
        "facebook": revendeur.get("boutique_facebook"),
        "instagram": revendeur.get("boutique_instagram"),
        "tiktok": revendeur.get("boutique_tiktok"),
        "telegram": revendeur.get("boutique_telegram"),
        "message_accueil": message_accueil,
        "a_propos": revendeur.get("boutique_a_propos"),
        "afficher_prix": revendeur.get("boutique_afficher_prix", True),
        "whatsapp_flottant": revendeur.get("boutique_whatsapp_flottant", True),
    }

    return render_template("boutique.html",
        revendeur=revendeur,
        boutique=boutique,
        services_par_reseau=services_par_reseau,
        slug=slug)