import logging
import secrets
import requests as req
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile

logger = logging.getLogger(__name__)

parrainage_bp = Blueprint("parrainage", __name__)

TAUX_COMMISSION_PARRAINAGE = 0.05  # 5% de chaque recharge REELLEMENT payee par le filleul
MIN_CONVERSION = 50  # 50 points minimum pour convertir


def _headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}


def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path


def get_or_create_code(user_id, email):
    """Recupere ou cree le code de parrainage."""
    try:
        r = req.get(_url(f"profiles?id=eq.{user_id}&select=referral_code,points,referral_count,referred_by"), headers=_headers())
        data = r.json()
        if not data:
            return None
        profile = data[0]
        if not profile.get("referral_code"):
            code = secrets.token_hex(4).upper()
            req.patch(_url(f"profiles?id=eq.{user_id}"), json={"referral_code": code}, headers=_headers())
            profile["referral_code"] = code
        return profile
    except Exception as e:
        logger.error(f"get_or_create_code: {e}")
        return None


def crediter_commission_recharge(filleul_id, montant_recharge_fcfa):
    """
    Credite le parrain d'une commission de TAUX_COMMISSION_PARRAINAGE (5%)
    UNIQUEMENT sur de l'argent reellement recu (appelee depuis le webhook,
    apres qu'un paiement de recharge ait ete confirme).

    Le parrain ne touche donc jamais plus que ce que Cherif vient d'encaisser :
    le systeme est auto-finance et ne peut jamais faire perdre d'argent,
    contrairement a un bonus fixe verse a l'inscription.
    """
    try:
        r = req.get(_url(f"profiles?id=eq.{filleul_id}&select=referred_by"), headers=_headers())
        data = r.json()
        if not data or not data[0].get("referred_by"):
            return

        ref_code = data[0]["referred_by"]

        rp = req.get(_url(f"profiles?referral_code=eq.{ref_code}&limit=1&select=id,points,email"), headers=_headers())
        parrain_data = rp.json()
        if not parrain_data:
            return
        parrain = parrain_data[0]

        commission = round(montant_recharge_fcfa * TAUX_COMMISSION_PARRAINAGE)
        if commission <= 0:
            return

        points_actuels = parrain.get("points", 0) or 0
        req.patch(_url(f"profiles?id=eq.{parrain['id']}"),
                  json={"points": points_actuels + commission},
                  headers=_headers())

        logger.info(f"Commission parrainage: {parrain['email']} +{commission} points "
                    f"(5% de {montant_recharge_fcfa} FCFA recharges par le filleul {filleul_id})")
    except Exception as e:
        logger.error(f"crediter_commission_recharge: {e}")


@parrainage_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_or_create_code(user["id"], user["email"])
    if not profile:
        flash("Erreur chargement profil.", "error")
        return redirect(url_for("dashboard.index"))

    code = profile.get("referral_code", "")
    points = profile.get("points", 0) or 0
    referral_count = profile.get("referral_count", 0) or 0
    base_url = request.host_url.rstrip("/")
    lien_parrainage = f"{base_url}/auth/login?ref={code}"

    return render_template("dashboard/parrainage.html",
        user=user,
        code=code,
        points=points,
        referral_count=referral_count,
        lien_parrainage=lien_parrainage,
        taux_commission=int(TAUX_COMMISSION_PARRAINAGE * 100),
        min_conversion=MIN_CONVERSION,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])


@parrainage_bp.route("/convertir", methods=["POST"])
@login_required
def convertir():
    user = get_current_user()
    profile = get_profile(user["id"])
    if not profile:
        flash("Profil introuvable.", "error")
        return redirect(url_for("parrainage.index"))

    points = profile.get("points", 0) or 0
    if points < MIN_CONVERSION:
        flash(f"Minimum {MIN_CONVERSION} points requis. Vous avez {points} points.", "error")
        return redirect(url_for("parrainage.index"))

    montant_fcfa = points
    new_balance = (profile.get("balance", 0) or 0) + montant_fcfa

    try:
        req.patch(_url(f"profiles?id=eq.{user['id']}"),
                  json={"points": 0, "balance": new_balance},
                  headers=_headers())
        flash(f"✅ {points} points convertis en {montant_fcfa:,.0f} FCFA !", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")

    return redirect(url_for("parrainage.index"))
