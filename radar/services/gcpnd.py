"""
Projets et opportunités du Groupe consultatif pour le financement du PND 2026-2030 (gcpnd.gouv.ci) :
chiffres clés, blocs des pages secteur et pilier, classement par profil et export CSV.

Les coûts sont des coûts estimatifs indicatifs, en millions de FCFA (null quand la fiche ne les précise pas).
"""
import csv
import io

from django.core.cache import cache
from django.db.models import Count, F, Sum

from ..models import Opportunite, ProjetGC
from .formatage import nombre

CLE_CHIFFRES = "radar:gcpnd:chiffres:v1"
SOURCE = ("Source : Groupe consultatif pour le financement du PND 2026-2030 (gcpnd.gouv.ci). "
          "Coûts estimatifs indicatifs.")

# Tranches de coût (en Md FCFA) proposées dans les filtres
TRANCHES = {
    "lt10": ("Moins de 10 Md", None, 10),
    "10-50": ("10 à 50 Md", 10, 50),
    "50-250": ("50 à 250 Md", 50, 250),
    "250-1000": ("250 à 1 000 Md", 250, 1000),
    "gt1000": ("Plus de 1 000 Md", 1000, None),
    "nd": ("Coût non défini", None, None),
}

# Secteurs où les projets relèvent surtout de travaux (routes, transport, habitat, eau, énergie, équipements)
SECTEURS_TRAVAUX = ["5.01", "5.02", "5.07", "5.08", "5.09", "3.03", "4.01", "4.03", "4.04", "1.02"]

# Préférences propres au Groupe consultatif, par profil type : ordre des types de projets
# et secteurs clés du métier (en plus des secteurs suivis dans le profil).
PREFS_GC = {
    "etudes": {"types": ["PUB", "PPP"], "secteurs": ["6.08", "6.03", "4.04", "5.02"]},
    "btp": {"types": ["PUB", "PPP"], "secteurs": SECTEURS_TRAVAUX},
    "num": {"types": ["PPP", "PUB", "PRI"], "secteurs": ["5.03", "6.01", "6.05"]},
    "agro": {"types": ["PRI", "PPP", "PUB"], "secteurs": ["2.01", "2.02", "3.04"]},
    "ong": {"types": ["PUB"], "secteurs": ["4.04", "4.05", "4.09", "4.10", "4.11", "5.08", "5.09"]},
    "inv": {"types": ["PPP", "PRI", "PUB"], "secteurs": ["3.01", "3.03", "3.04", "3.08", "5.02", "5.03"]},
    "form": {"types": ["PUB", "PPP"], "secteurs": ["4.02", "4.03", "4.06", "4.07"]},
    "com": {"types": ["PUB", "PPP"], "secteurs": ["3.07", "3.08", "4.12", "6.05"]},
    "four": {"types": ["PUB", "PPP"], "secteurs": ["4.04", "1.02", "1.03", "4.01", "5.08", "4.03"]},
}
# Profils pour qui les opportunités d'investissement privé sont prioritaires
PROFILS_INVESTISSEMENT = {"inv", "agro", "num"}
LIBELLES_TYPES = {"PUB": "projet public", "PPP": "projet en PPP", "PRI": "projet privé"}
TOP_GC = 10


def md_gc(millions):
    """Coût estimatif en millions de FCFA -> '34,4 Md' ; None -> 'Non défini'."""
    if millions is None:
        return "Non défini"
    md = float(millions) / 1000
    dec = 0 if abs(md) >= 100 else (1 if abs(md) >= 1 else 2)
    return f"{nombre(md, dec)} Md"


def invalider_cache_gc():
    cache.delete(CLE_CHIFFRES)


def chiffres_gc():
    data = cache.get(CLE_CHIFFRES)
    if data is not None:
        return data
    par_type = {t: {"n": 0, "t": 0} for t, _ in ProjetGC.TYPES}
    for row in ProjetGC.objects.values("type").annotate(n=Count("id"), t=Sum("cout_millions")):
        par_type[row["type"]] = {"n": row["n"], "t": row["t"] or 0}
    data = {
        "nb_projets": sum(v["n"] for v in par_type.values()),
        "total": sum(v["t"] for v in par_type.values()),
        "par_type": [{"type": t, "nom": nom, "court": ProjetGC.TYPES_COURTS[t], **par_type[t]} for t, nom in ProjetGC.TYPES],
        "nb_opportunites": Opportunite.objects.count(),
        "nb_opportunites_detaillees": Opportunite.objects.exclude(resume="").count(),
    }
    cache.set(CLE_CHIFFRES, data, 3600)
    return data


def kpis_par_type(qs):
    """Nombre et coût total par type, pour un queryset de projets déjà filtré."""
    agg = {r["type"]: r for r in qs.order_by().values("type").annotate(n=Count("id"), t=Sum("cout_millions"))}
    return [{"type": t, "nom": nom, "court": ProjetGC.TYPES_COURTS[t], "n": (agg.get(t) or {}).get("n", 0),
             "t": (agg.get(t) or {}).get("t") or 0} for t, nom in ProjetGC.TYPES]


