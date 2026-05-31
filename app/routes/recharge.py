import logging
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    soina_url = current_app.config.get("SOINA_PAY_URL", "https://soinapay.com/pay/zmnmqbap")
    return render_template("dashboard/recharge.html", user=user, profile=profile, history=history, soina_url=soina_url, whatsapp=current_app.config["WHATSAPP_NUMBER"])
