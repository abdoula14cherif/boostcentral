import logging
import requests as req
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from app.models.security import admin_required

logger = logging.getLogger(__name__)
admin_users_bp = Blueprint("admin_users", __name__)

def _headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path

@admin_users_bp.route("/")
@admin_required
def index():
    """Liste tous les utilisateurs."""
    users = req.get(
        _url("profiles?order=created_at.desc&select=*"),
        headers=_headers()
    ).json() or []
    return render_template("admin/users.html", users=users)

@admin_users_bp.route("/<user_id>")
@admin_required
def detail(user_id):
    """Detail d un utilisateur."""
    # Profil
    r = req.get(_url(f"profiles?id=eq.{user_id}&limit=1"), headers=_headers())
    data = r.json()
    if not data:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("admin_users.index"))
    user = data[0]

    # Commandes
    commandes = req.get(
        _url(f"commandes?user_id=eq.{user_id}&order=created_at.desc&limit=20"),
        headers=_headers()
    ).json() or []

    # Recharges
    recharges = req.get(
        _url(f"recharges?user_id=eq.{user_id}&order=created_at.desc&limit=10"),
        headers=_headers()
    ).json() or []

    # Stats
    total_depense = sum(c.get("prix_total", 0) for c in commandes)
    total_recharge = sum(r.get("montant_fcfa", 0) for r in recharges if r.get("statut") == "valide")
    nb_commandes = len(commandes)

    return render_template("admin/user_detail.html",
        user=user,
        commandes=commandes,
        recharges=recharges,
        total_depense=total_depense,
        total_recharge=total_recharge,
        nb_commandes=nb_commandes)

@admin_users_bp.route("/<user_id>/balance", methods=["POST"])
@admin_required
def update_balance(user_id):
    """Modifier le solde."""
    new_balance = request.form.get("balance", "0")
    try:
        new_balance = float(new_balance)
    except:
        flash("Montant invalide.", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    req.patch(_url(f"profiles?id=eq.{user_id}"),
        json={"balance": new_balance}, headers=_headers())
    flash(f"Solde mis a jour : {new_balance:,.0f} FCFA.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))

@admin_users_bp.route("/<user_id>/points", methods=["POST"])
@admin_required
def update_points(user_id):
    """Modifier les points."""
    new_points = request.form.get("points", "0")
    try:
        new_points = int(new_points)
    except:
        flash("Points invalides.", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    req.patch(_url(f"profiles?id=eq.{user_id}"),
        json={"points": new_points}, headers=_headers())
    flash(f"Points mis a jour : {new_points}.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))

@admin_users_bp.route("/<user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    """Envoyer email de reinitialisation."""
    r = req.get(_url(f"profiles?id=eq.{user_id}&select=email"), headers=_headers())
    data = r.json()
    if not data:
        flash("Utilisateur introuvable.", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    email = data[0]["email"]
    ANON_KEY = current_app.config.get("SUPABASE_ANON_KEY")
    req.post(
        current_app.config["SUPABASE_URL"] + "/auth/v1/recover",
        json={"email": email},
        headers={"apikey": ANON_KEY, "Content-Type": "application/json"}
    )
    flash(f"Email de reinitialisation envoye a {email}.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))

@admin_users_bp.route("/<user_id>/set-password", methods=["POST"])
@admin_required
def set_password(user_id):
    """Definir un nouveau mot de passe."""
    new_password = request.form.get("password", "")
    if len(new_password) < 6:
        flash("Mot de passe trop court (min 6 caracteres).", "error")
        return redirect(url_for("admin_users.detail", user_id=user_id))

    SERVICE_KEY = current_app.config.get("SUPABASE_SERVICE_KEY")
    r = req.put(
        current_app.config["SUPABASE_URL"] + f"/auth/v1/admin/users/{user_id}",
        json={"password": new_password},
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}
    )
    if r.status_code < 300:
        flash("Mot de passe mis a jour avec succes.", "success")
    else:
        flash(f"Erreur : {r.text}", "error")
    return redirect(url_for("admin_users.detail", user_id=user_id))

@admin_users_bp.route("/<user_id>/bloquer", methods=["POST"])
@admin_required
def bloquer(user_id):
    """Bloquer/debloquer un utilisateur."""
    action = request.form.get("action", "bloquer")
    SERVICE_KEY = current_app.config.get("SUPABASE_SERVICE_KEY")
    banned = action == "bloquer"
    r = req.put(
        current_app.config["SUPABASE_URL"] + f"/auth/v1/admin/users/{user_id}",
        json={"ban_duration": "876600h" if banned else "none"},
        headers={"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}", "Content-Type": "application/json"}
    )
    if r.status_code < 300:
        msg = "Utilisateur bloque." if banned else "Utilisateur debloque."
        flash(msg, "success")
    else:
        flash(f"Erreur : {r.text}", "error")
    return redirect(url_for("admin_users.detail", user_id=user_id))

@admin_users_bp.route("/<user_id>/note", methods=["POST"])
@admin_required
def update_note(user_id):
    """Ajouter une note admin sur un utilisateur."""
    note = request.form.get("note", "")
    req.patch(_url(f"profiles?id=eq.{user_id}"),
        json={"note_admin": note}, headers=_headers())
    flash("Note mise a jour.", "success")
    return redirect(url_for("admin_users.detail", user_id=user_id))
