"""
Factory Flask pour Boost Central.
SÉCURITÉ SÉVÈRE : headers, handler global, CSRF, limiter configurable.
MODE DEBUG TEMPORAIRE : affiche le traceback sur erreur 500.
"""
import os
import logging
import traceback
from flask import Flask, render_template, send_from_directory, request, redirect, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.exceptions import HTTPException
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
csrf = CSRFProtect()


def create_app(config_name="production"):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    from app.config import config_map
    app.config.from_object(config_map[config_name])

    # ⚠️ SÉCURITÉ : storage du rate limiter configurable
    if app.config.get("RATELIMIT_STORAGE_URI"):
        limiter.storage_uri = app.config["RATELIMIT_STORAGE_URI"]
    limiter.init_app(app)
    csrf.init_app(app)

    # ─── Enregistrement des blueprints ────────────────────────
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp
    from app.routes.recharge import recharge_bp
    from app.routes.webhook import webhook_bp
    from app.routes.gagner import gagner_bp
    from app.routes.admin_boostci import admin_boostci_bp
    from app.routes.auto import auto_bp
    from app.routes.admin_sync import admin_sync_bp
    from app.routes.parrainage import parrainage_bp
    from app.routes.admin_users import admin_users_bp
    from app.routes.api import api_bp
    from app.routes.relance import relance_bp
    from app.routes.support import support_bp
    from app.routes.revendeur import revendeur_bp
    from app.routes.boutique import boutique_bp
    from app.routes.vitrine import vitrine_bp
    from app.routes.affiliation import affiliation_bp
    from app.routes.vente import vente_bp
    from app.routes.admin_produits import admin_produits_bp
    from app.routes.admin_newsletter import admin_newsletter_bp
    from app.routes.admin_notifications import admin_notifications_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(recharge_bp, url_prefix="/recharge")
    app.register_blueprint(webhook_bp, url_prefix="/recharge")
    app.register_blueprint(gagner_bp, url_prefix="/gagner")
    app.register_blueprint(admin_boostci_bp, url_prefix="/admin/boostci")
    app.register_blueprint(auto_bp, url_prefix="/auto")
    app.register_blueprint(admin_sync_bp, url_prefix="/admin/sync")
    app.register_blueprint(parrainage_bp, url_prefix="/parrainage")
    app.register_blueprint(admin_users_bp, url_prefix="/admin/users")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(relance_bp, url_prefix="/cron")
    app.register_blueprint(support_bp, url_prefix="/support")
    app.register_blueprint(revendeur_bp, url_prefix="/revendeur")
    app.register_blueprint(boutique_bp)
    app.register_blueprint(vitrine_bp)
    app.register_blueprint(affiliation_bp, url_prefix="/affiliation")
    app.register_blueprint(vente_bp)
    app.register_blueprint(admin_produits_bp, url_prefix="/admin")
    app.register_blueprint(admin_newsletter_bp, url_prefix="/admin")
    app.register_blueprint(admin_notifications_bp, url_prefix="/admin")

    # ⚠️ SÉCURITÉ : CSRF exempt pour webhooks/API/cron
    csrf.exempt(webhook_bp)
    csrf.exempt(api_bp)
    csrf.exempt(relance_bp)

    # ─── Helper WhatsApp ──────────────────────────────────────
    from app.models.whatsapp import wa_link
    app.jinja_env.globals['wa_link'] = wa_link

    ROOT_DOMAIN = os.environ.get("ROOT_DOMAIN", "").lower().strip()

    @app.before_request
    def _detecter_sous_domaine_revendeur():
        if not ROOT_DOMAIN or request.path != "/":
            return None
        host = request.host.split(":")[0].lower()
        if host == ROOT_DOMAIN or host == f"www.{ROOT_DOMAIN}" or host.endswith(".vercel.app"):
            return None
        if host.endswith("." + ROOT_DOMAIN):
            slug = host[: -(len(ROOT_DOMAIN) + 1)]
            from app.routes.boutique import visiter
            return visiter(slug)
        return None

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/conditions")
    def conditions():
        return render_template("conditions.html")

    @app.route("/sw.js")
    def sw():
        return send_from_directory("static", "sw.js", mimetype="application/javascript")

    @app.route("/manifest.json")
    def manifest():
        return send_from_directory("static", "manifest.json", mimetype="application/manifest+json")

    # ═══════════════════════════════════════════════════════════
    # SÉCURITÉ : headers HTTP renforces
    # ═══════════════════════════════════════════════════════════
    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if not app.debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
        if request.path.startswith(("/dashboard", "/auth", "/admin", "/api/")):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"
        return response

    # ═══════════════════════════════════════════════════════════
    # GESTION DES ERREURS
    # ═══════════════════════════════════════════════════════════
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Forbidden"}), 403
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def internal_error(e):
        logger.exception("Erreur 500")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("errors/500.html"), 500

    @app.errorhandler(429)
    def ratelimit_handler(e):
        if request.path.startswith("/api/"):
            return jsonify({
                "error": "Trop de requetes. Reessayez plus tard.",
                "retry_after": getattr(e, "description", None)
            }), 429
        return render_template("errors/429.html"), 429

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "")).split(",")[0].strip()
        logger.warning(f"[SECURITE] CSRF echec : {e.description} | IP={ip} | path={request.path}")
        # ⚠️ DEBUG : affiche l'erreur CSRF en JSON pour diagnostic
        return jsonify({
            "error": "CSRFError",
            "message": str(e.description),
            "path": request.path,
            "method": request.method
        }), 400

    # ⚠️ DEBUG TEMPORAIRE : affiche le traceback complet
    @app.errorhandler(Exception)
    def handle_exception(e):
        if isinstance(e, HTTPException):
            return e

        # Log dans Vercel
        traceback.print_exc()
        logger.exception(f"Exception non geree : {type(e).__name__}")

        # ⚠️ TEMPORAIRE : renvoie le traceback en JSON pour diagnostic
        tb = traceback.format_exc()
        return jsonify({
            "error": str(e),
            "type": type(e).__name__,
            "path": request.path,
            "method": request.method,
            "traceback": tb[-3000:]
        }), 500

    # ─── Logging ──────────────────────────────────────────────
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    return app