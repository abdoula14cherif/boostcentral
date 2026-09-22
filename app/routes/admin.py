import logging
import secrets
import csv
import io
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, Response
from app.models.security import admin_required
from app.models.database import get_all_recharges, update_recharge, credit_balance, get_all_orders, update_order, get_all_users, update_balance, set_api_key, get_all_promo_codes, create_promo_code, update_promo_code, get_order_by_id, get_all_tickets, get_ticket_messages, add_ticket_message, update_ticket, get_all_retraits, get_retrait_by_id, update_retrait
from app.models.mailer import email_commande_livree

logger = logging.getLogger(__name__)
admin_bp = Blueprint("admin", __name__)

def _headers():
    url = current_app.config["SUPABASE_URL"]
    key = current_app.config["SUPABASE_SERVICE_KEY"] or current_app.config["SUPABASE_ANON_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}

def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path

@admin_bp.route("/")
@admin_required
def index():
    recharges = get_all_recharges(limit=50)
    orders = get_all_orders(limit=100)
    users = get_all_users()
    try:
        r = requests.get(_url("services?order=reseau,categorie"), headers=_headers())
        data = r.json()
        services = data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"services admin: {e}")
        services = []

    pending_recharges = sum(1 for r in recharges if r.get("statut") == "en_attente")
    pending_orders = sum(1 for o in orders if o.get("statut") == "en_attente")
    total_credited = sum(r.get("montant_fcfa", 0) for r in recharges if r.get("statut") == "valide")

    # Stats API : commandes passees via /api/v1 sont taguees "API..." dans note_admin
    orders_api = [o for o in orders if (o.get("note_admin") or "").startswith("API")]
    users_avec_cle = sum(1 for u in users if u.get("api_key"))
    total_facture_api = sum(o.get("prix_total", 0) for o in orders_api)

    stats = {
        "pending_recharges": pending_recharges,
        "pending_orders": pending_orders,
        "total_users": len(users),
        "total_credited": round(total_credited),
        "users_avec_cle": users_avec_cle,
        "commandes_api": len(orders_api),
        "total_facture_api": round(total_facture_api)
    }
    promo_codes = get_all_promo_codes()
    tickets = get_all_tickets()
    nb_tickets_ouverts = sum(1 for t in tickets if t.get("statut") == "ouvert")
    stats["tickets_ouverts"] = nb_tickets_ouverts

    retraits = get_all_retraits()
    stats["retraits_attente"] = sum(1 for r in retraits if r.get("statut") == "en_attente")

    return render_template("admin/index.html", recharges=recharges, orders=orders, services=services, users=users, stats=stats, promo_codes=promo_codes, tickets=tickets, retraits=retraits, whatsapp=current_app.config["WHATSAPP_NUMBER"])

@admin_bp.route("/recharge/process", methods=["POST"])
@admin_required
def process_recharge():
    recharge_id = request.form.get("recharge_id", "")
    action = request.form.get("action", "")
    admin_note = request.form.get("admin_note", "")
    if not recharge_id or action not in ("valider", "refuser"):
        flash("Donnees invalides.", "error")
        return redirect(url_for("admin.index"))
    try:
        r = requests.get(_url(f"recharges?id=eq.{recharge_id}&limit=1"), headers=_headers())
        data = r.json()
        recharge = data[0] if isinstance(data, list) and data else None
    except Exception as e:
        flash("Recharge introuvable.", "error")
        return redirect(url_for("admin.index"))
    if not recharge or recharge.get("statut") != "en_attente":
        flash("Recharge deja traitee.", "warning")
        return redirect(url_for("admin.index"))
    new_status = "valide" if action == "valider" else "refuse"
    update_recharge(recharge_id, {"statut": new_status, "note_admin": admin_note})
    if action == "valider":
        amount = recharge.get("montant_fcfa", 0)
        user_id = recharge.get("user_id")
        credit_balance(user_id, amount)
        flash(f"{amount:,.0f} FCFA credites a {recharge.get('user_email')}.", "success")
        try:
            email_recharge_validee(recharge.get('user_email'), recharge.get('user_email','').split('@')[0], amount)
        except:
            pass
    else:
        flash("Recharge refusee.", "info")
    return redirect(url_for("admin.index"))

