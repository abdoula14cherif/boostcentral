"""
Authentification Boost Central.
Version simplifiee - SECRETS EXTERNALISES.
"""
import logging
import requests
import secrets
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from app.models.forms import LoginForm, RegisterForm, ForgotPasswordForm
from app.models.security import set_session, clear_session
from app.models.database import get_profile_by_slug, rattacher_client_revendeur
from app import limiter

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)


# ═══════════════════════════════════════════════════════════════
# CONFIGURATION (via variables d'environnement)
# ═══════════════════════════════════════════════════════════════

def _supabase_url():
    return current_app.config.get("SUPABASE_URL", "").rstrip("/")


def _supabase_anon_key():
    return current_app.config.get("SUPABASE_ANON_KEY", "")


def _supabase_service_key():
    return current_app.config.get("SUPABASE_SERVICE_KEY", "")


def _auth_url():
    return _supabase_url() + "/auth/v1"


def _headers():
    """Headers pour les requetes publiques (anon key)."""
    return {
        "apikey": _supabase_anon_key(),
        "Content-Type": "application/json",
    }


def _admin_headers():
    """Headers pour les requetes admin (service key)."""
    key = _supabase_service_key()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

from app.models.mailer import email_admin_nouvelle_inscription


def _crediter_parrain(ref_code, new_user_id):
    """Enregistre la relation parrain/filleul."""
    if not ref_code:
        return False
    try:
        supabase_url = _supabase_url()
        headers = _admin_headers()

        r = requests.get(
            f"{supabase_url}/rest/v1/profiles?referral_code=eq.{ref_code}&limit=1",
            headers=headers,
            timeout=10
        )
        data = r.json()
        if not data:
            return False

        parrain = data[0]
        parrain_id = parrain["id"]
        referral_count = parrain.get("referral_count", 0) or 0

        requests.patch(
            f"{supabase_url}/rest/v1/profiles?id=eq.{parrain_id}",
            json={"referral_count": referral_count + 1},
            headers=headers,
            timeout=10
        )
        requests.patch(
            f"{supabase_url}/rest/v1/profiles?id=eq.{new_user_id}",
            json={"referred_by": ref_code},
            headers=headers,
            timeout=10
        )
        return True
    except Exception as e:
        logger.error(f"crediter_parrain: {type(e).__name__}")
        return False


def _ensure_profile(user_id, email, full_name, country):
    """Cree le profil s'il n'existe pas."""
    try:
        supabase_url = _supabase_url()
        headers = _admin_headers()

        r = requests.get(
            f"{supabase_url}/rest/v1/profiles?id=eq.{user_id}&limit=1",
            headers=headers,
            timeout=10
        )
        data = r.json()
        if not data:
            requests.post(
                f"{supabase_url}/rest/v1/profiles",
                json={
                    "id": user_id,
                    "email": email,
                    "full_name": full_name,
                    "country": country,
                    "balance": 0,
                },
                headers=headers,
                timeout=10
            )
    except Exception as e:
        logger.error(f"ensure_profile: {type(e).__name__}")


