"""
Configuration Boost Central.
SÉCURITÉ SÉVÈRE : cles obligatoires, CSRF actif, sessions securisees.
"""
import os
from datetime import timedelta


def _get_secret():
    """Recupere SECRET_KEY de maniere securisee."""
    key = os.environ.get("SECRET_KEY", "").strip()
    if not key or key == "changez-moi":
        if os.environ.get("FLASK_ENV") == "development":
            import secrets
            return secrets.token_hex(64)
        raise RuntimeError(
            "❌ SECRET_KEY obligatoire en production ! "
            "Genere avec : python -c \"import secrets; print(secrets.token_hex(64))\""
        )
    if len(key) < 32:
        raise RuntimeError(f"❌ SECRET_KEY trop courte ({len(key)} chars, min 32).")
    return key


class BaseConfig:
    # ─── SECRET_KEY (obligatoire) ─────────────────────────────
    SECRET_KEY = _get_secret()

    # ─── CSRF (ACTIF) ─────────────────────────────────────────
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False  # True si tout en HTTPS

    # ─── Sessions securisees ──────────────────────────────────
    SESSION_COOKIE_SECURE = True          # HTTPS uniquement
    SESSION_COOKIE_HTTPONLY = True        # Inaccessible en JS
    SESSION_COOKIE_SAMESITE = "Lax"       # Anti-CSRF
    PERMANENT_SESSION_LIFETIME = timedelta(hours=24)
    SESSION_REFRESH_EACH_REQUEST = True

    # ─── Limite upload ────────────────────────────────────────
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 Mo

    # ─── Supabase ─────────────────────────────────────────────
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")

    # ─── Admin ────────────────────────────────────────────────
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "abdoula13cherif@gmail.com")

    # ─── Contact ──────────────────────────────────────────────
    WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "237658033690")

    # ─── Paiements ────────────────────────────────────────────
    SOINA_PAY_URL = os.environ.get("SOINA_PAY_URL", "https://soinapay.com/pay/zmnmqbap")

    # ─── Email ────────────────────────────────────────────────
    GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

    # ─── Fournisseur BOOSTCI ──────────────────────────────────
    BOOSTCI_API_KEY = os.environ.get("BOOSTCI_API_KEY", "")
    BOOSTCI_API_URL = os.environ.get("BOOSTCI_API_URL", "https://boostci.com/api/v2")

    # ─── Pagination ───────────────────────────────────────────
    ORDERS_PER_PAGE = 20
    RECHARGES_PER_PAGE = 10

    # ─── Taux ─────────────────────────────────────────────────
    USD_RATE = 600.0

    # ─── Rate limiting ────────────────────────────────────────
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    RATELIMIT_HEADERS_ENABLED = True


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    WTF_CSRF_ENABLED = False   # ⚠️ Uniquement en dev
    SESSION_COOKIE_SECURE = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = True


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}