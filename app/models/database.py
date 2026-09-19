import logging
import requests
from flask import current_app

logger = logging.getLogger(__name__)


def _headers(admin=False):
    url = current_app.config["SUPABASE_URL"]
    key = current_app.config["SUPABASE_SERVICE_KEY"] if admin else current_app.config["SUPABASE_ANON_KEY"]
    return {"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json", "Prefer": "return=representation"}


def _url(path):
    return current_app.config["SUPABASE_URL"] + "/rest/v1/" + path


def get_supabase():
    return None


def get_supabase_admin():
    return None


def get_profile(user_id):
    try:
        r = requests.get(_url(f"profiles?id=eq.{user_id}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_profile: {e}")
        return None


def update_balance(user_id, new_balance):
    try:
        r = requests.patch(_url(f"profiles?id=eq.{user_id}"), json={"balance": new_balance}, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"update_balance: {e}")
        return False


def credit_balance(user_id, amount):
    try:
        profile = get_profile(user_id)
        if not profile:
            return None
        new_bal = (profile.get("balance") or 0) + amount
        if update_balance(user_id, new_bal):
            return new_bal
        return None
    except Exception as e:
        logger.error(f"credit_balance: {e}")
        return None


def debit_balance(user_id, amount):
    try:
        profile = get_profile(user_id)
        if not profile:
            return None
        current = profile.get("balance") or 0
        if current < amount:
            return None
        new_bal = current - amount
        if update_balance(user_id, new_bal):
            return new_bal
        return None
    except Exception as e:
        logger.error(f"debit_balance: {e}")
        return None


def get_active_services(network=None):
    try:
        if network:
            url = _url(f"services?actif=eq.true&reseau=eq.{network}&order=categorie")
        else:
            url = _url("services?actif=eq.true&order=reseau,categorie")
        r = requests.get(url, headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_active_services: {e}")
        return []


def get_service_by_id(service_id):
    try:
        r = requests.get(_url(f"services?id=eq.{service_id}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_service_by_id: {e}")
        return None


def create_order(data):
    try:
        r = requests.post(_url("commandes"), json=data, headers=_headers(True))
        result = r.json()
        if isinstance(result, list) and result:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"create_order: {e}")
        return None


def get_user_orders(user_id, limit=20):
    try:
        r = requests.get(_url(f"commandes?user_id=eq.{user_id}&order=created_at.desc&limit={limit}"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_user_orders: {e}")
        return []


def get_order_by_id_for_user(order_id, user_id):
    try:
        r = requests.get(_url(f"commandes?id=eq.{order_id}&user_id=eq.{user_id}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_order_by_id_for_user: {e}")
        return None


def get_all_orders(limit=100):
    try:
        r = requests.get(_url(f"commandes?order=created_at.desc&limit={limit}"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_all_orders: {e}")
        return []


def update_order(order_id, data):
    try:
        r = requests.patch(_url(f"commandes?id=eq.{order_id}"), json=data, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"update_order: {e}")
        return False


def create_recharge(data):
    try:
        r = requests.post(_url("recharges"), json=data, headers=_headers(True))
        result = r.json()
        if isinstance(result, list) and result:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"create_recharge: {e}")
        return None


def get_user_recharges(user_id, limit=10):
    try:
        r = requests.get(_url(f"recharges?user_id=eq.{user_id}&order=created_at.desc&limit={limit}"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_user_recharges: {e}")
        return []


def get_all_recharges(limit=50):
    try:
        r = requests.get(_url(f"recharges?order=created_at.desc&limit={limit}"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_all_recharges: {e}")
        return []


def get_recharge_by_hash(hash_tx):
    """Retrouve une recharge via sa reference (utilise par le webhook SoleasPay pour matcher invoice_reference)."""
    try:
        r = requests.get(_url(f"recharges?hash_tx=eq.{hash_tx}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_recharge_by_hash: {e}")
        return None


def update_recharge(recharge_id, data):
    try:
        r = requests.patch(_url(f"recharges?id=eq.{recharge_id}"), json=data, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"update_recharge: {e}")
        return False


def get_all_users():
    try:
        r = requests.get(_url("profiles?order=created_at.desc"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        logger.error(f"get_all_users: {e}")
        return []


def get_profile_by_api_key(api_key):
    try:
        r = requests.get(_url(f"profiles?api_key=eq.{api_key}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_profile_by_api_key: {e}")
        return None


def set_api_key(user_id, api_key):
    try:
        r = requests.patch(_url(f"profiles?id=eq.{user_id}"), json={"api_key": api_key}, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"set_api_key: {e}")
        return False


def get_total_recharged(user_id):
    """Somme des recharges VALIDEES (argent reellement recu) - base du programme VIP."""
    try:
        r = requests.get(_url(f"recharges?user_id=eq.{user_id}&statut=eq.valide&select=montant_fcfa"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list):
            return sum(row.get("montant_fcfa", 0) or 0 for row in data)
        return 0
    except Exception as e:
        logger.error(f"get_total_recharged: {e}")
        return 0


def update_profile(user_id, data):
    """Mise a jour generique d'un profil (champs divers : vip_tier_vu, etc.)."""
    try:
        r = requests.patch(_url(f"profiles?id=eq.{user_id}"), json=data, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"update_profile: {e}")
        return False


def get_promo_code(code):
    """Recupere un code promo par son code (insensible a la casse cote appelant)."""
    try:
        r = requests.get(_url(f"promo_codes?code=eq.{code}&limit=1"), headers=_headers(True))
        data = r.json()
        if isinstance(data, list) and data:
            return data[0]
        return None
    except Exception as e:
        logger.error(f"get_promo_code: {e}")
        return None


def get_all_promo_codes():
    try:
        r = requests.get(_url("promo_codes?order=created_at.desc"), headers=_headers(True))
        data = r.json()
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"get_all_promo_codes: {e}")
        return []


def create_promo_code(data):
    try:
        r = requests.post(_url("promo_codes"), json=data, headers=_headers(True))
        result = r.json()
        if isinstance(result, list) and result:
            return result[0]
        return None
    except Exception as e:
        logger.error(f"create_promo_code: {e}")
        return None


def update_promo_code(code_id, data):
    try:
        r = requests.patch(_url(f"promo_codes?id=eq.{code_id}"), json=data, headers=_headers(True))
        return r.status_code < 300
    except Exception as e:
        logger.error(f"update_promo_code: {e}")
        return False


def has_user_used_code(user_id, code_id):
    try:
        r = requests.get(_url(f"promo_utilisations?user_id=eq.{user_id}&code_id=eq.{code_id}&limit=1"), headers=_headers(True))
        data = r.json()
        return isinstance(data, list) and len(data) > 0
    except Exception as e:
        logger.error(f"has_user_used_code: {e}")
        return True  # par securite, on bloque en cas d'erreur plutot que de laisser abuser


def enregistrer_utilisation_code(code_id, user_id, recharge_id):
    try:
        requests.post(_url("promo_utilisations"), json={
            "code_id": code_id, "user_id": user_id, "recharge_id": recharge_id
        }, headers=_headers(True))
        # Incrementer le compteur d'utilisations
        code = requests.get(_url(f"promo_codes?id=eq.{code_id}&limit=1"), headers=_headers(True)).json()
        if code:
            current = code[0].get("utilisations_count", 0) or 0
            update_promo_code(code_id, {"utilisations_count": current + 1})
        return True
    except Exception as e:
        logger.error(f"enregistrer_utilisation_code: {e}")
        return False
