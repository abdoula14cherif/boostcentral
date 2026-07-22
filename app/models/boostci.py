"""
Module BOOSTCI — Fournisseur SMM automatique.
Marge : prix BOOSTCI x 2 (tu vends le double du prix fournisseur)
"""
import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)

USD_RATE = 600.0        # 1 USD = 600 FCFA
MULTIPLICATEUR = 1.0    # Tu ajoutes 1F fixe par unite

def _post(data: dict) -> dict:
    try:
        url = current_app.config.get("BOOSTCI_API_URL", "https://boostci.com/api/v2")
        key = current_app.config.get("BOOSTCI_API_KEY", "")
        data["key"] = key
        r = requests.post(url, data=data, timeout=30)
        return r.json()
    except Exception as e:
        logger.error(f"BOOSTCI erreur: {e}")
        return {"error": str(e)}

def get_services() -> list:
    result = _post({"action": "services"})
    return result if isinstance(result, list) else []

def get_balance() -> float:
    result = _post({"action": "balance"})
    try:
        return float(result.get("balance", 0))
    except:
        return 0.0

def add_order(service_id: int, link: str, quantity: int) -> dict:
    return _post({
        "action": "add",
        "service": service_id,
        "link": link,
        "quantity": quantity
    })

def get_order_status(order_id: int) -> dict:
    return _post({"action": "status", "order": order_id})

def prix_boostci_fcfa(rate_per_1k: float, quantity: int) -> float:
    """Prix reel BOOSTCI en FCFA."""
    return (rate_per_1k / 1000) * quantity * USD_RATE

MARGE_PAR_UNITE = 1.0   # +1 FCFA par unite vendue

def prix_client_fcfa(rate_per_1k: float, quantity: int) -> float:
    """Prix client = prix BOOSTCI + 1 FCFA par unite."""
    return prix_boostci_fcfa(rate_per_1k, quantity) + (MARGE_PAR_UNITE * quantity)
