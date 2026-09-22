"""
Alerte de solde bas : envoyee UNE SEULE FOIS quand le solde passe sous le
seuil (pas a chaque commande), puis reinitialisee des que l'utilisateur
recharge - pour ne jamais spammer.
"""
import logging
from app.models.database import get_profile, update_profile
from app.models.mailer import email_solde_bas

logger = logging.getLogger(__name__)

SEUIL_SOLDE_BAS = 1000  # FCFA


def verifier_solde_bas(user_id, user_email, nom):
    """A appeler juste apres un debit de solde (commande)."""
    try:
        profile = get_profile(user_id)
        if not profile:
            return
        solde = profile.get("balance", 0) or 0
        if solde >= SEUIL_SOLDE_BAS:
            return
        if profile.get("alerte_solde_envoyee"):
            return  # deja alerte, on ne spamme pas tant qu'il n'a pas recharge

        if email_solde_bas(user_email, nom, solde):
            update_profile(user_id, {"alerte_solde_envoyee": True})
    except Exception as e:
        logger.error(f"verifier_solde_bas: {e}")


def reinitialiser_alerte_solde(user_id):
    """A appeler juste apres une recharge validee, pour reactiver l'alerte future."""
    try:
        update_profile(user_id, {"alerte_solde_envoyee": False})
    except Exception as e:
        logger.error(f"reinitialiser_alerte_solde: {e}")