def tri_cout(qs):
    return qs.order_by(F("cout_millions").desc(nulls_last=True), "ordre")


def bloc(**filtre):
    """Bloc « Projets du Groupe consultatif » d'une page secteur ou pilier."""
    qs = ProjetGC.objects.filter(**filtre).select_related("secteur", "pilier")
    agg = qs.aggregate(n=Count("id"), t=Sum("cout_millions"))
    return {
        "nb": agg["n"] or 0, "total": agg["t"] or 0, "par_type": kpis_par_type(qs),
        "top": list(tri_cout(qs)[:5]),
        "opportunites": list(Opportunite.objects.filter(**filtre).select_related("secteur", "pilier")),
    }


# ---------------------------------------------------------------- classement par profil


def scorer_projet(p, profil):
    """
    Score (0 à 100) d'un projet du Groupe consultatif pour un profil.
      Secteur   45 secteur suivi dans le profil, 25 secteur clé du métier
      Type      30 / 20 / 10 selon l'ordre de préférence du profil
      Taille    15 coût estimatif dans la tranche visée (8 si toutes tailles)
      Coût      10 coût estimatif renseigné
    p : dict avec type, secteur (code), cout (M FCFA ou None)
    """
    from .scoring import taille_ok

    prefs = PREFS_GC.get(profil.get("type"), PREFS_GC["etudes"])
    s, raisons = 0, []
    if p["secteur"] in (profil.get("secteurs") or []):
        s += 45
        raisons.append("secteur suivi")
    elif p["secteur"] in prefs["secteurs"]:
        s += 25
        raisons.append("secteur clé pour votre métier")
    types = prefs["types"]
    if p["type"] in types:
        rang = types.index(p["type"])
        s += (30, 20, 10)[rang]
        if rang == 0:
            raisons.append(f"{LIBELLES_TYPES[p['type']]}, priorité de votre profil")
        elif rang == 1:
            raisons.append(LIBELLES_TYPES[p["type"]])
    taille = profil.get("taille") or "any"
    if p["cout"] is not None:
        s += 10
        if taille == "any":
            s += 8
        elif taille_ok(p["cout"], taille):
            s += 15
            raisons.append("taille visée")
    else:
        raisons.append("coût non défini")
    return min(100, s), raisons


def classer_projets(profil, limite=TOP_GC):
    projets = list(ProjetGC.objects.select_related("secteur", "pilier"))
    prefs = PREFS_GC.get(profil.get("type"), PREFS_GC["etudes"])
    secteurs = set(profil.get("secteurs") or []) | set(prefs["secteurs"])
    res = []
    for p in projets:
        if p.secteur_code not in secteurs:
            continue
        sc, raisons = scorer_projet({"type": p.type, "secteur": p.secteur_code, "cout": p.cout_millions}, profil)
        res.append((p, sc, raisons))
    res.sort(key=lambda x: (-x[1], -(x[0].cout_millions or 0)))
    return res[:limite], len(res), sum(p.cout_millions or 0 for p, _, _ in res)


def opportunites_profil(profil, limite=6):
    """Opportunités des secteurs suivis ou clés du profil ; fiches détaillées en premier."""
    prefs = PREFS_GC.get(profil.get("type"), PREFS_GC["etudes"])
    suivis = set(profil.get("secteurs") or [])
    cles = set(prefs["secteurs"])
    out = []
    for o in Opportunite.objects.select_related("secteur", "pilier"):
        if o.secteur_code in suivis:
            rang, raison = 0, "secteur suivi"
        elif o.secteur_code in cles:
            rang, raison = 1, "secteur clé pour votre métier"
        else:
            continue
        out.append((rang, not o.detaillee, o.ordre, o, raison))
    out.sort(key=lambda x: x[:3])
    return [(o, raison) for *_, o, raison in out[:limite]], profil.get("type") in PROFILS_INVESTISSEMENT


# ---------------------------------------------------------------- export


ENTETES_CSV = ["Type", "Code", "Intitulé", "Pilier", "Code secteur", "Secteur", "Coût estimatif (M FCFA)",
               "Coût estimatif (Md FCFA)", "Fiche officielle (PDF)", "Fiche Radar PND"]


def csv_projets(projets, base_url=""):
    """CSV séparé par des points-virgules, UTF-8 avec BOM (ouverture directe dans Excel)."""
    buf = io.StringIO()
    buf.write("﻿")
    w = csv.writer(buf, delimiter=";")
    w.writerow(ENTETES_CSV)
    for p in projets:
        w.writerow([
            p.get_type_display(), p.code, p.titre, f"{p.pilier.numero}. {p.pilier.nom}" if p.pilier_id else "", p.secteur_code, p.secteur_nom,
            "" if p.cout_millions is None else nombre(p.cout_millions, 0),
            "" if p.cout_millions is None else nombre(p.cout_millions / 1000, 1),
            p.pdf_url, f"{base_url}{p.get_absolute_url()}",
        ])
    w.writerow([])
    w.writerow([SOURCE])
    return buf.getvalue().encode("utf-8")
