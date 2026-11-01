"""Accès en lecture au référentiel, avec un petit cache mémoire pour le scoring."""
from django.core.cache import cache
from django.db.models import Sum

from ..models import ANNEES, Action, Famille, Pilier, Secteur

CLE_CACHE = "radar:actions_scoring:v1"


def actions_pour_scoring():
    """Liste de dicts légers (1 480 actions) utilisée par le radar."""
    data = cache.get(CLE_CACHE)
    if data is not None:
        return data
    fams = {}
    for aid, nom in Action.familles.through.objects.values_list("action_id", "famille__nom"):
        fams.setdefault(aid, []).append(nom)
    data = []
    for a in Action.objects.values("id", "code", "secteur__code", "peak", "trend", "total"):
        data.append({"id": a["id"], "code": a["code"], "secteur": a["secteur__code"], "peak": a["peak"],
                     "trend": a["trend"], "total": a["total"], "familles": fams.get(a["id"], [])})
    cache.set(CLE_CACHE, data, 3600)
    return data


def invalider_cache():
    cache.delete(CLE_CACHE)
    cache.delete("radar:chiffres:v1")


def chiffres_cles():
    data = cache.get("radar:chiffres:v1")
    if data is not None:
        return data
    agg = Secteur.objects.aggregate(**{f"y{an}": Sum(f"cost_{an}") for an in ANNEES}, total=Sum("total"))
    annuel = [agg[f"y{an}"] or 0 for an in ANNEES]
    from ..models import Indicateur

    data = {
        "total": agg["total"] or 0,
        "annuel": annuel,
        "nb_actions": Action.objects.count(),
        "nb_secteurs": Secteur.objects.count(),
        "nb_indicateurs": Indicateur.objects.count(),
        "nb_piliers": Pilier.objects.count(),
        "ratio_2030_2026": (annuel[4] / annuel[0]) if annuel[0] else 0,
    }
    cache.set("radar:chiffres:v1", data, 3600)
    return data


def piliers_avec_totaux():
    tot = chiffres_cles()["total"] or 1
    out = []
    for p in Pilier.objects.annotate(t=Sum("secteurs__total")).order_by("numero"):
        p.total_md = p.t or 0
        p.part = (p.t or 0) / tot * 100
        p.nb_secteurs = p.secteurs.count()
        p.nb_actions = p.actions.count()
        out.append(p)
    return out


def familles_avec_totaux():
    return list(Famille.objects.annotate(t=Sum("actions__total")).order_by("-t"))
