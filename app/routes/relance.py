import os
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify
from app.models.database import get_all_users, get_user_orders, update_profile
from app.models.mailer import email_inactivite

logger = logging.getLogger(__name__)
relance_bp = Blueprint("relance", __name__)

JOURS_INACTIVITE = 14


def _est_autorise():
    """Verifie que l'appel vient bien de Vercel Cron (via CRON_SECRET)."""
    secret = os.environ.get("CRON_SECRET", "")
    if not secret:
        return False
    auth = request.headers.get("Authorization", "")
    return auth == f"Bearer {secret}"


@relance_bp.route("/inactifs", methods=["GET", "POST"])
def relancer_inactifs():
    if not _est_autorise():
        return jsonify({"error": "Non autorise."}), 401

    users = get_all_users()
    maintenant = datetime.now(timezone.utc)
    seuil = maintenant - timedelta(days=JOURS_INACTIVITE)

    relances = 0
    verifies = 0

    for u in users:
        user_id = u.get("id")
        email = u.get("email")
        if not user_id or not email:
            continue
        verifies += 1

        # Ne pas relancer un compte tout jeune
        try:
            created = datetime.fromisoformat((u.get("created_at") or "").replace("Z", "+00:00"))
            if created > seuil:
                continue
        except Exception:
            pass

        # Ne pas relancer plus d'une fois par periode de 14 jours
        derniere_relance = u.get("derniere_relance")
        if derniere_relance:
            try:
                dr = datetime.fromisoformat(derniere_relance.replace("Z", "+00:00"))
                if dr > seuil:
                    continue
            except Exception:
                pass

        # Verifier la derniere commande
        derniere_commande = get_user_orders(user_id, limit=1)
        if derniere_commande:
            try:
                dc = datetime.fromisoformat((derniere_commande[0].get("created_at") or "").replace("Z", "+00:00"))
                if dc > seuil:
                    continue  # actif recemment, on ne relance pas
            except Exception:
                pass

        nom = (u.get("full_name") or email.split("@")[0])
        try:
            ok = email_inactivite(email, nom)
            if ok:
                update_profile(user_id, {"derniere_relance": maintenant.isoformat()})
                relances += 1
        except Exception as e:
            logger.error(f"relance inactivite {email}: {e}")

    logger.info(f"Relance inactifs: {verifies} verifies, {relances} relances envoyees")
    return jsonify({"verifies": verifies, "relances": relances})
