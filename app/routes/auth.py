import logging
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, session, request, current_app
from app.models.forms import LoginForm, RegisterForm, ForgotPasswordForm
from app.models.security import set_session, clear_session
from app.models.database import get_profile_by_slug, rattacher_client_revendeur
from app import limiter

logger = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)

SUPABASE_URL = "https://yyecncgrmtbmvvwitwmf.supabase.co"
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl5ZWNuY2dybXRibXZ2d2l0d21mIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzk4MjgyMzUsImV4cCI6MjA5NTQwNDIzNX0.UA_K5k5VeX53WXFao-hQlXhM4gF3Kj8OMVa0T8yfKaM"


def _auth_url():
    return SUPABASE_URL + "/auth/v1"


def _headers():
    return {"apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json"}


def _admin_headers():
    SERVICE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl5ZWNuY2dybXRibXZ2d2l0d21mIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTgyODIzNSwiZXhwIjoyMDk1NDA0MjM1fQ.4x5GwPi2pjU6kuBOvKdsL3GzMFFzyBlvL5ot8dkgc2g"
    return {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json", "Prefer": "return=representation"}


from app.models.mailer import email_admin_nouvelle_inscription


def _crediter_parrain(ref_code, new_user_id):
    """
    Enregistre la relation de parrainage (filleul -> parrain) SANS credit
    immediat. Le parrain ne gagnera une commission que plus tard, quand le
    filleul recharge REELLEMENT (voir crediter_commission_recharge dans
    parrainage.py, appelee depuis webhook.py) - ainsi Cherif ne verse jamais
    d'argent qu'il n'a pas deja encaisse.
    """
    if not ref_code:
        return
    try:
        import requests as req
        SUPABASE_URL_P = "https://yyecncgrmtbmvvwitwmf.supabase.co"
        SERVICE_KEY_P = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inl5ZWNuY2dybXRibXZ2d2l0d21mIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3OTgyODIzNSwiZXhwIjoyMDk1NDA0MjM1fQ.4x5GwPi2pjU6kuBOvKdsL3GzMFFzyBlvL5ot8dkgc2g"
        headers = {"apikey": SERVICE_KEY_P, "Authorization": f"Bearer {SERVICE_KEY_P}", "Content-Type": "application/json"}

        # Trouver le parrain
        r = req.get(f"{SUPABASE_URL_P}/rest/v1/profiles?referral_code=eq.{ref_code}&limit=1", headers=headers)
        data = r.json()
        if not data:
            logger.warning(f"crediter_parrain: aucun parrain trouve pour le code {ref_code}")
            return False
        parrain = data[0]
        parrain_id = parrain["id"]
        referral_count = parrain.get("referral_count", 0) or 0

        # Incrementer le compteur de filleuls du parrain (stats uniquement, pas de credit)
        req.patch(f"{SUPABASE_URL_P}/rest/v1/profiles?id=eq.{parrain_id}",
                  json={"referral_count": referral_count + 1},
                  headers=headers)

        # Enregistrer le parrain chez le filleul (sert de base a la commission future)
        req.patch(f"{SUPABASE_URL_P}/rest/v1/profiles?id=eq.{new_user_id}",
                  json={"referred_by": ref_code},
                  headers=headers)

        logger.info(f"Filleul enregistre pour le parrain {parrain.get('email')} (code {ref_code}) - commission a venir sur recharge")
        return True
    except Exception as e:
        logger.error(f"crediter_parrain: {e}")
        return False


def _ensure_profile(user_id, email, full_name, country):
    try:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/profiles?id=eq.{user_id}&limit=1", headers=_admin_headers())
        data = r.json()
        if not data:
            requests.post(f"{SUPABASE_URL}/rest/v1/profiles",
                json={"id": user_id, "email": email, "full_name": full_name, "country": country, "balance": 0},
                headers=_admin_headers())
    except Exception as e:
        logger.error(f"ensure_profile: {e}")


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20 per minute")
def login():
    # On capture le code de parrainage AVANT toute redirection, y compris
    # si le visiteur est deja connecte (son propre compte) - sinon le code
    # est perdu silencieusement pour tous les visiteurs deja connectes.
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
        # On NE retire PAS le code de la session ici : si l'inscription
        # echoue (email deja utilise, erreur serveur...), l'utilisateur doit
        # pouvoir reessayer sans perdre son code de parrainage.
        ref_code = session.get("ref_code")
        revendeur_slug = session.get("revendeur_slug")

        try:
            r = requests.post(f"{_auth_url()}/signup",
                json={"email": email, "password": password,
                      "data": {"full_name": full_name, "country": country}},
                headers=_headers())
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
                    except:
                        pass
                    flash(f"Bienvenue {full_name.split()[0]} !", "success")
                    return redirect(url_for("dashboard.index"))
                else:
                    if "id" in data:
                        _ensure_profile(data["id"], email, full_name, country)
                        if _crediter_parrain(ref_code, data["id"]):
                            session.pop("ref_code", None)
                        if revendeur_slug:
                            rev = get_profile_by_slug(revendeur_slug)
                            if rev and rattacher_client_revendeur(rev["id"], data["id"]):
                                session.pop("revendeur_slug", None)
                    flash("Compte cree ! Connectez-vous.", "info")
                    return redirect(url_for("auth.login"))
            else:
                msg = data.get("msg", data.get("error_description", data.get("message", "Erreur.")))
                if "already" in str(msg).lower():
                    flash("Email deja utilise. Connectez-vous.", "error")
                else:
                    flash(f"Erreur : {msg}", "error")
        except Exception as e:
            logger.error(f"register error: {e}")
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
            requests.post(f"{_auth_url()}/recover",
                json={"email": email}, headers=_headers())
            flash("Lien envoye ! Verifiez vos spams.", "info")
            return redirect(url_for("auth.login"))
        except Exception as e:
            flash("Erreur.", "error")
    return render_template("auth/forgot_password.html", form=form)
