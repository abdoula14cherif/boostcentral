import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_supabase_admin, update_balance
import requests as req

logger = logging.getLogger(__name__)
gagner_bp = Blueprint("gagner", __name__)

POINTS_PAR_PUB = 10        # Points gagnes par pub regardee
FCFA_PAR_POINT = 1         # 1 point = 1 FCFA
MIN_CONVERSION = 500       # Minimum 500 points pour convertir

@gagner_bp.route("/")
@login_required
def index():
    from flask import render_template
    return render_template("dashboard/maintenance.html")

@gagner_bp.route("/old")
@login_required
def index_old():
    user = get_current_user()
    profile = get_profile(user["id"])
    points = profile.get("points", 0) if profile else 0
    balance = profile.get("balance", 0) if profile else 0
    return render_template("dashboard/gagner.html",
        user=user, profile=profile, points=points,
        balance=balance,
        points_par_pub=POINTS_PAR_PUB,
        fcfa_par_point=FCFA_PAR_POINT,
        min_conversion=MIN_CONVERSION,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])

@gagner_bp.route("/crediter-points", methods=["POST"])
@login_required
def crediter_points():
    """Credite les points apres qu une pub a ete regardee."""
    user = get_current_user()
    try:
        sb = req.get(
            current_app.config["SUPABASE_URL"] + f"/rest/v1/profiles?id=eq.{user['id']}&limit=1",
            headers={
                "apikey": current_app.config["SUPABASE_SERVICE_KEY"],
                "Authorization": f"Bearer {current_app.config['SUPABASE_SERVICE_KEY']}"
            }
        )
        data = sb.json()
        profile = data[0] if data else {}
        points_actuels = profile.get("points", 0) or 0
        nouveaux_points = points_actuels + POINTS_PAR_PUB

        req.patch(
            current_app.config["SUPABASE_URL"] + f"/rest/v1/profiles?id=eq.{user['id']}",
            json={"points": nouveaux_points},
            headers={
                "apikey": current_app.config["SUPABASE_SERVICE_KEY"],
                "Authorization": f"Bearer {current_app.config['SUPABASE_SERVICE_KEY']}",
                "Content-Type": "application/json"
            }
        )
        return {"ok": True, "points": nouveaux_points}
    except Exception as e:
        logger.error(f"crediter_points: {e}")
        return {"ok": False}, 500

@gagner_bp.route("/convertir", methods=["POST"])
@login_required
def convertir():
    """Convertit les points en solde FCFA."""
    user = get_current_user()
    profile = get_profile(user["id"])
    if not profile:
        flash("Profil introuvable.", "error")
        return redirect(url_for("gagner.index"))

    points = profile.get("points", 0) or 0

    if points < MIN_CONVERSION:
        flash(f"Minimum {MIN_CONVERSION} points requis pour convertir. Vous avez {points} points.", "error")
        return redirect(url_for("gagner.index"))

    montant_fcfa = points * FCFA_PAR_POINT
    new_balance = (profile.get("balance", 0) or 0) + montant_fcfa

    try:
        headers = {
            "apikey": current_app.config["SUPABASE_SERVICE_KEY"],
            "Authorization": f"Bearer {current_app.config['SUPABASE_SERVICE_KEY']}",
            "Content-Type": "application/json"
        }
        req.patch(
            current_app.config["SUPABASE_URL"] + f"/rest/v1/profiles?id=eq.{user['id']}",
            json={"points": 0, "balance": new_balance},
            headers=headers
        )
        flash(f"✅ {points} points convertis en {montant_fcfa:,.0f} FCFA !", "success")
        logger.info(f"Conversion: {user['email']} - {points} points = {montant_fcfa} FCFA")
    except Exception as e:
        logger.error(f"convertir: {e}")
        flash("Erreur lors de la conversion.", "error")

    return redirect(url_for("gagner.index"))
