"""
Helper WhatsApp — Génère des liens contextuels avec message pré-rempli.
Le message s'adapte automatiquement à la page et à l'utilisateur connecté.
"""
import urllib.parse
from flask import current_app, session, request


def wa_link(message=None, context=None, extra=None):
    """
    Génère un lien WhatsApp avec message pré-rempli contextuel.

    Arguments :
    - message : texte personnalisé (prioritaire sur tout le reste)
    - context : 'dashboard', 'recharge', 'vente', 'admin', 'revendeur', 'affiliation', 'support', 'commande'
    - extra   : dict de données à injecter (ex: {'reference': 'xxx', 'montant': 5000})

    Utilisation dans un template :
        <a href="{{ wa_link() }}">Contacter le support</a>
        <a href="{{ wa_link('Mon message custom') }}">Ecrire</a>
        <a href="{{ wa_link(context='vente', extra={'reference': 'abc123'}) }}">Probleme achat</a>
    """
    num = current_app.config.get("WHATSAPP_NUMBER", "237658033690")

    # Si un message custom est fourni, on l'utilise directement
    if message:
        return f"https://wa.me/{num}?text={urllib.parse.quote(message)}"

    # Sinon, on construit un message selon le contexte
    user_email = session.get("user_email", "")
    path = request.path if request else "/"

    # Détection automatique du contexte si non fourni
    if not context:
        if path.startswith("/dashboard"):
            context = "dashboard"
        elif path.startswith("/recharge"):
            context = "recharge"
        elif path.startswith("/admin"):
            context = "admin"
        elif path.startswith("/revendeur"):
            context = "revendeur"
        elif path.startswith("/affiliation"):
            context = "affiliation"
        elif path.startswith("/support"):
            context = "support"
        elif "/p/" in path:
            context = "vente"
        else:
            context = "general"

    # Construction du message selon le contexte
    email_part = f"\nMon email : {user_email}" if user_email else ""
    extra = extra or {}

    if context == "dashboard":
        msg = (
            f"Bonjour Boost Central, j'ai besoin d'aide concernant mon compte."
            f"{email_part}\n\nPouvez-vous m'assister ?"
        )

    elif context == "recharge":
        txid = extra.get("txid", "")
        montant = extra.get("montant", "")
        details = ""
        if montant:
            details += f"\nMontant : {montant} FCFA"
        if txid:
            details += f"\nReference TXID : {txid}"
        msg = (
            f"Bonjour, j'ai un probleme de recharge sur mon compte."
            f"{email_part}{details}\n\nMon solde n'a pas ete credite. Pouvez-vous verifier ?"
        )

    elif context == "vente":
        ref = extra.get("reference", "")
        produit = extra.get("produit", "")
        montant = extra.get("montant", "")
        details = ""
        if produit:
            details += f"\nProduit : {produit}"
        if montant:
            details += f"\nMontant paye : {montant} FCFA"
        if ref:
            details += f"\nReference : {ref}"
        msg = (
            f"Bonjour, j'ai effectue un achat mais je n'ai pas recu mon produit."
            f"{email_part}{details}\n\nMerci de verifier et de m'envoyer mon produit."
        )

    elif context == "commande":
        order_id = extra.get("order_id", "")
        details = f"\nCommande n° : {order_id}" if order_id else ""
        msg = (
            f"Bonjour, j'ai une question sur ma commande."
            f"{email_part}{details}\n\nPouvez-vous m'aider ?"
        )

    elif context == "affiliation":
        msg = (
            f"Bonjour Boost Central, je souhaite devenir affilie et vendre vos produits."
            f"{email_part}\n\nPouvez-vous m'expliquer comment commencer ?"
        )

    elif context == "revendeur":
        msg = (
            f"Bonjour Boost Central, je souhaite devenir revendeur de vos services."
            f"{email_part}\n\nQuelles sont les conditions ?"
        )

    elif context == "support":
        sujet = extra.get("sujet", "")
        details = f"\nSujet : {sujet}" if sujet else ""
        msg = (
            f"Bonjour, j'ai besoin d'aide sur Boost Central."
            f"{email_part}{details}\n\nPouvez-vous m'assister ?"
        )

    elif context == "admin":
        msg = (
            f"Bonjour, intervention requise sur Boost Central."
            f"{email_part}\n\nMerci de verifier."
        )

    elif context == "produit":
        produit = extra.get("produit", "")
        details = f"\nProduit : {produit}" if produit else ""
        msg = (
            f"Bonjour, j'ai une question sur un produit Boost Central."
            f"{email_part}{details}"
        )

    else:  # general
        msg = (
            f"Bonjour Boost Central, j'ai une question."
            f"{email_part}\n\nPouvez-vous m'aider ?"
        )

    return f"https://wa.me/{num}?text={urllib.parse.quote(msg)}"