"""
Codes promo : bonus sur recharge (ex: +10% offert), cree et controle par toi
depuis l'admin. Cout maitrise : tu choisis le taux, tu peux desactiver ou
limiter le nombre d'utilisations a tout moment.
"""
import logging
from datetime import datetime, timezone
from app.models.database import get_promo_code, has_user_used_code

logger = logging.getLogger(__name__)


def valider_code(code, user_id):
    """
    Verifie qu'un code promo est utilisable par cet utilisateur.
    Retourne (ok: bool, message: str, promo: dict|None)
    """
    if not code:
        return False, "Code manquant.", None

    promo = get_promo_code(code.strip().upper())
    if not promo:
        return False, "Code promo invalide.", None

    if not promo.get("actif"):
        return False, "Ce code promo n'est plus actif.", None

    max_util = promo.get("max_utilisations")
    if max_util is not None and (promo.get("utilisations_count") or 0) >= max_util:
        return False, "Ce code promo a atteint sa limite d'utilisation.", None

    date_exp = promo.get("date_expiration")
    if date_exp:
        try:
            exp = datetime.fromisoformat(date_exp.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) > exp:
                return False, "Ce code promo a expire.", None
        except Exception as e:
            logger.error(f"parse date_expiration: {e}")

    if has_user_used_code(user_id, promo["id"]):
        return False, "Vous avez deja utilise ce code promo.", None

    return True, f"Code valide : +{round(promo['bonus_pct']*100)}% offert !", promo
