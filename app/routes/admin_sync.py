import logging
import requests as req
from flask import Blueprint, render_template, redirect, url_for, flash, current_app
from app.models.security import admin_required

logger = logging.getLogger(__name__)
admin_sync_bp = Blueprint("admin_sync", __name__)

BOOSTCI_KEY = "b48e3d458ac91cedd3b490baaeae55f80890f47d308de5d8f31abc5cc12bf741"

def _headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"}

def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path

def _boostci_status(order_id):
    r = req.post("https://boostci.com/api/v2", data={
        "key": BOOSTCI_KEY, "action": "status", "order": order_id
    }, timeout=15)
    return r.json()

@admin_sync_bp.route("/")
@admin_required
def index():
    """Page de sync des commandes BOOSTCI."""
    commandes = req.get(
        _url("commandes?statut=eq.en_cours&select=id,service,note_admin,quantite,lien,created_at&order=created_at.desc"),
        headers=_headers()
    ).json() or []

    resultats = []
    for cmd in commandes:
        note = cmd.get("note_admin", "")
        boostci_id = None
        statut_boostci = "N/A"
        remains = 0

        if "BOOSTCI order ID:" in note:
            try:
                boostci_id = int(note.split("BOOSTCI order ID:")[-1].strip().split()[0])
                s = _boostci_status(boostci_id)
                statut_boostci = s.get("status", "N/A")
                remains = s.get("remains", 0)
            except Exception as e:
                statut_boostci = f"Erreur: {e}"

        resultats.append({
            "id": cmd["id"],
            "service": cmd["service"],
            "lien": cmd.get("lien","")[:40],
            "quantite": cmd["quantite"],
            "boostci_id": boostci_id,
            "statut_boostci": statut_boostci,
            "remains": remains,
            "date": cmd.get("created_at","")[:10]
        })

    return render_template("admin/sync.html", resultats=resultats)

@admin_sync_bp.route("/now")
@admin_required
def sync_now():
    """Lance le sync et met a jour les statuts."""
    commandes = req.get(
        _url("commandes?statut=eq.en_cours&select=id,service,note_admin,quantite"),
        headers=_headers()
    ).json() or []

    updated = 0
    for cmd in commandes:
        note = cmd.get("note_admin", "")
        if "BOOSTCI order ID:" not in note:
            continue
        try:
            boostci_id = int(note.split("BOOSTCI order ID:")[-1].strip().split()[0])
            s = _boostci_status(boostci_id)
            statut = s.get("status", "").lower()
            remains = int(s.get("remains", 0))
            qte = cmd.get("quantite", 1)

            if statut == "completed":
                req.patch(_url(f"commandes?id=eq.{cmd['id']}"),
                    json={"statut": "termine", "progression": 100,
                          "note_admin": f"✅ BOOSTCI order ID: {boostci_id} | Livre"},
                    headers=_headers())
                updated += 1
            elif statut == "processing" or statut == "in progress":
                fait = max(qte - remains, 0)
                prog = min(int((fait / qte) * 100), 99) if qte > 0 else 0
                req.patch(_url(f"commandes?id=eq.{cmd['id']}"),
                    json={"progression": prog},
                    headers=_headers())
            elif statut in ("canceled", "cancelled", "refunded"):
                req.patch(_url(f"commandes?id=eq.{cmd['id']}"),
                    json={"statut": "refuse", "progression": 0,
                          "note_admin": f"❌ BOOSTCI order ID: {boostci_id} | Annule"},
                    headers=_headers())
                updated += 1
            elif statut == "partial":
                req.patch(_url(f"commandes?id=eq.{cmd['id']}"),
                    json={"statut": "termine", "progression": 100,
                          "note_admin": f"✅ BOOSTCI order ID: {boostci_id} | Partiel"},
                    headers=_headers())
                updated += 1
        except Exception as e:
            logger.error(f"Sync erreur: {e}")

    flash(f"✅ Sync termine ! {updated} commandes mises a jour.", "success")
    return redirect(url_for("admin_sync.index"))
