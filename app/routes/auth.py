import logging
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from app.models.forms import LoginForm, RegisterForm, ForgotPasswordForm
from app.models.security import set_session, clear_session
from app import limiter

logger = logging.getLogger(__name__)
auth_bp = Blueprint("auth", __name__)

def _auth_url():
    return current_app.config["SUPABASE_URL"] + "/auth/v1"

def _headers():
    return {"apikey": current_app.config["SUPABASE_ANON_KEY"], "Content-Type": "application/json"}

def _admin_headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY") or current_app.config["SUPABASE_ANON_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}

def _ensure_profile(user_id, email, full_name, country):
    """Cree le profil si il n'existe pas encore."""
    try:
        url = current_app.config["SUPABASE_URL"] + "/rest/v1/"
        r = requests.get(f"{url}profiles?id=eq.{user_id}&limit=1", headers=_admin_headers())
        data = r.json()
        if not data:
            requests.post(f"{url}profiles",
                json={"id": user_id, "email": email, "full_name": full_name, "country": country, "balance": 0},
                headers=_admin_headers())
            logger.info(f"Profil cree pour {email}")
    except Exception as e:
        logger.error(f"ensure_profile error: {e}")

@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    if "user_id" in session:
        return redirect(url_for("dashboard.index"))
    form = LoginForm()
    reg_form = RegisterForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        try:
            r = requests.post(f"{_auth_url()}/token?grant_type=password",
                json={"email": email, "password": password}, headers=_headers())
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
        except Exception as e:
            logger.error(f"login error: {e}")
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
        try:
            r = requests.post(f"{_auth_url()}/signup",
                json={"email": email, "password": password,
                      "data": {"full_name": full_name, "country": country}},
                headers=_headers())
            data = r.json()
            logger.info(f"REGISTER status={r.status_code}")

            if r.status_code in (200, 201):
                if "access_token" in data:
                    user = data.get("user", {})
                    user_id = user.get("id") or data.get("id")
                    # Creer le profil manuellement
                    _ensure_profile(user_id, email, full_name, country)
                    set_session(user_id, email, full_name)
                    flash(f"Bienvenue {full_name.split()[0]} !", "success")
                    return redirect(url_for("dashboard.index"))
                elif "id" in data:
                    _ensure_profile(data["id"], email, full_name, country)
                    flash("Compte cree ! Verifiez votre email pour confirmer.", "info")
                    return redirect(url_for("auth.login"))
                else:
                    flash("Compte cree ! Connectez-vous.", "info")
                    return redirect(url_for("auth.login"))
            else:
                msg = data.get("msg", data.get("error_description", data.get("message", "Erreur inscription.")))
                if "already" in str(msg).lower():
                    flash("Email deja utilise. Connectez-vous.", "error")
                else:
                    flash(f"Erreur : {msg}", "error")
        except Exception as e:
            logger.error(f"register error: {e}")
            flash("Erreur serveur. Reessayez.", "error")
    else:
        for field, errors in reg_form.errors.items():
            for error in errors:
                flash(f"{error}", "error")
    return render_template("auth/login.html", form=form, reg_form=reg_form)

@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    if request.method == "POST":
        clear_session()
        flash("Deconnecte avec succes.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/logout.html")

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
@limiter.limit("3 per hour")
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        try:
            requests.post(f"{_auth_url()}/recover",
                json={"email": email}, headers=_headers())
            flash("Lien envoye ! Verifiez vos spams.", "info")
            return redirect(url_for("auth.login"))
        except Exception as e:
            flash("Erreur. Reessayez.", "error")
    return render_template("auth/forgot_password.html", form=form)
