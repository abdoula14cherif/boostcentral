import logging
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, current_app, request, session
from app.models.security import login_required, get_current_user
from app.models.database import get_profile, get_user_recharges, create_recharge

logger = logging.getLogger(__name__)
recharge_bp = Blueprint("recharge", __name__)

SOINA_PUBLIC = "pk_live_05f91d02ce7aaf0805575c766690e35d"
SOINA_SECRET = "sk_live_4c266e348b979cf6c2e42ee357233c937a27e5fc707e97c9"
SOINA_PAY_URL = "https://soinapay.com/pay/zmnmqbap"

@recharge_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    history = get_user_recharges(user["id"], limit=10)
    return render_template("dashboard/recharge.html",
        user=user, profile=profile, history=history,
        soina_url=SOINA_PAY_URL,
        whatsapp=current_app.config["WHATSAPP_NUMBER"])
