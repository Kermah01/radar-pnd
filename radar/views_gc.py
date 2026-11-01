"""Pages du Groupe consultatif pour le financement du PND 2026-2030 : projets et opportunités d'investissement."""
from django.conf import settings
from django.core.paginator import Paginator
from django.db.models import Count, F, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from comptes.decorators import acces_requis
from comptes.models import a_acces

from .models import GCPND_INSCRIPTION, Action, Opportunite, Pilier, ProjetGC
from .services import gcpnd
from .services.alignement import paragraphe_projet
from .services.formatage import normaliser

TRIS_GC = {"cout": "Coût décroissant", "cout_asc": "Coût croissant", "titre": "Intitulé (A à Z)", "code": "Code"}
PAR_PAGE = 50


def _apercu():
    return settings.RADAR.get("APERCU_GC", 20)


def _secteurs_gc(pilier=""):
    """Secteurs (code, nom) qui comptent au moins un projet du Groupe consultatif."""
    qs = ProjetGC.objects.all()
    if pilier:
        qs = qs.filter(pilier__numero=pilier)
    return list(qs.order_by("secteur_code").values_list("secteur_code", "secteur_nom").distinct())


def projets_gc(request):
    acces = a_acces(request.user)
    g = request.GET
    q, typ, pil, sec, tr = (g.get("q", "").strip(), g.get("type", ""), g.get("pilier", ""), g.get("secteur", ""),
                            g.get("cout", ""))
    tri = g.get("tri") if g.get("tri") in TRIS_GC else "cout"
    base = ProjetGC.objects.select_related("secteur", "pilier")
    if q:
        for mot in normaliser(q).split():
            base = base.filter(search_text__contains=mot)
    if pil:
        base = base.filter(pilier__numero=pil)
    if sec:
        base = base.filter(secteur_code=sec)
    if tr in gcpnd.TRANCHES:
        if tr == "nd":
            base = base.filter(cout_millions__isnull=True)
        else:
            _, lo, hi = gcpnd.TRANCHES[tr]
            if lo is not None:
                base = base.filter(cout_millions__gte=lo * 1000)
            if hi is not None:
                base = base.filter(cout_millions__lt=hi * 1000)
    else:
        tr = ""
    kpis = gcpnd.kpis_par_type(base)  # tuiles par type : tous les filtres sauf le type
    if typ not in dict(ProjetGC.TYPES):
        typ = ""
    qs = base.filter(type=typ) if typ else base
    if tri == "cout":
        qs = gcpnd.tri_cout(qs)
    elif tri == "cout_asc":
        qs = qs.order_by(F("cout_millions").asc(nulls_last=True), "ordre")
    else:
        qs = qs.order_by(tri, "ordre")
    agg = qs.aggregate(n=Count("id"), t=Sum("cout_millions"))

    if g.get("format") == "csv":
        if not acces:
            return redirect(f"{reverse('comptes:connexion')}?next={request.get_full_path()}")
        resp = HttpResponse(gcpnd.csv_projets(qs, request.build_absolute_uri("/")[:-1]),
                            content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="radar-pnd-projets-gcpnd-{timezone.localdate():%Y%m%d}.csv"'
        return resp

    if acces:
        page = Paginator(qs, PAR_PAGE).get_page(g.get("page"))
        lignes = page.object_list
    else:
        page = None
        lignes = list(qs[: _apercu()])
    return render(request, "radar/projets_gc.html", {
        "lignes": lignes, "page": page, "nb": agg["n"] or 0, "total": agg["t"] or 0, "kpis": kpis,
        "chiffres_gc": gcpnd.chiffres_gc(), "piliers": Pilier.objects.order_by("numero"),
        "secteurs": _secteurs_gc(pil), "types": ProjetGC.TYPES_COURTS, "tranches": gcpnd.TRANCHES, "tris": TRIS_GC,
        "f": {"q": q, "type": typ, "pilier": pil, "secteur": sec, "cout": tr, "tri": tri},
        "apercu_lignes": _apercu(), "inscription_url": GCPND_INSCRIPTION,
    })


@acces_requis
def projet_gc(request, code):
    p = get_object_or_404(ProjetGC.objects.select_related("secteur__pilier", "pilier"), code=code)
    actions, nb_actions, autres, opps = [], 0, [], []
    if p.secteur_id:
        actions = list(Action.objects.filter(secteur=p.secteur).select_related("secteur").order_by("-total")[:8])
        nb_actions = p.secteur.actions.count()
        autres = list(gcpnd.tri_cout(ProjetGC.objects.filter(secteur=p.secteur).exclude(pk=p.pk))[:8])
        opps = list(Opportunite.objects.filter(secteur=p.secteur))
    nb_meme_secteur = ProjetGC.objects.filter(secteur_code=p.secteur_code).count()
    return render(request, "radar/projet_gc.html", {
        "p": p, "actions": actions, "nb_actions": nb_actions, "autres": autres, "opportunites": opps,
        "nb_meme_secteur": nb_meme_secteur,
        "paragraphe": paragraphe_projet(p, nb_actions, actions[0] if actions else None),
        "part_secteur": (p.cout_millions or 0) / (p.secteur.total or 1) * 100 if p.secteur_id else 0,
        "inscription_url": GCPND_INSCRIPTION,
    })


def _groupes_opportunites():
    """Opportunités regroupées par pilier puis par secteur (fiches détaillées d'abord)."""
    piliers = {p.numero: p for p in Pilier.objects.all()}
    groupes = {}
    for o in Opportunite.objects.select_related("secteur", "pilier").order_by("secteur_code", "ordre"):
        num = o.pilier.numero if o.pilier_id else ""
        pg = groupes.setdefault(num, {"pilier": piliers.get(num), "secteurs": {}})
        sg = pg["secteurs"].setdefault(o.secteur_code, {"code": o.secteur_code, "nom": o.secteur_nom,
                                                        "secteur": o.secteur, "detaillees": [], "simples": []})
        (sg["detaillees"] if o.detaillee else sg["simples"]).append(o)
    out = []
    for num in sorted(groupes):
        pg = groupes[num]
        # « Économie circulaire » (code x.xx, transversal) en fin de pilier
        pg["secteurs"] = sorted(pg["secteurs"].values(), key=lambda s: (s["secteur"] is None, s["code"]))
        pg["nb"] = sum(len(s["detaillees"]) + len(s["simples"]) for s in pg["secteurs"])
        out.append(pg)
    return out


def opportunites(request):
    return render(request, "radar/opportunites.html", {
        "groupes": _groupes_opportunites(), "chiffres_gc": gcpnd.chiffres_gc(), "inscription_url": GCPND_INSCRIPTION,
    })


@acces_requis
def opportunite(request, code):
    o = get_object_or_404(Opportunite.objects.select_related("secteur__pilier", "pilier"), code=code)
    projets, voisines, actions = [], [], []
    if o.secteur_id:
        projets = list(gcpnd.tri_cout(ProjetGC.objects.filter(secteur=o.secteur))[:6])
        actions = list(Action.objects.filter(secteur=o.secteur).order_by("-total")[:5])
    voisines = list(Opportunite.objects.filter(secteur_code=o.secteur_code).exclude(pk=o.pk))
    return render(request, "radar/opportunite.html", {
        "o": o, "projets": projets, "voisines": voisines, "actions": actions, "inscription_url": GCPND_INSCRIPTION,
    })
