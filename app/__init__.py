import os
import logging
from flask import Flask, render_template, send_from_directory
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["200 per hour"])
csrf = CSRFProtect()

def create_app(config_name="production"):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    from app.config import config_map
    app.config.from_object(config_map[config_name])
    limiter.init_app(app)
    csrf.init_app(app)
    from app.routes.auth import auth_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.admin import admin_bp
    from app.routes.recharge import recharge_bp
    from app.routes.webhook import webhook_bp
    from app.routes.gagner import gagner_bp
    from app.routes.admin_boostci import admin_boostci_bp
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(recharge_bp, url_prefix="/recharge")
    app.register_blueprint(webhook_bp, url_prefix="/recharge")
    app.register_blueprint(gagner_bp, url_prefix="/gagner")
    app.register_blueprint(admin_boostci_bp, url_prefix="/admin/boostci")
    csrf.exempt(webhook_bp)
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
    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403
    @app.errorhandler(500)
    def internal_error(e):
        return render_template("errors/500.html"), 500
    logging.basicConfig(level=logging.INFO)
    return app
