"""
Programme VIP par paliers - remise automatique selon le total recharge a vie.
Cout maitrise : la remise vient de ta propre marge, jamais d'argent verse en plus.
"""

TIERS = [
    {"key": "platine", "nom": "Platine", "seuil": 500000, "remise": 0.08, "couleur": "#7C3AED", "icone": "fa-crown"},
    {"key": "or", "nom": "Or", "seuil": 200000, "remise": 0.05, "couleur": "#D97706", "icone": "fa-medal"},
    {"key": "argent", "nom": "Argent", "seuil": 50000, "remise": 0.02, "couleur": "#64748B", "icone": "fa-award"},
    {"key": "bronze", "nom": "Bronze", "seuil": 0, "remise": 0.0, "couleur": "#B45309", "icone": "fa-shield"},
]

ORDRE = ["bronze", "argent", "or", "platine"]


def get_vip_tier(total_recharge_fcfa):
    """Retourne le palier VIP courant + infos de progression vers le suivant."""
    total = total_recharge_fcfa or 0
    for i, t in enumerate(TIERS):
        if total >= t["seuil"]:
            actuel = t
            suivant = TIERS[i - 1] if i > 0 else None
            if suivant:
                restant = max(0, suivant["seuil"] - total)
                progression = min(100, round((total - actuel["seuil"]) / (suivant["seuil"] - actuel["seuil"]) * 100))
            else:
                restant = 0
                progression = 100
            return {
                "key": actuel["key"], "nom": actuel["nom"], "remise": actuel["remise"],
                "couleur": actuel["couleur"], "icone": actuel["icone"],
                "suivant_nom": suivant["nom"] if suivant else None,
                "suivant_remise": suivant["remise"] if suivant else None,
                "restant": restant, "progression": progression
            }
    # Ne devrait jamais arriver (bronze a seuil 0)
    return {"key": "bronze", "nom": "Bronze", "remise": 0.0, "couleur": "#B45309", "icone": "fa-shield",
            "suivant_nom": "Argent", "suivant_remise": 0.02, "restant": 50000, "progression": 0}


def rang(tier_key):
    try:
        return ORDRE.index(tier_key)
    except ValueError:
        return 0
