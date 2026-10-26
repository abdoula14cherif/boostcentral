"""
Configuration Boost Central.
Version securisee pour production (Vercel).
"""
import os
from datetime import timedelta


class BaseConfig:
    # ─── SECRET_KEY ──────────────────────────────────────────
    # En prod, doit etre absolument defini sur Vercel
    SECRET_KEY = os.environ.get("SECRET_KEY", "boostcentral-dev-secret-key-change-in-prod")

    # ─── CSRF (Securite active) ──────────────────────────────
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600  # 1 heure
    WTF_CSRF_SSL_STRICT = False  # Garder False car Vercel fait le proxy SSL

    # ─── Sessions (Optimisé pour Vercel/HTTPS) ───────────────
    # IMPORTANT : Doit être True en production (HTTPS)
    SESSION_COOKIE_SECURE = True 
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
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
    # En local (HTTP), on doit désactiver le cookie sécurisé sinon on ne peut pas se connecter
    SESSION_COOKIE_SECURE = False
    # On peut se permettre d'être un peu plus souple en dev
    WTF_CSRF_SSL_STRICT = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    # En prod (HTTPS), sécurisé à 100%
    SESSION_COOKIE_SECURE = True
    

config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}