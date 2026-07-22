"""
Module d automatisation — tache de fond.
Appele via /auto/sync pour mettre a jour les commandes BOOSTCI.
"""
import logging
import requests as req
from flask import Blueprint, jsonify, current_app
from app.models.boostci import get_order_status, get_balance

logger = logging.getLogger(__name__)
auto_bp = Blueprint("auto", __name__)

def _admin_headers():
    key = current_app.config.get("SUPABASE_SERVICE_KEY")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path

@auto_bp.route("/sync")
def sync():
    """
    Verifie et met a jour toutes les commandes BOOSTCI en cours.
    Appeler via cron ou manuellement.
    """
    try:
        # Recuperer commandes en_cours avec ID BOOSTCI
        r = req.get(
            _url("commandes?statut=eq.en_cours&order=created_at.desc&limit=50"),
            headers=_admin_headers()
        )
        commandes = r.json() if isinstance(r.json(), list) else []

        updated = 0
        errors = 0

        for cmd in commandes:
            note = cmd.get("note_admin", "")
            if "BOOSTCI order ID:" not in note:
                continue

            # Extraire l ID BOOSTCI
            try:
                boostci_order_id = int(note.split("BOOSTCI order ID:")[-1].strip().split()[0])
            except:
                continue

            # Verifier le statut
            status = get_order_status(boostci_order_id)
            s = status.get("status", "").lower()
            remains = int(status.get("remains", 0))
            charge = status.get("charge", 0)

            nouveau_statut = None
            progression = cmd.get("progression", 0)

            if s == "completed":
                nouveau_statut = "termine"
                progression = 100
            elif s == "in progress" or s == "processing":
                nouveau_statut = "en_cours"
                qte = cmd.get("quantite", 1)
                fait = qte - remains
                progression = min(int((fait / qte) * 100), 99) if qte > 0 else 0
            elif s in ("cancelled", "canceled", "refunded"):
                nouveau_statut = "refuse"
                progression = 0
            elif s == "partial":
                nouveau_statut = "termine"
                progression = 100

            if nouveau_statut:
                req.patch(
                    _url(f"commandes?id=eq.{cmd['id']}"),
                    json={
                        "statut": nouveau_statut,
                        "progression": progression,
                        "note_admin": f"✅ BOOSTCI order ID: {boostci_order_id} | Statut: {s}"
                    },
                    headers=_admin_headers()
                )
                updated += 1

        # Verifier solde BOOSTCI
        solde = get_balance()

        return jsonify({
            "ok": True,
            "commandes_verifiees": len(commandes),
            "mises_a_jour": updated,
            "erreurs": errors,
            "solde_boostci_usd": solde
        })

    except Exception as e:
        logger.error(f"auto_sync erreur: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@auto_bp.route("/import-services")
def import_services():
    """Import automatique de tous les services BOOSTCI detectes."""
    from app.models.boostci import get_services, prix_client_fcfa

    RESEAU_MAP = {
        "facebook": "facebook", "instagram": "instagram", "tiktok": "tiktok",
        "youtube": "youtube", "twitter": "twitter", "telegram": "telegram",
        "spotify": "spotify", "whatsapp": "whatsapp"
    }

    def detect_reseau(name, category):
        txt = (name + " " + category).lower()
        for r in RESEAU_MAP:
            if r in txt:
                return r
        return None

    services = get_services()
    importe = 0
    ignore = 0

    for s in services:
        reseau = detect_reseau(s.get("name", ""), s.get("category", ""))
        if not reseau:
            ignore += 1
            continue

        rate = float(s.get("rate", 0))
        if rate <= 0:
            ignore += 1
            continue

        # Prix BOOSTCI en FCFA par unite + 1F de marge
        prix_boostci_unite = (rate / 1000) * 600
        prix_client_unite = prix_boostci_unite + 1.0
        prix_client_unite = max(round(prix_client_unite, 4), 0.01)

        try:
            r = req.post(_url("services"), json={
                "reseau": reseau,
                "categorie": s.get("name", ""),
                "prix_fcfa": prix_client_unite,
                "min_qte": int(s.get("min", 100)),
                "max_qte": int(s.get("max", 100000)),
                "description": s.get("description", ""),
                "actif": True,
                "boostci_service_id": int(s.get("service", 0))
            }, headers=_admin_headers())

            if r.status_code in (200, 201):
                importe += 1
            else:
                logger.error(f"Import erreur: {r.text}")
                ignore += 1
        except Exception as e:
            logger.error(f"Import exception: {e}")
            ignore += 1

    return jsonify({
        "ok": True,
        "importe": importe,
        "ignore": ignore,
        "total": len(services)
    })

@auto_bp.route("/solde")
def solde():
    """Verifie le solde BOOSTCI."""
    try:
        s = get_balance()
        return jsonify({"ok": True, "solde_usd": s, "solde_fcfa": s * 600})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})
