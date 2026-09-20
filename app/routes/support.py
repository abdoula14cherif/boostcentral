import logging
from flask import Blueprint, render_template, redirect, url_for, flash, request
from app.models.security import login_required, get_current_user
from app.models.database import (get_profile, create_ticket, get_user_tickets,
    get_ticket_by_id_for_user, get_ticket_messages, add_ticket_message, update_ticket)

logger = logging.getLogger(__name__)
support_bp = Blueprint("support", __name__)


@support_bp.route("/")
@login_required
def index():
    user = get_current_user()
    profile = get_profile(user["id"])
    tickets = get_user_tickets(user["id"])
    return render_template("dashboard/support.html", user=user, profile=profile, tickets=tickets)


@support_bp.route("/nouveau", methods=["POST"])
@login_required
def nouveau():
    user = get_current_user()
    sujet = request.form.get("sujet", "").strip()
    message = request.form.get("message", "").strip()

    if not sujet or not message:
        flash("Sujet et message requis.", "error")
        return redirect(url_for("support.index"))

    ticket = create_ticket({
        "user_id": user["id"],
        "user_email": user["email"],
        "sujet": sujet,
        "statut": "ouvert"
    })

    if not ticket:
        flash("Erreur lors de la creation du ticket.", "error")
        return redirect(url_for("support.index"))

    add_ticket_message(ticket["id"], "client", message)
    flash("Ticket envoye ! Notre equipe va vous repondre rapidement.", "success")
    return redirect(url_for("support.detail", ticket_id=ticket["id"]))


@support_bp.route("/<ticket_id>")
@login_required
def detail(ticket_id):
    user = get_current_user()
    ticket = get_ticket_by_id_for_user(ticket_id, user["id"])
    if not ticket:
        flash("Ticket introuvable.", "error")
        return redirect(url_for("support.index"))
    messages = get_ticket_messages(ticket_id)
    return render_template("dashboard/support_detail.html", user=user, ticket=ticket, messages=messages)


@support_bp.route("/<ticket_id>/repondre", methods=["POST"])
@login_required
def repondre(ticket_id):
    user = get_current_user()
    ticket = get_ticket_by_id_for_user(ticket_id, user["id"])
    if not ticket:
        flash("Ticket introuvable.", "error")
        return redirect(url_for("support.index"))

    if ticket.get("statut") == "ferme":
        flash("Ce ticket est ferme. Ouvrez-en un nouveau si besoin.", "warning")
        return redirect(url_for("support.detail", ticket_id=ticket_id))

    message = request.form.get("message", "").strip()
    if not message:
        flash("Message vide.", "error")
        return redirect(url_for("support.detail", ticket_id=ticket_id))

    add_ticket_message(ticket_id, "client", message)
    update_ticket(ticket_id, {"statut": "ouvert"})
    flash("Message envoye.", "success")
    return redirect(url_for("support.detail", ticket_id=ticket_id))
