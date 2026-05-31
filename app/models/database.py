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
