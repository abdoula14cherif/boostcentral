"""
Module BOOSTCI — Fournisseur de services SMM.
Toutes les commandes clients sont automatiquement
transmises a BOOSTCI avec une marge beneficiaire.
"""
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

# Marge beneficiaire en FCFA par commande
MARGE_FCFA = 200

def _post(data: dict) -> dict:
    """Envoie une requete a l API BOOSTCI."""
    try:
        api_url = current_app.config.get("BOOSTCI_API_URL", "https://boostci.com/api/v2")
        api_key = current_app.config.get("BOOSTCI_API_KEY", "")
        data["key"] = api_key
        r = requests.post(api_url, data=data, timeout=30)
        return r.json()
    except Exception as e:
        logger.error(f"BOOSTCI API erreur: {e}")
        return {"error": str(e)}

def get_services() -> list:
    """Recupere tous les services BOOSTCI."""
    result = _post({"action": "services"})
    if isinstance(result, list):
        return result
    return []

def add_order(service_id: int, link: str, quantity: int) -> dict:
    """
    Passe une commande chez BOOSTCI.
    Retourne {"order": ID} si succes ou {"error": msg} si echec.
    """
    return _post({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    })

def get_order_status(order_id: int) -> dict:
    """
    Verifie le statut d une commande BOOSTCI.
    Retourne {"status": "...", "remains": N, "charge": X}
    """
    return _post({
        "action": "status",
        "order": order_id
    })

def get_balance() -> float:
    """Recupere le solde du compte BOOSTCI."""
    result = _post({"action": "balance"})
    try:
        return float(result.get("balance", 0))
    except:
        return 0.0

def calculate_boostci_price(rate_per_1k: float, quantity: int) -> float:
    """
    Calcule le prix BOOSTCI en FCFA.
    rate_per_1k est en USD pour 1000 unites.
    """
    USD_RATE = 600.0
    price_usd = (rate_per_1k / 1000) * quantity
    return price_usd * USD_RATE

def calculate_client_price(rate_per_1k: float, quantity: int) -> float:
    """
    Calcule le prix client = prix BOOSTCI + marge de 200 FCFA.
    """
    boostci_price = calculate_boostci_price(rate_per_1k, quantity)
    return boostci_price + MARGE_FCFA
