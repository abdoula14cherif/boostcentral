"""
Module Email — Envoi automatique des notifications.
Utilise Gmail SMTP.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)

GMAIL = "abdoula13cherif@gmail.com"
ADMIN_EMAIL = "abdoula13cherif@gmail.com"


def _send(to, subject, html_body):
    """Envoie un email via Gmail SMTP."""
    try:
        password = current_app.config.get("GMAIL_APP_PASSWORD", "")
        if not password:
            logger.warning("GMAIL_APP_PASSWORD non configure")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"Boost Central <{GMAIL}>"
        msg["To"] = to

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL, password)
            server.sendmail(GMAIL, [to], msg.as_string())

        logger.info(f"Email envoye a {to}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Email erreur: {e}")
        return False


def _template(titre, contenu, couleur="#0066FF", couleur2="#0047CC", emoji="⚡", eyebrow="BOOST CENTRAL"):
    """Template HTML commun — design premium pour tous les emails."""
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;padding:0;background:#EEF2F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif}}
.wrap{{padding:32px 16px}}
.container{{max-width:560px;margin:0 auto;background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 10px 40px rgba(15,23,42,.10)}}
.header{{background:linear-gradient(135deg,{couleur},{couleur2});padding:38px 30px 34px;text-align:center;position:relative}}
.header .badge{{display:inline-flex;align-items:center;justify-content:center;width:56px;height:56px;background:rgba(255,255,255,.18);border-radius:16px;font-size:1.7rem;margin-bottom:14px}}
.header .eyebrow{{color:rgba(255,255,255,.75);font-size:.72rem;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;margin:0 0 6px}}
.header h1{{color:#fff;margin:0;font-size:1.3rem;font-weight:800;line-height:1.35}}
.body{{padding:32px 30px 28px}}
.body p{{color:#475569;line-height:1.7;margin:0 0 14px;font-size:.94rem}}
.box{{background:#F8FAFC;border-radius:14px;padding:18px 20px;margin:18px 0;border:1px solid #E2E8F0}}
.box .row{{display:flex;justify-content:space-between;align-items:center;padding:6px 0;font-size:.86rem}}
.box .row+.row{{border-top:1px dashed #E2E8F0}}
.box .row span:first-child{{color:#64748B}}
.box .row span:last-child{{color:#0F172A;font-weight:700;text-align:right}}
.btn-wrap{{text-align:center;margin:24px 0 8px}}
.btn{{display:inline-block;background:linear-gradient(90deg,#FF6600,#E65C00);color:#fff !important;padding:14px 34px;border-radius:12px;text-decoration:none;font-weight:800;font-size:.92rem;box-shadow:0 8px 20px rgba(255,102,0,.28)}}
.footer{{background:#0F172A;padding:24px 30px;text-align:center;color:rgba(255,255,255,.45);font-size:.76rem;line-height:1.7}}
.footer a{{color:rgba(255,255,255,.75);text-decoration:none;font-weight:600}}
.small-note{{color:#94A3B8;font-size:.8rem;margin-top:22px}}
</style>
</head>
<body>
<div class="wrap">
<div class="container">
<div class="header">
<div class="badge">{emoji}</div>
<p class="eyebrow">{eyebrow}</p>
<h1>{titre}</h1>
</div>
<div class="body">
{contenu}
<p class="small-note">Si vous n avez pas effectue cette action, ignorez cet email ou contactez-nous.</p>
</div>
<div class="footer">
<p>Boost Central • <a href="https://wa.me/237689011185">Support WhatsApp</a></p>
<p>Cet email a ete envoye automatiquement, ne pas repondre.</p>
</div>
</div>
</div>
</body>
</html>"""


# ─── EMAILS CLIENTS ─────────────────────────────────────────────

def email_commande_passee(to_email, nom, service, quantite, prix_total, lien):
    """Email de confirmation de commande."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre commande a bien ete enregistree et est en cours de traitement. Notre equipe s en occupe !</p>
<div class="box">
<div class="row"><span>Service</span><span>{service}</span></div>
<div class="row"><span>Quantite</span><span>{quantite:,}</span></div>
<div class="row"><span>Prix total</span><span>{prix_total:,.0f} FCFA</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Voir ma commande</a></div>
"""
    return _send(to_email, "✅ Commande confirmee — Boost Central",
                 _template("Votre commande est en cours !", contenu, emoji="🚀"))


def email_commande_livree(to_email, nom, service, quantite):
    """Email de livraison de commande."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Excellente nouvelle ! Votre commande a ete livree avec succes.</p>
<div class="box">
<div class="row"><span>Service</span><span>{service}</span></div>
<div class="row"><span>Quantite livree</span><span>{quantite:,}</span></div>
<div class="row"><span>Statut</span><span style="color:#059669">✅ Termine</span></div>
</div>
<p>Merci pour votre confiance. N hesitez pas a passer une nouvelle commande !</p>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Passer une nouvelle commande</a></div>
"""
    return _send(to_email, "🎉 Commande livree — Boost Central",
                 _template("Votre commande est livree !", contenu, "#059669", "#047857", emoji="🎉"))


