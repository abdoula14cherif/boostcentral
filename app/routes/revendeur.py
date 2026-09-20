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
    return render_template("dashboard/revendeur.html",
        user=user, profile=profile, prix_activation=PRIX_ACTIVATION)


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
