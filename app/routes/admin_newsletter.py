"""
Admin Newsletter — Envoi d'emails a 1, plusieurs ou tous les utilisateurs.
"""
import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.security import admin_required
from app.models.database import get_all_users
from app.models.mailer import email_newsletter_personnalise

logger = logging.getLogger(__name__)
admin_newsletter_bp = Blueprint("admin_newsletter", __name__)


@admin_newsletter_bp.route("/newsletter")
@admin_required
def newsletter_page():
    """Page d'envoi de newsletter."""
    users = get_all_users()
    # Trier par date d'inscription recente
    users.sort(key=lambda u: u.get("created_at", ""), reverse=True)
    return render_template("admin/newsletter.html", users=users)


@admin_newsletter_bp.route("/newsletter/envoyer", methods=["POST"])
@admin_required
def envoyer_newsletter():
    """Envoie un email a 1, plusieurs ou tous les utilisateurs."""
    sujet = request.form.get("sujet", "").strip()
    contenu = request.form.get("contenu", "").strip()
    cible = request.form.get("cible", "tous")  # 'tous' | 'selection' | 'un'

    if not sujet or not contenu:
        flash("Sujet et contenu sont requis.", "error")
        return redirect(url_for("admin_newsletter.newsletter_page"))

    users = get_all_users()

    # Determiner les destinataires
    destinataires = []
    if cible == "tous":
        destinataires = users
    elif cible == "un":
        user_id = request.form.get("user_id_un", "")
        destinataires = [u for u in users if str(u.get("id")) == str(user_id)]
    elif cible == "selection":
        user_ids = request.form.getlist("user_ids")
        destinataires = [u for u in users if str(u.get("id")) in user_ids]

    if not destinataires:
        flash("Aucun destinataire valide selectionne.", "error")
        return redirect(url_for("admin_newsletter.newsletter_page"))

    # Envoi
    succes = 0
    echecs = 0
    for u in destinataires:
        email = u.get("email")
        if not email:
            continue
        nom = u.get("full_name") or email.split("@")[0]
        try:
            ok = email_newsletter_personnalise(email, nom, sujet, contenu)
            if ok:
                succes += 1
            else:
                echecs += 1
        except Exception as e:
            logger.error(f"Newsletter erreur pour {email}: {e}")
            echecs += 1

    if succes > 0:
        flash(f"✅ Email envoye a {succes} utilisateur(s)." + (f" ({echecs} echec(s))" if echecs else ""), "success")
    else:
        flash(f"❌ Aucun email n'a pu etre envoye ({echecs} echec(s)).", "error")

    return redirect(url_for("admin_newsletter.newsletter_page"))