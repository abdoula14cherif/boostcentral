import logging
import requests as req
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from app.models.security import admin_required
from app.models.boostci import get_services as boostci_get_services, prix_client_fcfa

logger = logging.getLogger(__name__)
admin_boostci_bp = Blueprint("admin_boostci", __name__)

RESEAU_MAP = {
    "facebook": "facebook", "instagram": "instagram", "tiktok": "tiktok",
    "youtube": "youtube", "twitter": "twitter", "telegram": "telegram",
    "spotify": "spotify", "whatsapp": "whatsapp"
}

def _admin_headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}",
            "Content-Type": "application/json", "Prefer": "return=representation"}

def _supabase_url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path

def detect_reseau(name, category):
    txt = (name + " " + category).lower()
    for r in RESEAU_MAP:
        if r in txt:
            return r
    return None

@admin_boostci_bp.route("/")
@admin_required
def index():
    services = boostci_get_services()
    grouped = {}
    for s in services:
        cat = s.get("category", "Autre")
        if cat not in grouped:
            grouped[cat] = []
        reseau = detect_reseau(s.get("name",""), cat)
        prix_1000 = prix_client_fcfa(float(s.get("rate", 0)), 1000)
        grouped[cat].append({
            **s,
            "reseau_detecte": reseau,
            "prix_client_1000": round(prix_1000)
        })
    return render_template("admin/boostci.html", grouped=grouped)

@admin_boostci_bp.route("/importer", methods=["POST"])
@admin_required
def importer():
    boostci_id = request.form.get("boostci_id")
    nom = request.form.get("nom", "")
    reseau = request.form.get("reseau", "")
    min_qte = request.form.get("min_qte", 100)
    max_qte = request.form.get("max_qte", 100000)
    prix_fcfa = request.form.get("prix_fcfa", 0)

    if not boostci_id or not reseau or not nom:
        flash("Donnees manquantes.", "error")
        return redirect(url_for("admin_boostci.index"))

    # Verifier si deja importe
    exist = req.get(_supabase_url(f"services?boostci_service_id=eq.{boostci_id}&limit=1"), headers=_admin_headers())
    if exist.json():
        flash("Ce service est deja importe.", "warning")
        return redirect(url_for("admin_boostci.index"))

    try:
        prix_val = max(float(prix_fcfa), 0.01)
        r = req.post(_supabase_url("services"), json={
            "reseau": reseau,
            "categorie": nom,
            "prix_fcfa": prix_val,
            "min_qte": int(min_qte),
            "max_qte": int(max_qte),
            "description": "Service premium Boost Central",
            "actif": True,
            "boostci_service_id": int(boostci_id)
        }, headers=_admin_headers())
        if r.status_code in (200, 201):
            flash(f"Service '{nom}' importe !", "success")
        else:
            flash(f"Erreur : {r.text}", "error")
    except Exception as e:
        flash(f"Erreur : {e}", "error")

    return redirect(url_for("admin_boostci.index"))

@admin_boostci_bp.route("/importer-tous", methods=["POST"])
@admin_required
def importer_tous():
    services = boostci_get_services()
    importe = 0
    ignore = 0
    USD_RATE = 600

    for s in services:
        reseau = detect_reseau(s.get("name", ""), s.get("category", ""))
        if not reseau:
            ignore += 1
            continue

        rate = float(s.get("rate", 0))
        if rate <= 0:
            ignore += 1
            continue

        boostci_sid = int(s.get("service", 0))

        # Verifier si deja importe
        exist = req.get(_supabase_url(f"services?boostci_service_id=eq.{boostci_sid}&limit=1"), headers=_admin_headers())
        if exist.json():
            ignore += 1
            continue

        prix_boostci = (rate / 1000) * USD_RATE
        prix_client = max(round(prix_boostci + 1, 4), 0.01)

        try:
            r = req.post(_supabase_url("services"), json={
                "reseau": reseau,
                "categorie": s.get("name", ""),
                "prix_fcfa": prix_client,
                "min_qte": int(s.get("min", 100)),
                "max_qte": int(s.get("max", 100000)),
                "description": s.get("description", ""),
                "actif": True,
                "boostci_service_id": boostci_sid
            }, headers=_admin_headers())

            if r.status_code in (200, 201):
                importe += 1
            else:
                ignore += 1
        except Exception as e:
            logger.error(f"Import erreur: {e}")
            ignore += 1

    flash(f"✅ {importe} services importes, {ignore} ignores.", "success")
    return redirect(url_for("admin_boostci.index"))
