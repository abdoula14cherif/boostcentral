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
            logger.info(f"LOGIN status={r.status_code} data={data}")
            if r.status_code == 200 and "access_token" in data:
                user = data.get("user", {})
                meta = user.get("user_metadata", {})
                full_name = meta.get("full_name", "")
                set_session(user["id"], user["email"], full_name)
                next_url = session.pop("next_url", None)
                return redirect(next_url or url_for("dashboard.index"))
            else:
                msg = data.get("error_description", data.get("msg", data.get("message", "")))
                flash(f"Erreur : {msg}", "error")
        except Exception as e:
            logger.error(f"login error: {e}")
            flash("Erreur serveur.", "error")
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
            logger.info(f"REGISTER status={r.status_code} data={data}")
            if r.status_code == 200 and "id" in data:
                if data.get("access_token"):
                    set_session(data["id"], data["email"], full_name)
                    flash(f"Bienvenue {full_name.split()[0]} !", "success")
                    return redirect(url_for("dashboard.index"))
                else:
                    flash("Compte cree ! Verifiez votre email.", "info")
                    return redirect(url_for("auth.login"))
            else:
                msg = data.get("msg", data.get("error_description", data.get("message", str(data))))
                flash(f"Erreur inscription : {msg}", "error")
        except Exception as e:
            logger.error(f"register error: {e}")
            flash(f"Erreur serveur : {e}", "error")
    else:
        for field, errors in reg_form.errors.items():
            for error in errors:
                flash(f"{field}: {error}", "error")
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
