import logging
import requests
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from app.models.security import admin_required
from app.models.database import get_all_recharges, update_recharge, credit_balance, get_all_orders, update_order, get_all_users, update_balance

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
    stats = {"pending_recharges": pending_recharges, "pending_orders": pending_orders, "total_users": len(users), "total_credited": round(total_credited)}
    return render_template("admin/index.html", recharges=recharges, orders=orders, services=services, users=users, stats=stats, whatsapp=current_app.config["WHATSAPP_NUMBER"])

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
    ok = update_order(order_id, {"statut": status, "progression": progression, "note_admin": admin_note})
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
