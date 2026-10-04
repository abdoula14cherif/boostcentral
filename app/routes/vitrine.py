import logging
from flask import Blueprint, render_template
from app.models.database import get_all_preuves

logger = logging.getLogger(__name__)
vitrine_bp = Blueprint("vitrine", __name__)


@vitrine_bp.route("/preuves")
def preuves_publiques():
    preuves = get_all_preuves()
    return render_template("preuves_publiques.html", preuves=preuves)
