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

def _template(titre, contenu, couleur="#0066FF"):
    """Template HTML commun pour tous les emails."""
    return f"""
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{margin:0;padding:0;background:#F8FAFC;font-family:'Segoe UI',Arial,sans-serif}}
.container{{max-width:580px;margin:30px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08)}}
.header{{background:linear-gradient(135deg,{couleur},#0047CC);padding:32px 28px;text-align:center}}
.header h1{{color:#fff;margin:0;font-size:1.4rem;font-weight:800}}
.header p{{color:rgba(255,255,255,.85);margin:8px 0 0;font-size:.9rem}}
.body{{padding:28px}}
.body p{{color:#475569;line-height:1.7;margin-bottom:14px;font-size:.92rem}}
.box{{background:#F1F5F9;border-radius:12px;padding:16px;margin:16px 0;border-left:4px solid {couleur}}}
.box p{{margin:4px 0;font-size:.88rem}}
.btn{{display:inline-block;background:linear-gradient(90deg,#FF6600,#E65C00);color:#fff;padding:12px 28px;border-radius:10px;text-decoration:none;font-weight:700;font-size:.9rem;margin:16px 0}}
.footer{{background:#1E293B;padding:20px;text-align:center;color:rgba(255,255,255,.5);font-size:.78rem}}
.footer a{{color:rgba(255,255,255,.7);text-decoration:none}}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>⚡ BOOST CENTRAL</h1>
<p>Boostez votre presence en ligne</p>
</div>
<div class="body">
<h2 style="color:#1E293B;font-size:1.1rem;margin-bottom:16px">{titre}</h2>
{contenu}
<p style="color:#94A3B8;font-size:.82rem;margin-top:24px">Si vous n avez pas effectue cette action, ignorez cet email ou contactez-nous.</p>
</div>
<div class="footer">
<p>Boost Central • <a href="https://wa.me/237689011185">Support WhatsApp</a></p>
<p>Cet email a ete envoye automatiquement, ne pas repondre.</p>
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
<p><strong>Service :</strong> {service}</p>
<p><strong>Quantite :</strong> {quantite:,}</p>
<p><strong>Prix total :</strong> {prix_total:,.0f} FCFA</p>
<p><strong>Lien :</strong> {lien[:60]}...</p>
</div>
<p>Vous pouvez suivre l avancement de votre commande depuis votre dashboard.</p>
<a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Voir ma commande</a>
"""
    return _send(to_email, "✅ Commande confirmee — Boost Central",
                 _template("Votre commande est en cours !", contenu))

def email_commande_livree(to_email, nom, service, quantite):
    """Email de livraison de commande."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Excellente nouvelle ! Votre commande a ete livree avec succes. 🎉</p>
<div class="box">
<p><strong>Service :</strong> {service}</p>
<p><strong>Quantite livree :</strong> {quantite:,}</p>
<p><strong>Statut :</strong> ✅ Termine</p>
</div>
<p>Merci pour votre confiance. N hesitez pas a passer une nouvelle commande !</p>
<a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Passer une nouvelle commande</a>
"""
    return _send(to_email, "🎉 Commande livree — Boost Central",
                 _template("Votre commande est livree !", contenu, "#059669"))

def email_recharge_validee(to_email, nom, montant):
    """Email de confirmation de recharge."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre recharge a ete validee et votre solde a ete credite avec succes !</p>
<div class="box">
<p><strong>Montant credite :</strong> {montant:,.0f} FCFA</p>
<p><strong>Statut :</strong> ✅ Valide</p>
</div>
<p>Vous pouvez maintenant utiliser votre solde pour booster vos reseaux sociaux.</p>
<a href="https://boostcentral-eta.vercel.app/dashboard/" class="btn">Utiliser mon solde</a>
"""
    return _send(to_email, "💰 Recharge validee — Boost Central",
                 _template("Votre solde a ete credite !", contenu, "#059669"))

def email_solde_insuffisant(to_email, nom, solde, requis):
    """Email de solde insuffisant."""
    contenu = f"""
<p>Bonjour <strong>{nom}</strong>,</p>
<p>Votre tentative de commande n a pas pu aboutir car votre solde est insuffisant.</p>
<div class="box">
<p><strong>Votre solde :</strong> {solde:,.0f} FCFA</p>
<p><strong>Montant requis :</strong> {requis:,.0f} FCFA</p>
<p><strong>Manque :</strong> {requis - solde:,.0f} FCFA</p>
</div>
<p>Rechargez votre compte pour continuer a booster vos reseaux !</p>
<a href="https://boostcentral-eta.vercel.app/recharge/" class="btn">Recharger mon compte</a>
"""
    return _send(to_email, "⚠️ Solde insuffisant — Boost Central",
                 _template("Solde insuffisant", contenu, "#FF6600"))

# ─── EMAILS ADMIN ────────────────────────────────────────────────

def email_admin_nouvelle_inscription(user_email, nom, pays):
    """Notifie l admin d une nouvelle inscription."""
    contenu = f"""
<p>Un nouvel utilisateur vient de s inscrire sur Boost Central !</p>
<div class="box">
<p><strong>Nom :</strong> {nom}</p>
<p><strong>Email :</strong> {user_email}</p>
<p><strong>Pays :</strong> {pays or 'Non renseigne'}</p>
</div>
<a href="https://boostcentral-eta.vercel.app/admin/users/" class="btn">Voir les utilisateurs</a>
"""
    return _send(ADMIN_EMAIL, f"👤 Nouvelle inscription : {user_email}",
                 _template("Nouvelle inscription !", contenu))

def email_admin_nouvelle_commande(user_email, service, quantite, prix_total, lien):
    """Notifie l admin d une nouvelle commande."""
    contenu = f"""
<p>Un client vient de passer une nouvelle commande !</p>
<div class="box">
<p><strong>Client :</strong> {user_email}</p>
<p><strong>Service :</strong> {service}</p>
<p><strong>Quantite :</strong> {quantite:,}</p>
<p><strong>Prix total :</strong> {prix_total:,.0f} FCFA</p>
<p><strong>Lien :</strong> {lien[:60]}...</p>
</div>
<a href="https://boostcentral-eta.vercel.app/admin/" class="btn">Voir les commandes</a>
"""
    return _send(ADMIN_EMAIL, f"🚀 Nouvelle commande : {service}",
                 _template("Nouvelle commande !", contenu, "#FF6600"))