def email_recharge_validee(to_email, nom, montant):
    """Email de confirmation de recharge."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre recharge a ete validee et votre solde a ete credite avec succes !</p>
<div class="box">
<div class="row"><span>Montant credite</span><span>{montant:,.0f} FCFA</span></div>
<div class="row"><span>Statut</span><span style="color:#059669">✅ Valide</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Utiliser mon solde</a></div>
"""
    return _send(to_email, "💰 Recharge validee — Boost Central",
                 _template("Votre solde a ete credite !", contenu, "#059669", "#047857", emoji="💰"))


def email_solde_insuffisant(to_email, nom, solde, requis):
    """Email de solde insuffisant."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre tentative de commande n a pas pu aboutir car votre solde est insuffisant.</p>
<div class="box">
<div class="row"><span>Votre solde</span><span>{solde:,.0f} FCFA</span></div>
<div class="row"><span>Montant requis</span><span>{requis:,.0f} FCFA</span></div>
<div class="row"><span>Manque</span><span style="color:#DC2626">{requis - solde:,.0f} FCFA</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/recharge/" class="btn">Recharger mon compte</a></div>
"""
    return _send(to_email, "⚠️ Solde insuffisant — Boost Central",
                 _template("Solde insuffisant", contenu, "#FF6600", "#E65C00", emoji="⚠️"))


def email_solde_bas(to_email, nom, solde):
    """Alerte preventive quand le solde passe sous le seuil (avant meme d'etre a court)."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre solde Boost Central commence a etre bas. Rechargez maintenant pour continuer a booster vos reseaux sans interruption.</p>
<div class="box">
<div class="row"><span>Solde actuel</span><span style="color:#DC2626">{solde:,.0f} FCFA</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/recharge/" class="btn">Recharger mon compte</a></div>
"""
    return _send(to_email, "🔔 Votre solde est bas — Boost Central",
                 _template("Pensez a recharger !", contenu, "#FF6600", "#E65C00", emoji="🔔"))


def email_inactivite(to_email, nom):
    """Relance automatique apres 2 semaines sans commande (envoyee par tache planifiee)."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Ca fait un moment qu on ne vous a pas vu sur Boost Central ! Vos reseaux sociaux n attendent que vous pour grandir.</p>
<div class="box">
<div class="row"><span>Followers, vues, likes, commentaires</span><span>Disponibles</span></div>
<div class="row"><span>Paiement</span><span>Mobile Money / Carte</span></div>
</div>
<p>Revenez quand vous voulez, votre compte et votre solde vous attendent.</p>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Retourner sur Boost Central</a></div>
"""
    return _send(to_email, "👋 On ne vous voit plus — Boost Central",
                 _template("Vous nous manquez !", contenu, "#7C3AED", "#6D28D9", emoji="👋"))


# ─── EMAILS ADMIN ────────────────────────────────────────────────

def email_admin_nouvelle_inscription(user_email, nom, pays):
    """Notifie l admin d une nouvelle inscription."""
    contenu = f"""
<p>Un nouvel utilisateur vient de s inscrire sur Boost Central !</p>
<div class="box">
<div class="row"><span>Nom</span><span>{nom}</span></div>
<div class="row"><span>Email</span><span>{user_email}</span></div>
<div class="row"><span>Pays</span><span>{pays or 'Non renseigne'}</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/admin/users/" class="btn">Voir les utilisateurs</a></div>
"""
    return _send(ADMIN_EMAIL, f"👤 Nouvelle inscription : {user_email}",
                 _template("Nouvelle inscription !", contenu, emoji="👤"))


def email_admin_nouvelle_commande(user_email, service, quantite, prix_total, lien):
    """Notifie l admin d une nouvelle commande."""
    contenu = f"""
<p>Un client vient de passer une nouvelle commande !</p>
<div class="box">
<div class="row"><span>Client</span><span>{user_email}</span></div>
<div class="row"><span>Service</span><span>{service}</span></div>
<div class="row"><span>Quantite</span><span>{quantite:,}</span></div>
<div class="row"><span>Prix total</span><span>{prix_total:,.0f} FCFA</span></div>
</div>
<div class="btn-wrap"><a href="https://boostcentral-eta.vercel.app/admin/" class="btn">Voir les commandes</a></div>
"""
    return _send(ADMIN_EMAIL, f"🚀 Nouvelle commande : {service}",
                 _template("Nouvelle commande !", contenu, "#FF6600", "#E65C00", emoji="🚀"))
