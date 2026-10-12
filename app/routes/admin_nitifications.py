"""
Admin Notifications — Gestion de la file d'envoi d'emails (produits + newsletter).
"""
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from app.models.security import admin_required
from app.models.database import (
    get_notifications_en_attente,
    marquer_notification_envoyee,
    marquer_notification_echec
)

logger = logging.getLogger(__name__)
admin_notifications_bp = Blueprint("admin_notifications", __name__)


def _traiter_notifications(limit=25):
    """
    Traite la file d'attente : envoie jusqu'a `limit` emails.
    Retourne (envoyes, echecs).
    """
    from app.models.mailer import email_nouveau_produit, email_newsletter_personnalise

    notifs = get_notifications_en_attente(limit=limit)
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
            logger.error(f"traitement notif {n.get('id')}: {e}")
            marquer_notification_echec(n["id"], str(e))
            echecs += 1

    logger.info(f"Traitement notifs: {envoyes} envoyes, {echecs} echecs")
    return envoyes, echecs


@admin_notifications_bp.route("/notifications")
@admin_required
def notifications_page():
    """Page admin pour gerer les notifications."""
    from app.models.database import _url, _headers
    import requests

    # Recuperer les stats
    try:
        r = requests.get(_url("notifications_queue?select=statut"), headers=_headers(True))
        toutes = r.json() if r.status_code < 300 else []
        stats = {
            "total": len(toutes),
            "en_attente": sum(1 for n in toutes if n.get("statut") == "en_attente"),
            "envoye": sum(1 for n in toutes if n.get("statut") == "envoye"),
            "echec": sum(1 for n in toutes if n.get("statut") == "echec"),
        }
    except Exception as e:
        logger.error(f"stats notifs: {e}")
        stats = {"total": 0, "en_attente": 0, "envoye": 0, "echec": 0}

    # Recuperer les 50 dernieres notifications
    try:
        r = requests.get(
            _url("notifications_queue?order=created_at.desc&limit=50"),
            headers=_headers(True)
        )
        notifications = r.json() if r.status_code < 300 else []
    except Exception as e:
        logger.error(f"liste notifs: {e}")
        notifications = []

    return render_template("admin/notifications.html",
                          stats=stats, notifications=notifications)


@admin_notifications_bp.route("/notifications/envoyer", methods=["POST"])
@admin_required
def envoyer_notifications():
    """Envoie 25 notifications en attente (appele par le bouton)."""
    limit = int(request.form.get("limit", 25))
    envoyes, echecs = _traiter_notifications(limit=limit)

    if envoyes > 0:
        flash(f"✅ {envoyes} email(s) envoye(s)." + (f" ({echecs} echec(s))" if echecs else ""), "success")
    else:
        flash(f"Aucun email envoye. {echecs} echec(s).", "warning")

    return redirect(url_for("admin_notifications.notifications_page"))


@admin_notifications_bp.route("/notifications/envoyer-ajax", methods=["POST"])
@admin_required
def envoyer_notifications_ajax():
    """Envoi AJAX (utilise si on veut enchainer les lots)."""
    limit = int(request.form.get("limit", 25))
    envoyes, echecs = _traiter_notifications(limit=limit)
    return jsonify({"envoyes": envoyes, "echecs": echecs})


@admin_notifications_bp.route("/notifications/relancer", methods=["POST"])
@admin_required
def relancer_echecs():
    """Remet les notifications en echec dans la file d'attente."""
    from app.models.database import _url, _headers
    import requests

    try:
        r = requests.patch(
            _url("notifications_queue?statut=eq.echec"),
            json={"statut": "en_attente", "tentatives": 0, "erreur": None},
            headers=_headers(True)
        )
        if r.status_code < 300:
            flash("Notifications en echec remises en file d'attente.", "success")
        else:
            flash("Erreur lors de la remise en file.", "error")
    except Exception as e:
        logger.error(f"relancer echecs: {e}")
        flash("Erreur.", "error")

    return redirect(url_for("admin_notifications.notifications_page"))