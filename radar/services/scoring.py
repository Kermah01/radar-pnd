"""
Score de pertinence (0 à 100) d'une action du PND pour un profil utilisateur.

Grille (note de conception AIC) :
  Famille de prestations  40  l'action relève d'au moins une famille proposée
  Secteur                 25  l'action appartient à un secteur suivi
  Calendrier              15  l'année de pic correspond à l'horizon visé
  Dynamique               10  Nouvelle / Hausse forte 10, Hausse 7, Stable 4, Baisse 1
  Taille                  10  le coût total entre dans la tranche visée

Le score est une aide à la priorisation, jamais une probabilité d'obtenir un marché.
"""
from dataclasses import dataclass, field

NUMERIQUE = "Numérique & systèmes d’information"

PROFILS = [
    {"id": "etudes", "nom": "Bureau d'études ou consultant",
     "familles": ["Études, conseil & statistiques", "Formation & renforcement de capacités", "Réformes & cadre juridique"],
     "secteurs": ["6.08", "4.06", "2.01", "5.08", "4.04"], "horizon": "early", "taille": "any"},
    {"id": "btp", "nom": "Entreprise du BTP",
     "familles": ["Travaux & infrastructures", "Équipements & fournitures"],
     "secteurs": ["5.01", "5.07", "4.02", "3.05", "5.08"], "horizon": "late", "taille": "any"},
    {"id": "num", "nom": "Entreprise du numérique",
     "familles": [NUMERIQUE, "Études, conseil & statistiques"],
     "secteurs": ["5.03", "6.01", "4.04", "2.01", "6.03"], "horizon": "any", "taille": "any"},
    {"id": "agro", "nom": "Coopérative ou entreprise agroalimentaire",
     "familles": ["Investissement productif & PPP", "Appui aux entreprises & financement", "Équipements & fournitures"],
     "secteurs": ["2.01", "2.02", "3.04"], "horizon": "any", "taille": "any"},
    {"id": "ong", "nom": "ONG ou association",
     "familles": ["Communication & sensibilisation", "Formation & renforcement de capacités", "Services & autres"],
     "secteurs": ["4.05", "4.10", "4.11", "4.04", "4.09"], "horizon": "early", "taille": "s"},
    {"id": "inv", "nom": "Investisseur ou membre de la diaspora",
     "familles": ["Investissement productif & PPP", "Appui aux entreprises & financement"],
     "secteurs": ["3.03", "3.04", "3.08", "3.05", "5.03"], "horizon": "late", "taille": "l"},
    {"id": "form", "nom": "Organisme de formation",
     "familles": ["Formation & renforcement de capacités"],
     "secteurs": ["4.02", "4.06", "4.07", "3.02"], "horizon": "any", "taille": "any"},
    {"id": "com", "nom": "Agence de communication ou événementiel",
     "familles": ["Communication & sensibilisation"],
     "secteurs": ["3.08", "3.07", "4.12", "6.05"], "horizon": "any", "taille": "any"},
    {"id": "four", "nom": "Fournisseur d'équipements",
     "familles": ["Équipements & fournitures", "Travaux & infrastructures"],
     "secteurs": ["4.04", "1.03", "4.01", "5.08"], "horizon": "any", "taille": "any"},
]
PROFILS_PAR_ID = {p["id"]: p for p in PROFILS}
PROFIL_DEFAUT = "etudes"

POINTS_DYNAMIQUE = {"Nouvelle": 10, "Hausse forte": 10, "Hausse": 7, "Stable": 4, "Baisse": 1}
TENDANCES_HAUSSE = ("Nouvelle", "Hausse forte", "Hausse")
TOP_N = 40


def profil_preset(pid):
    p = PROFILS_PAR_ID.get(pid) or PROFILS_PAR_ID[PROFIL_DEFAUT]
    return {"type": p["id"], "familles": list(p["familles"]), "secteurs": list(p["secteurs"]),
            "horizon": p["horizon"], "taille": p["taille"]}


@dataclass
class Score:
    score: int
    raisons: list = field(default_factory=list)
    famille_ok: bool = False


def taille_ok(total_millions, taille):
    md = (total_millions or 0) / 1000
    return (taille == "any" or (taille == "s" and md < 10) or (taille == "m" and 10 <= md <= 200)
            or (taille == "l" and md > 200))


def scorer(action, profil):
    """
    action : dict avec familles (liste de noms), secteur (code), peak, trend, total (M FCFA)
    profil : dict avec familles, secteurs, horizon, taille
    """
    s = 0
    raisons = []
    fams = profil.get("familles") or []
    secs = profil.get("secteurs") or []
    horizon = profil.get("horizon") or "any"

    fm = any(f in fams for f in action.get("familles") or [])
    if fams:
        if fm:
            s += 40
            raisons.append("correspond à votre offre")
    else:
        s += 20

    if secs:
        if action.get("secteur") in secs:
            s += 25
            raisons.append("secteur suivi")
    else:
        s += 12

    peak = action.get("peak")
    if peak:
        if horizon == "any":
            s += 8
        elif (horizon == "early" and peak <= 2027) or (horizon == "late" and peak >= 2028):
            s += 15
            raisons.append(f"pic en {peak}")

    trend = action.get("trend")
    s += POINTS_DYNAMIQUE.get(trend, 0)
    if trend in TENDANCES_HAUSSE:
        raisons.append("démarre après 2026" if trend == "Nouvelle" else "budget en hausse")

    if taille_ok(action.get("total"), profil.get("taille") or "any"):
        s += 10

    if not action.get("total"):
        s = min(s, 20)
    return Score(score=min(100, s), raisons=raisons, famille_ok=fm)


def classer(actions, profil, limite=TOP_N):
    """
    Classe les actions chiffrées pour le profil.
    Renvoie (liste [(action, Score)] limitée, nombre total de correspondances, montant total des correspondances).
    """
    fams = profil.get("familles") or []
    res = []
    for a in actions:
        if not a.get("total"):
            continue
        sc = scorer(a, profil)
        if sc.famille_ok or not fams:
            res.append((a, sc))
    res.sort(key=lambda x: (-x[1].score, -(x[0].get("total") or 0)))
    return res[:limite], len(res), sum(a.get("total") or 0 for a, _ in res)
