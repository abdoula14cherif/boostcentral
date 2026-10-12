import logging
from flask import Blueprint, jsonify, request
from app.models.database import (
    get_notifications_en_attente,
    marquer_notification_envoyee,
    marquer_notification_echec
)
from app.models.mailer import email_nouveau_produit, email_newsletter_personnalise

logger = logging.getLogger(__name__)
relance_bp = Blueprint("relance", __name__)


@relance_bp.route("/process-notifications", methods=["GET", "POST"])
def process_notifications():
    """
    Traite la file de notifications : envoie 10 emails max par appel.
    Appele par Vercel Cron toutes les 5 minutes.
    """
    notifs = get_notifications_en_attente(limit=10)
    envoyes = 0
    echecs = 0

    for n in notifs:
        try:
            type_notif = n.get("type", "")
            email_dest = n.get("destinataire_email")
            nom_dest = n.get("destinataire_nom") or (email_dest or "").split("@")[0]
            payload = n.get("payload") or {}

            ok = False

            if type_notif == "nouveau_produit":
                ok = email_nouveau_produit(
                    to_email=email_dest,
                    nom_destinataire=nom_dest,
                    nom_produit=payload.get("nom_produit", ""),
                    description_produit=payload.get("description", ""),
                    prix_plateforme=payload.get("prix", 0),
                    image_url=payload.get("image_url") or None,
                    lien_produit="https://boostcentral.world/dashboard/affiliation"
                )

            elif type_notif == "newsletter":
                ok = email_newsletter_personnalise(
                    to_email=email_dest,
                    nom_destinataire=nom_dest,
                    sujet=n.get("sujet", "Boost Central"),
                    contenu_html=n.get("contenu_html", "")
                )

            if ok:
                marquer_notification_envoyee(n["id"])
                envoyes += 1
            else:
                marquer_notification_echec(n["id"], "Envoi echoue")
                echecs += 1
        except Exception as e:
            logger.error(f"process_notifications -> {n.get('id')}: {e}")
            marquer_notification_echec(n["id"], str(e))
            echecs += 1

    logger.info(f"process_notifications: {envoyes} envoyes, {echecs} echecs")
    return jsonify({
        "envoyes": envoyes,
        "echecs": echecs,
        "restants": len(notifs) - envoyes - echecs
    }), 200