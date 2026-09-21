"""
Moteur de tarification revendeur. Centralise ici pour que dashboard.py,
la commande groupee et l'API publique appliquent tous exactement la meme
regle, sans divergence.
"""
import logging
import requests as req
from flask import current_app
from app.models.database import get_client_revendeur, get_revendeur_prix, get_total_recharged, credit_balance
from app.models.vip import get_vip_tier, calculer_remise_totale

logger = logging.getLogger(__name__)


def _headers():
    key = current_app.config["SUPABASE_SERVICE_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}


def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path


def calculer_prix_ligne(user_id, service, quantity):
    """
    Determine le prix a payer pour une ligne de commande, en tenant compte
    d'un eventuel revendeur auquel le client est rattache.

    Retourne (unit_price, total_price, revendeur_info).
    revendeur_info est None si le client n'est rattache a aucun revendeur.
    """
    revendeur = get_client_revendeur(user_id)
    base_unit_price = float(service["prix_fcfa"])

    logger.info(f"DEBUG revendeur: client={user_id} service={service.get('id')} revendeur_trouve={bool(revendeur)}")
    if revendeur:
        logger.info(f"DEBUG revendeur: modele={revendeur.get('revendeur_modele')} revendeur_id={revendeur.get('id')}")

    if revendeur and revendeur.get("revendeur_modele") == "marge":
        custom = get_revendeur_prix(revendeur["id"], service["id"])
        logger.info(f"DEBUG revendeur: prix_personnalise_trouve={bool(custom)}")
        if custom:
            unit_price = float(custom["prix_fcfa"])
            total_price = round(unit_price * quantity)
            return unit_price, total_price, {"revendeur": revendeur, "type": "marge", "base_unit_price": base_unit_price}

    # Prix standard (VIP + volume) - s'applique si pas de revendeur, ou revendeur
    # en mode commission, ou revendeur en mode marge sans prix personnalise pour ce service
    remise_vip = get_vip_tier(get_total_recharged(user_id))["remise"]
    remise_totale = calculer_remise_totale(remise_vip, quantity)
    total_price = round(base_unit_price * quantity * (1 - remise_totale))

    if revendeur and revendeur.get("revendeur_modele") == "commission":
        return base_unit_price, total_price, {"revendeur": revendeur, "type": "commission", "base_unit_price": base_unit_price}

    return base_unit_price, total_price, None


def crediter_revendeur(revendeur_info, quantity, total_price, client_id, order_id):
    """
    Credite le revendeur APRES la creation reelle de la commande (jamais avant) :
    - mode marge : la difference entre son prix et le prix de base Boost Central
    - mode commission : son pourcentage sur le total paye
    Toujours une fraction de ce que le client vient reellement de payer -
    jamais d'argent verse que tu n'as pas deja encaisse.
    """
    logger.info(f"DEBUG crediter_revendeur appele: revendeur_info={revendeur_info}, quantity={quantity}, total_price={total_price}, client_id={client_id}, order_id={order_id}")

    if not revendeur_info:
        logger.info("DEBUG crediter_revendeur: revendeur_info est None, aucun credit (client non rattache ou pas de prix personnalise trouve)")
        return
    try:
        revendeur = revendeur_info["revendeur"]
        if revendeur_info["type"] == "marge":
            gain = round(total_price - revendeur_info["base_unit_price"] * quantity)
        else:
            gain = round(total_price * float(revendeur.get("revendeur_commission_pct") or 0))

        logger.info(f"DEBUG crediter_revendeur: type={revendeur_info['type']}, base_unit_price={revendeur_info['base_unit_price']}, gain calcule={gain}")

        if gain <= 0:
            logger.info(f"DEBUG crediter_revendeur: gain <= 0 ({gain}), rien credite")
            return

        credit_balance(revendeur["id"], gain)
        req.post(_url("revendeur_gains"), json={
            "revendeur_id": revendeur["id"], "client_id": client_id,
            "order_id": order_id, "montant": gain
        }, headers=_headers())
        logger.info(f"Revendeur {revendeur.get('email')} credite de {gain} FCFA (type={revendeur_info['type']})")
    except Exception as e:
        logger.error(f"crediter_revendeur: {e}")
