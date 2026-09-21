import re
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, debit_balance, slug_deja_pris, activer_revendeur

logger = logging.getLogger(__name__)
revendeur_bp = Blueprint("revendeur", __name__)

PRIX_ACTIVATION = 12000


def _slug_valide(slug):
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{2,28}[a-z0-9]", slug))


@revendeur_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    base_url = request.host_url.rstrip("/")
    return render_template("dashboard/revendeur.html",
        user=user, profile=profile, prix_activation=PRIX_ACTIVATION, base_url=base_url)


@revendeur_bp.route("/activer", methods=["POST"])
@login_required
def activer():
    user = get_current_user()
    profile = get_profile(user["id"])

    if profile and profile.get("est_revendeur"):
        flash("Vous etes deja revendeur.", "info")
        return redirect(url_for("revendeur.index"))

    slug = request.form.get("slug", "").strip().lower()
    modele = request.form.get("modele", "")

    if not _slug_valide(slug):
        flash("Identifiant invalide : 3 a 30 caracteres, lettres minuscules/chiffres/tirets uniquement.", "error")
        return redirect(url_for("revendeur.index"))

    if modele not in ("marge", "commission"):
        flash("Choisissez un modele de gain.", "error")
        return redirect(url_for("revendeur.index"))

    if slug_deja_pris(slug):
        flash("Cet identifiant est deja pris, choisissez-en un autre.", "error")
        return redirect(url_for("revendeur.index"))

    balance = profile.get("balance", 0) if profile else 0
    if balance < PRIX_ACTIVATION:
        flash(f"Solde insuffisant. Il faut {PRIX_ACTIVATION:,.0f} FCFA pour activer le mode revendeur (solde actuel : {balance:,.0f} FCFA).", "error")
        return redirect(url_for("revendeur.index"))

    new_balance = debit_balance(user["id"], PRIX_ACTIVATION)
    if new_balance is None:
        flash("Erreur lors du debit.", "error")
        return redirect(url_for("revendeur.index"))

    commission_pct = 0.10 if modele == "commission" else 0.0
    ok = activer_revendeur(user["id"], slug, modele, commission_pct)

    if ok:
        flash("🎉 Bienvenue dans le programme revendeur !", "success")
        return redirect(url_for("revendeur.index") + "?active=1")
    else:
        flash("Erreur lors de l'activation. Contactez le support.", "error")
        return redirect(url_for("revendeur.index"))


@revendeur_bp.route("/prix")
@login_required
def prix():
    from app.models.database import get_active_services, get_revendeur_prix_all
    user = get_current_user()
    profile = get_profile(user["id"])

    if not profile or not profile.get("est_revendeur"):
        flash("Vous devez d'abord activer le mode revendeur.", "error")
        return redirect(url_for("revendeur.index"))

    if profile.get("revendeur_modele") != "marge":
        flash("Cette page concerne uniquement le modele 'mes propres prix'.", "info")
        return redirect(url_for("revendeur.index"))

    services = get_active_services()
    mes_prix = {p["service_id"]: p["prix_fcfa"] for p in get_revendeur_prix_all(user["id"])}

    return render_template("dashboard/revendeur_prix.html",
        user=user, profile=profile, services=services, mes_prix=mes_prix)


@revendeur_bp.route("/prix/enregistrer", methods=["POST"])
@login_required
def prix_enregistrer():
    from app.models.database import set_revendeur_prix, get_service_by_id
    user = get_current_user()
    profile = get_profile(user["id"])

    if not profile or profile.get("revendeur_modele") != "marge":
        flash("Action non autorisee.", "error")
        return redirect(url_for("revendeur.index"))

    service_id = request.form.get("service_id", "")
    prix_fcfa = request.form.get("prix_fcfa", "").strip()

    try:
        service_id = int(service_id)
        prix_fcfa = float(prix_fcfa)
    except:
        flash("Valeurs invalides.", "error")
        return redirect(url_for("revendeur.prix"))

    service = get_service_by_id(service_id)
    if not service:
        flash("Service introuvable.", "error")
        return redirect(url_for("revendeur.prix"))

    if prix_fcfa < float(service["prix_fcfa"]):
        flash(f"Votre prix doit etre superieur ou egal au prix de base ({service['prix_fcfa']} FCFA), sinon vous perdez de l'argent.", "error")
        return redirect(url_for("revendeur.prix"))

    ok = set_revendeur_prix(user["id"], service_id, prix_fcfa)
    if ok:
        flash("Prix enregistre.", "success")
    else:
        flash("Erreur lors de l'enregistrement du prix (verifie que la table revendeur_prix existe bien dans Supabase).", "error")
    return redirect(url_for("revendeur.prix"))


@revendeur_bp.route("/clients")
@login_required
def clients():
    from app.models.database import get_revendeur_clients_detail, get_revendeur_gains_total
    user = get_current_user()
    profile = get_profile(user["id"])

    if not profile or not profile.get("est_revendeur"):
        flash("Vous devez d'abord activer le mode revendeur.", "error")
        return redirect(url_for("revendeur.index"))

    mes_clients = get_revendeur_clients_detail(user["id"])
    gains_total = get_revendeur_gains_total(user["id"])
    base_url = request.host_url.rstrip("/")

    return render_template("dashboard/revendeur_clients.html",
        user=user, profile=profile, mes_clients=mes_clients, gains_total=gains_total, base_url=base_url)


@revendeur_bp.route("/commandes")
@login_required
def commandes():
    from app.models.database import get_revendeur_orders, get_revendeur_gains_total
    user = get_current_user()
    profile = get_profile(user["id"])

    if not profile or not profile.get("est_revendeur"):
        flash("Vous devez d'abord activer le mode revendeur.", "error")
        return redirect(url_for("revendeur.index"))

    orders = get_revendeur_orders(user["id"], limit=200)
    gains_total = get_revendeur_gains_total(user["id"])

    return render_template("dashboard/revendeur_commandes.html",
        user=user, profile=profile, orders=orders, gains_total=gains_total)