@admin_bp.route("/order/update", methods=["POST"])
@admin_required
def update_order_route():
    order_id = request.form.get("order_id", "")
    status = request.form.get("status", "")
    admin_note = request.form.get("admin_note", "")
    try:
        progression = int(request.form.get("progression", 0))
    except:
        progression = 0
    if not order_id:
        flash("ID commande manquant.", "error")
        return redirect(url_for("admin.index"))
    if status == "termine":
        progression = 100
    elif status == "refuse":
        progression = 0

    order_avant = get_order_by_id(order_id)
    deja_termine = order_avant and order_avant.get("statut") == "termine"

    ok = update_order(order_id, {"statut": status, "progression": progression, "note_admin": admin_note})

    if ok and status == "termine" and not deja_termine and order_avant:
        try:
            email_commande_livree(
                order_avant.get("user_email"),
                (order_avant.get("user_email") or "").split("@")[0],
                order_avant.get("service"),
                order_avant.get("quantite", 0)
            )
        except Exception as e:
            logger.error(f"email_commande_livree: {e}")

    if ok:
        flash("Commande mise a jour.", "success")
    else:
        flash("Erreur mise a jour.", "error")
    return redirect(url_for("admin.index") + "#commandes")

@admin_bp.route("/service/update", methods=["POST"])
@admin_required
def update_service():
    service_id = request.form.get("service_id", "")
    if not service_id:
        flash("ID service manquant.", "error")
        return redirect(url_for("admin.index") + "#services")
    try:
        r = requests.patch(_url(f"services?id=eq.{service_id}"), json={
            "prix_fcfa": float(request.form.get("prix_fcfa", 0)),
            "min_qte": int(request.form.get("min_qte", 1)),
            "max_qte": int(request.form.get("max_qte", 1)),
            "description": request.form.get("description", ""),
            "actif": request.form.get("actif") == "on"
        }, headers=_headers())
        flash("Service mis a jour.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "error")
    return redirect(url_for("admin.index") + "#services")

@admin_bp.route("/user/balance", methods=["POST"])
@admin_required
def update_user_balance():
    user_id = request.form.get("user_id", "")
    try:
        new_balance = float(request.form.get("new_balance", 0))
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin.index") + "#users")
    ok = update_balance(user_id, new_balance)
    if ok:
        flash(f"Solde mis a jour : {new_balance:,.0f} FCFA.", "success")
    else:
        flash("Erreur mise a jour solde.", "error")
    return redirect(url_for("admin.index") + "#users")

@admin_bp.route("/user/api-key", methods=["POST"])
@admin_required
def manage_api_key():
    """Genere/regenere ou revoque la cle API d'un utilisateur, depuis l'admin."""
    user_id = request.form.get("user_id", "")
    action = request.form.get("action", "")
    user_email = request.form.get("user_email", "")

    if not user_id or action not in ("generer", "revoquer"):
        flash("Donnees invalides.", "error")
        return redirect(url_for("admin.index") + "#api")

    if action == "revoquer":
        ok = set_api_key(user_id, None)
        if ok:
            flash(f"Cle API revoquee pour {user_email}.", "success")
        else:
            flash("Erreur lors de la revocation.", "error")
    else:
        new_key = "bc_" + secrets.token_hex(20)
        ok = set_api_key(user_id, new_key)
        if ok:
            flash(f"Nouvelle cle API generee pour {user_email}.", "success")
        else:
            flash("Erreur lors de la generation.", "error")

    return redirect(url_for("admin.index") + "#api")


@admin_bp.route("/promo/create", methods=["POST"])
@admin_required
def create_promo():
    code = request.form.get("code", "").strip().upper()
    try:
        bonus_pct = float(request.form.get("bonus_pct", 0)) / 100
    except:
        flash("Pourcentage invalide.", "error")
        return redirect(url_for("admin.index") + "#promo")

    max_util = request.form.get("max_utilisations", "").strip()
    max_util = int(max_util) if max_util else None

    date_exp = request.form.get("date_expiration", "").strip()
    date_exp = date_exp if date_exp else None

    if not code or bonus_pct <= 0:
        flash("Code et pourcentage requis.", "error")
        return redirect(url_for("admin.index") + "#promo")

    result = create_promo_code({
        "code": code,
        "bonus_pct": bonus_pct,
        "actif": True,
        "max_utilisations": max_util,
        "date_expiration": date_exp
    })
    if result:
        flash(f"Code promo {code} cree ({round(bonus_pct*100)}%).", "success")
    else:
        flash("Erreur lors de la creation (code deja existant ?).", "error")

    return redirect(url_for("admin.index") + "#promo")


@admin_bp.route("/promo/toggle", methods=["POST"])
@admin_required
def toggle_promo():
    code_id = request.form.get("code_id", "")
    actif = request.form.get("actif") == "1"
    if not code_id:
        flash("ID manquant.", "error")
        return redirect(url_for("admin.index") + "#promo")
    ok = update_promo_code(code_id, {"actif": not actif})
    if ok:
        flash("Code promo mis a jour.", "success")
    else:
        flash("Erreur mise a jour.", "error")
    return redirect(url_for("admin.index") + "#promo")


@admin_bp.route("/ticket/<ticket_id>")
@admin_required
def ticket_detail(ticket_id):
    from flask import jsonify
    ticket = None
    for t in get_all_tickets():
        if str(t.get("id")) == str(ticket_id):
            ticket = t
            break
    messages = get_ticket_messages(ticket_id)
    return jsonify({"ticket": ticket, "messages": messages})


@admin_bp.route("/ticket/repondre", methods=["POST"])
@admin_required
def ticket_repondre():
    ticket_id = request.form.get("ticket_id", "")
    message = request.form.get("message", "").strip()
    if not ticket_id or not message:
        flash("Donnees manquantes.", "error")
        return redirect(url_for("admin.index") + "#support")

    add_ticket_message(ticket_id, "admin", message)
    update_ticket(ticket_id, {"statut": "repondu"})
    flash("Reponse envoyee.", "success")
    return redirect(url_for("admin.index") + "#support")


@admin_bp.route("/ticket/statut", methods=["POST"])
@admin_required
def ticket_statut():
    ticket_id = request.form.get("ticket_id", "")
    statut = request.form.get("statut", "")
    if not ticket_id or statut not in ("ouvert", "repondu", "ferme"):
        flash("Donnees invalides.", "error")
        return redirect(url_for("admin.index") + "#support")
    update_ticket(ticket_id, {"statut": statut})
    flash("Statut mis a jour.", "success")
    return redirect(url_for("admin.index") + "#support")


def _csv_response(rows, headers, filename):
    """Construit une reponse CSV telechargeable a partir d'une liste de dicts."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    output = buf.getvalue()
    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@admin_bp.route("/export/commandes.csv")
@admin_required
def export_commandes():
    orders = get_all_orders(limit=10000)
    headers = ["ID", "Email client", "Reseau", "Service", "Quantite", "Prix unitaire", "Prix total", "Lien", "Statut", "Progression", "Date"]
    rows = [[
        o.get("id"), o.get("user_email"), o.get("reseau"), o.get("service"),
        o.get("quantite"), o.get("prix_unitaire"), o.get("prix_total"),
        o.get("lien"), o.get("statut"), o.get("progression"),
        (o.get("created_at") or "")[:19]
    ] for o in orders]
    return _csv_response(rows, headers, "commandes_boostcentral.csv")


@admin_bp.route("/export/recharges.csv")
@admin_required
def export_recharges():
    recharges = get_all_recharges(limit=10000)
    headers = ["ID", "Email client", "Montant FCFA", "Methode", "Code promo", "Statut", "Date"]
    rows = [[
        r.get("id"), r.get("user_email"), r.get("montant_fcfa"), r.get("methode"),
        r.get("promo_code") or "", r.get("statut"), (r.get("created_at") or "")[:19]
    ] for r in recharges]
    return _csv_response(rows, headers, "recharges_boostcentral.csv")


@admin_bp.route("/export/utilisateurs.csv")
@admin_required
def export_utilisateurs():
    users = get_all_users()
    headers = ["ID", "Email", "Nom", "Pays", "Solde FCFA", "Revendeur", "Date inscription"]
    rows = [[
        u.get("id"), u.get("email"), u.get("full_name"), u.get("country"),
        u.get("balance"), "Oui" if u.get("est_revendeur") else "Non",
        (u.get("created_at") or "")[:19]
    ] for u in users]
    return _csv_response(rows, headers, "utilisateurs_boostcentral.csv")


@admin_bp.route("/retrait/traiter", methods=["POST"])
@admin_required
def traiter_retrait():
    retrait_id = request.form.get("retrait_id", "")
    action = request.form.get("action", "")

    retrait = get_retrait_by_id(retrait_id)
    if not retrait or retrait.get("statut") != "en_attente":
        flash("Retrait introuvable ou deja traite.", "error")
        return redirect(url_for("admin.index") + "#retraits")

    if action == "valider":
        update_retrait(retrait_id, {"statut": "valide"})
        flash(f"Retrait de {retrait['montant']:,.0f} FCFA marque comme paye. N'oublie pas d'envoyer l'argent reellement.", "success")
    elif action == "refuser":
        credit_balance(retrait["user_id"], retrait["montant"])
        update_retrait(retrait_id, {"statut": "refuse"})
        flash(f"Retrait refuse, {retrait['montant']:,.0f} FCFA recredites au client.", "info")
    else:
        flash("Action invalide.", "error")

    return redirect(url_for("admin.index") + "#retraits")
