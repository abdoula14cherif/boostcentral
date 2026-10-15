"""
Helpers de securite Boost Central : sessions, decorateurs, anti-bot, honeypot.
SÉCURITÉ SÉVÈRE : sessions, bannissement, detection bots.
"""
import logging
import time
from functools import wraps

from flask import (
    session, redirect, url_for, flash, current_app, request, abort
)

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "abdoula13cherif@gmail.com"

# Duree de session
SESSION_MAX_AGE = 24 * 3600  # 24h
SESSION_INACTIVITY = 8 * 3600  # 8h


# ═══════════════════════════════════════════════════════════════
# DETECTION DE BOTS
# ═══════════════════════════════════════════════════════════════

_BOTS_CONNUS = (
    "curl", "wget", "python-requests", "python-urllib", "scrapy",
    "httrack", "ahrefs", "semrushbot", "mj12bot", "dotbot",
    "petalbot", "bytespider", "gptbot", "chatgpt", "claudebot",
    "googlebot-news", "yandexbot", "baiduspider", "sogou",
    "exabot", "facebot", "ia_archiver", "netcraft", "zgrab",
    "masscan", "nmap", "sqlmap", "nikto", "acunetix", "nessus",
    "openvas", "havij", "whatweb", "dirbuster", "gobuster",
    "wfuzz", "hydra", "medusa", "patator",
)

_UA_AUTORISES = (
    "boostreseller-python/",
    "boostreseller-js/",
)


def est_bot():
    """Detecte les bots via User-Agent."""
    ua = (request.headers.get("User-Agent") or "").lower().strip()
    if not ua:
        return True
    if any(a in ua for a in _UA_AUTORISES):
        return False
    if any(bot in ua for bot in _BOTS_CONNUS):
        return True
    if len(ua) < 15:
        return True
    return False


def est_bot_fort():
    """Detection renforcee : UA + headers suspects."""
    if est_bot():
        return True
    if not request.headers.get("Accept-Language"):
        return True
    if not request.headers.get("Accept"):
        return True
    return False


def verifier_honeypot():
    """
    Verifie que le champ cache 'website' n'a pas ete rempli.
    Retourne True si OK (pas de bot), False si bot.
    """
    honeypot = request.form.get("website", "").strip()
    return not honeypot


def _log_bot(endpoint):
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "")).split(",")[0].strip()
    ua = (request.headers.get("User-Agent") or "")[:120]
    logger.warning(f"[BOT DETECTE] endpoint={endpoint} | IP={ip} | UA={ua}")


# ═══════════════════════════════════════════════════════════════
# SESSIONS
# ═══════════════════════════════════════════════════════════════

def set_session(user_id, user_email, full_name=""):
    """Cree une session securisee."""
    session.clear()
    session.permanent = True
    session["user_id"] = user_id
    session["user_email"] = user_email.strip().lower()
    session["user_name"] = full_name or user_email.split("@")[0]
    session["login_at"] = time.time()
    session["last_activity"] = time.time()


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


def _session_valide():
    """Verifie la duree et l'inactivite."""
    if "user_id" not in session:
        return False
    login_at = session.get("login_at", 0)
    now = time.time()
    if now - login_at > SESSION_MAX_AGE:
        return False
    last_activity = session.get("last_activity", login_at)
    if now - last_activity > SESSION_INACTIVITY:
        return False
    return True


def _verifier_banni(user_id):
    """Verifie si l'utilisateur est banni via Supabase."""
    try:
        import requests
        url = current_app.config.get("SUPABASE_URL", "https://yyecncgrmtbmvvwitwmf.supabase.co")
        key = current_app.config.get("SUPABASE_SERVICE_KEY", "")
        if not key:
            return False
        r = requests.get(
            f"{url}/rest/v1/profiles?id=eq.{user_id}&select=banni&limit=1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=5
        )
        data = r.json()
        if isinstance(data, list) and data:
            return bool(data[0].get("banni"))
    except Exception as e:
        logger.error(f"_verifier_banni: {type(e).__name__}")
    return False


# ═══════════════════════════════════════════════════════════════
# DECORATEURS
# ═══════════════════════════════════════════════════════════════

def login_required(f):
    """Oblige l'utilisateur a etre connecte."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            session["next_url"] = request.url
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))

        if not _session_valide():
            clear_session()
            flash("Votre session a expire. Reconnectez-vous.", "warning")
            return redirect(url_for("auth.login"))

        # Verifie le bannissement (1 fois par minute max)
        last_check = session.get("_ban_check", 0)
        now = time.time()
        if now - last_check > 60:
            if _verifier_banni(session["user_id"]):
                clear_session()
                flash("Votre compte a ete suspendu. Contactez le support.", "error")
                return redirect(url_for("auth.login"))
            session["_ban_check"] = now

        session["last_activity"] = now
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Reserve l'acces aux administrateurs."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            session["next_url"] = request.url
            flash("Veuillez vous connecter.", "warning")
            return redirect(url_for("auth.login"))

        if not _session_valide():
            clear_session()
            flash("Votre session a expire. Reconnectez-vous.", "warning")
            return redirect(url_for("auth.login"))

        user_email = (session.get("user_email") or "").strip().lower()
        logger.info(f"Admin check email: [{user_email}]")
        if user_email != ADMIN_EMAIL.lower():
            logger.warning(f"Acces admin refuse: {user_email}")
            abort(403)

        session["last_activity"] = time.time()
        return f(*args, **kwargs)
    return decorated


def bot_blocked(f):
    """Bloque les bots sur les routes sensibles."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if est_bot_fort():
            _log_bot(request.path)
            return "Forbidden", 403
        return f(*args, **kwargs)
    return decorated