# ═══════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    ref_code = request.args.get("ref", "").strip().upper()
    if ref_code:
        session["ref_code"] = ref_code

    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    reg_form = RegisterForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        try:
            r = requests.post(
                f"{_auth_url()}/token?grant_type=password",
                json={"email": email, "password": password},
                headers=_headers(),
                timeout=15
            )
            data = r.json()

            if r.status_code == 200 and "access_token" in data:
                user = data.get("user", {})
                meta = user.get("user_metadata", {})
                full_name = meta.get("full_name", "")
                set_session(user["id"], user["email"], full_name)
                next_url = session.pop("next_url", None)
                return redirect(next_url or url_for("dashboard.index"))
            else:
                msg = data.get("error_description", data.get("msg", "Email ou mot de passe incorrect."))
                flash(f"Erreur : {msg}", "error")
        except requests.Timeout:
            flash("Le serveur met trop de temps a repondre.", "error")
        except Exception as e:
            logger.error(f"login error: {type(e).__name__}")
            flash("Erreur serveur. Reessayez.", "error")

    return render_template("auth/login.html", form=form, reg_form=reg_form)


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per hour")
def register():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    reg_form = RegisterForm()

    if reg_form.validate_on_submit():
        email = reg_form.email.data.strip().lower()
        password = reg_form.password.data
        full_name = reg_form.full_name.data.strip()
        country = reg_form.country.data.strip() if reg_form.country.data else "CM"
        ref_code = session.get("ref_code")
        revendeur_slug = session.get("revendeur_slug")

        try:
            r = requests.post(
                f"{_auth_url()}/signup",
                json={
                    "email": email,
                    "password": password,
                    "data": {"full_name": full_name, "country": country}
                },
                headers=_headers(),
                timeout=15
            )
            data = r.json()

            if r.status_code in (200, 201):
                if "access_token" in data:
                    user = data.get("user", {})
                    user_id = user.get("id") or data.get("id")
                    _ensure_profile(user_id, email, full_name, country)
                    if _crediter_parrain(ref_code, user_id):
                        session.pop("ref_code", None)
                    if revendeur_slug:
                        rev = get_profile_by_slug(revendeur_slug)
                        if rev and rattacher_client_revendeur(rev["id"], user_id):
                            session.pop("revendeur_slug", None)
                    set_session(user_id, email, full_name)
                    try:
                        email_admin_nouvelle_inscription(email, full_name, country)
                    except Exception:
                        pass
                    flash(f"Bienvenue {full_name.split()[0]} !", "success")
                    return redirect(url_for("dashboard.index"))
                else:
                    if "id" in data:
                        _ensure_profile(data["id"], email, full_name, country)
                        if _crediter_parrain(ref_code, data["id"]):
                            session.pop("ref_code", None)
                    flash("Compte cree ! Connectez-vous.", "info")
                    return redirect(url_for("auth.login"))
            else:
                msg = data.get("msg", data.get("error_description", data.get("message", "Erreur.")))
                if "already" in str(msg).lower():
                    flash("Email deja utilise. Connectez-vous.", "error")
                else:
                    flash(f"Erreur : {msg}", "error")
        except Exception as e:
            logger.error(f"register error: {type(e).__name__}")
            flash("Erreur serveur.", "error")
    else:
        for field, errors in reg_form.errors.items():
            for error in errors:
                flash(f"{error}", "error")

    return render_template("auth/login.html", form=form, reg_form=reg_form)


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        clear_session()
        flash("Deconnecte.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/logout.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        try:
            requests.post(
                f"{_auth_url()}/recover",
                json={"email": email},
                headers=_headers(),
                timeout=10
            )
            flash("Lien envoye ! Verifiez vos spams.", "info")
            return redirect(url_for("auth.login"))
        except Exception:
            flash("Erreur.", "error")
    return render_template("auth/forgot_password.html", form=form)


# ═══════════════════════════════════════════════════════════════
# SSO VERS RESELLER — Génère un code temporaire
# ═══════════════════════════════════════════════════════════════

@auth_bp.route("/sso-login")
@limiter.limit("20 per hour")
def sso_login():
    """Genere un code SSO temporaire et redirige vers Boost Reseller."""
    if "user_id" not in session:
        session["next_url"] = request.url
        flash("Connectez-vous pour devenir revendeur.", "info")
        return redirect(url_for("auth.login"))

    return_url = request.args.get("redirect", "").strip()
    if not return_url:
        return_url = "https://reseller.boostcentral.world/auth/sso"

    # Whitelist
    if not return_url.startswith("https://reseller.boostcentral.world/"):
        flash("Lien de redirection invalide.", "error")
        return redirect(url_for("dashboard.index"))

    # Genere un code temporaire
    code = secrets.token_urlsafe(32)[:40]
    expires = (datetime.now(timezone.utc) + timedelta(seconds=120)).isoformat()

    try:
        r = requests.post(
            f"{_supabase_url()}/rest/v1/sso_tokens",
            json={
                "code": code,
                "user_id": session["user_id"],
                "email": session.get("user_email", ""),
                "full_name": session.get("user_name", ""),
                "expires_at": expires,
            },
            headers=_admin_headers(),
            timeout=10
        )

        if r.status_code not in (200, 201):
            logger.error(f"SSO erreur : {r.status_code}")
            flash("Erreur lors de la connexion SSO. Reessayez.", "error")
            return redirect(url_for("dashboard.index"))

        sep = "&" if "?" in return_url else "?"
        return redirect(f"{return_url}{sep}code={code}")

    except Exception as e:
        logger.error(f"SSO exception : {type(e).__name__}")
        flash("Erreur lors de la generation du lien SSO.", "error")
        return redirect(url_for("dashboard.index"))