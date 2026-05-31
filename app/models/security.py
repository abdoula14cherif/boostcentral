import logging
from functools import wraps
from flask import session, redirect, url_for, flash, current_app, request, abort

logger = logging.getLogger(__name__)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            session["next_url"] = request.url
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))
        user_email = session.get("user_email", "")
        admin_email = current_app.config.get("ADMIN_EMAIL", "")
        if user_email.lower() != admin_email.lower():
            logger.warning(f"Acces admin refuse pour {user_email}")
            abort(403)
        return f(*args, **kwargs)
    return decorated

def set_session(user_id, user_email, full_name=""):
    session.permanent = True
    session["user_id"] = user_id
    session["user_email"] = user_email
    session["user_name"] = full_name or user_email.split("@")[0]

def clear_session():
    session.clear()

def get_current_user():
    if "user_id" not in session:
        return {}
    return {
        "id": session.get("user_id"),
        "email": session.get("user_email"),
        "name": session.get("user_name"),
    }
