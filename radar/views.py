import math

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from comptes.decorators import acces_requis
from comptes.models import a_acces

from .models import ANNEES, COULEURS_PILIERS, Action, Famille, Indicateur, Pilier, Profil, ProjetGC, Secteur, Selection
from .services import catalogue, export, gcpnd
from .services.alignement import paragraphe
from .services.formatage import normaliser
from .services.scoring import PROFILS, PROFILS_PAR_ID, classer, profil_preset

TRIS = {"total": "Coût total", "growth": "Croissance 2026-2030", "code": "Code"}
PAR_PAGE = 50


def _actions_qs():
    return Action.objects.select_related("pilier", "secteur", "effet", "produit").prefetch_related("familles")


def _ids_selection(user):
    if not a_acces(user):
        return set()
    return set(user.selections.values_list("action_id", flat=True))


# ---------------------------------------------------------------- pages publiques


def _radar_svg(piliers, cx=250, cy=250):
    """Secteurs angulaires (un par pilier), rayon proportionnel à la racine du coût programmé."""
    vmax = max([p.total_md for p in piliers] + [1])
    n = len(piliers) or 1
    for i, p in enumerate(piliers):
        a0 = math.radians(-90 + i * 360 / n + 2)
        a1 = math.radians(-90 + (i + 1) * 360 / n - 2)
        r = 70 + 160 * math.sqrt(p.total_md / vmax)
        x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
        x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
        p.wedge = f"M{cx},{cy} L{x0:.1f},{y0:.1f} A{r:.1f},{r:.1f} 0 0 1 {x1:.1f},{y1:.1f} Z"
        am = (a0 + a1) / 2
        p.dehors = r < 120
        rl = r + 18 if p.dehors else r - 28
        p.lx, p.ly = cx + rl * math.cos(am), cy + rl * math.sin(am) + 4
        rn = r * 0.55 if p.dehors else 52
        p.nx, p.ny = cx + rn * math.cos(am), cy + rn * math.sin(am) + 6
    return piliers


def accueil(request):
    chiffres = catalogue.chiffres_cles()
    piliers = _radar_svg(catalogue.piliers_avec_totaux())
    return render(request, "radar/accueil.html", {
        "chiffres": chiffres,
        "piliers": piliers,
        "familles": catalogue.familles_avec_totaux()[:6],
        "profils": PROFILS,
        "chiffres_gc": gcpnd.chiffres_gc(),
    })


def tendances(request):
    chiffres = catalogue.chiffres_cles()
    secteurs = list(Secteur.objects.select_related("pilier").order_by("-total"))
    par_pilier = []
    for p in Pilier.objects.order_by("numero"):
        agg = p.secteurs.aggregate(**{f"y{an}": Sum(f"cost_{an}") for an in ANNEES})
        par_pilier.append({"numero": p.numero, "nom": p.nom, "couleur": p.couleur,
                           "annuel": [round((agg[f"y{an}"] or 0) / 1000, 1) for an in ANNEES]})
    familles = catalogue.familles_avec_totaux()
    tendances_n = dict(Action.objects.values_list("trend").annotate(n=Count("id")).values_list("trend", "n"))
    tendances_m = dict(Action.objects.values_list("trend").annotate(t=Sum("total")).values_list("trend", "t"))
    croissance = sorted([s for s in secteurs if s.total >= 50000 and s.cost_2026], key=lambda s: -s.growth)
    vmax = max([s.total for s in secteurs[:20]] + [1])
    gmax = math.log(max([s.growth for s in croissance[:20]] + [2]))
    graph = {
        "secteurs_total": [{"code": s.code, "nom": s.nom, "v": round(s.total / 1000, 1), "c": COULEURS_PILIERS[s.pilier.numero],
                            "url": s.get_absolute_url(), "w": round(s.total / vmax * 100, 1)} for s in secteurs[:20]],
        # Largeur des barres de montée en charge sur une échelle logarithmique (x 1 = 0 %)
        "secteurs_croissance": [{"code": s.code, "nom": s.nom, "v": round(s.growth, 2), "c": COULEURS_PILIERS[s.pilier.numero],
                                 "url": s.get_absolute_url(), "w": round(max(math.log(max(s.growth, 1)) / gmax * 100, 2), 1)}
                                for s in croissance[:20]],
        "annees": list(ANNEES),
        "piliers": par_pilier,
        "familles": [{"nom": f.nom, "v": round((f.t or 0) / 1000, 1), "slug": f.slug,
                      "w": round((f.t or 0) / (max([x.t or 0 for x in familles] + [1])) * 100, 1)} for f in familles],
        "tendances": [{"nom": t, "n": tendances_n.get(t, 0), "v": round((tendances_m.get(t) or 0) / 1000, 1)}
                      for t in Action.TENDANCES],
    }
    return render(request, "radar/tendances.html", {
        "chiffres": chiffres, "graph": graph, "piliers": catalogue.piliers_avec_totaux(),
        "plus_dynamiques": croissance[:5],
    })


def pilier_detail(request, numero):
    p = get_object_or_404(Pilier, numero=numero)
    chiffres = catalogue.chiffres_cles()
    secteurs = list(p.secteurs.annotate(n=Count("actions")).order_by("-total"))
    total = sum(s.total for s in secteurs)
    annuel = [sum(s.couts[i] for s in secteurs) for i in range(5)]
    top = list(_actions_qs().filter(pilier=p).order_by("-total")[:10])
    nb_actions = p.actions.count()
    autres = Pilier.objects.exclude(pk=p.pk).order_by("numero")
    return render(request, "radar/pilier.html", {
        "pilier": p, "secteurs": secteurs, "total": total, "part": total / (chiffres["total"] or 1) * 100,
        "annuel": annuel, "ratio": annuel[4] / annuel[0] if annuel[0] else 0, "graph": {"annees": list(ANNEES), "valeurs": [round(v / 1000, 1) for v in annuel],
                                    "couleur": p.couleur},
        "max_secteur": max([s.total for s in secteurs] + [1]),
        "top": top, "nb_actions": nb_actions, "autres": autres, "ids_sel": _ids_selection(request.user),
        "nb_indicateurs": Indicateur.objects.filter(parent__startswith=f"{p.numero}.").count(),
        "gc": gcpnd.bloc(pilier=p),
    })


def secteur_detail(request, code):
    s = get_object_or_404(Secteur.objects.select_related("pilier"), code=code)
    acces = a_acces(request.user)
    effets = list(s.effets.prefetch_related("produits").annotate(n=Count("actions"), t=Sum("actions__total")))
    ind_resultat = list(Indicateur.objects.filter(parent=s.code))
    ind_effets = list(Indicateur.objects.filter(parent__in=[e.code for e in effets]))
    limite = 12 if acces else 5
    top = list(_actions_qs().filter(secteur=s).order_by("-total")[:limite])
    nb_actions = s.actions.count()
    familles = list(Famille.objects.filter(actions__secteur=s).annotate(t=Sum("actions__total"), n=Count("actions")).order_by("-t"))
    voisins = s.pilier.secteurs.exclude(pk=s.pk).order_by("code")
    return render(request, "radar/secteur.html", {
        "secteur": s, "effets": effets, "ind_resultat": ind_resultat, "ind_effets": ind_effets, "top": top,
        "nb_actions": nb_actions, "familles": familles, "voisins": voisins, "ids_sel": _ids_selection(request.user),
        "graph": {"annees": list(ANNEES), "valeurs": [round(v / 1000, 1) for v in s.couts], "couleur": s.pilier and COULEURS_PILIERS[s.pilier.numero]},
        "part_pilier": s.total / (s.pilier.secteurs.aggregate(t=Sum("total"))["t"] or 1) * 100,
        "gc": gcpnd.bloc(secteur=s),
    })


def explorer(request):
    acces = a_acces(request.user)
    g = request.GET
    q, pil, sec, fam, tr = g.get("q", "").strip(), g.get("pilier", ""), g.get("secteur", ""), g.get("famille", ""), g.get("tendance", "")
    tri = g.get("tri", "total") if g.get("tri") in TRIS else "total"
    qs = _actions_qs()
    if q:
        for mot in normaliser(q).split():
            qs = qs.filter(search_text__contains=mot)
    if pil:
        qs = qs.filter(pilier__numero=pil)
    if sec:
        qs = qs.filter(secteur__code=sec)
    if fam:
        qs = qs.filter(familles__slug=fam)
    if tr in Action.TENDANCES:
        qs = qs.filter(trend=tr)
    qs = qs.order_by({"total": "-total", "growth": "-growth", "code": "ordre"}[tri], "ordre")
    if tri == "growth":
        qs = qs.order_by("-growth", "-total")
    agg = qs.aggregate(n=Count("id", distinct=True), t=Sum("total"))

    if g.get("format") == "csv":
        if not acces:
            return redirect(f"{reverse('comptes:connexion')}?next={request.get_full_path()}")
        resp = HttpResponse(export.csv_actions(qs.distinct()), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="radar-pnd-explorer-{timezone.localdate():%Y%m%d}.csv"'
        return resp

    if acces:
        page = Paginator(qs.distinct(), PAR_PAGE).get_page(g.get("page"))
        lignes = page.object_list
    else:
        page = None
        lignes = list(qs.distinct()[: settings.RADAR["APERCU_LIGNES"]])
    return render(request, "radar/explorer.html", {
        "lignes": lignes, "page": page, "nb": agg["n"] or 0, "total": agg["t"] or 0,
        "piliers": Pilier.objects.order_by("numero"),
        "secteurs": Secteur.objects.filter(pilier__numero=pil) if pil else Secteur.objects.all(),
        "familles": Famille.objects.all(), "tendances": Action.TENDANCES, "tris": TRIS,
        "f": {"q": q, "pilier": pil, "secteur": sec, "famille": fam, "tendance": tr, "tri": tri},
        "ids_sel": _ids_selection(request.user), "apercu_lignes": settings.RADAR["APERCU_LIGNES"],
        "nb_filtres": sum(1 for v in (pil, sec, fam, tr) if v),
    })


def methode(request):
    return render(request, "radar/methode.html")


def apropos(request):
    return render(request, "radar/apropos.html", {"chiffres": catalogue.chiffres_cles()})


# ---------------------------------------------------------------- espace abonné


def _profil(user):
    prof, cree = Profil.objects.get_or_create(user=user, defaults=profil_preset("etudes"))
    return prof


@acces_requis
def mon_radar(request):
    prof = _profil(request.user)
    if request.method == "POST":
        p = request.POST
        type_ = p.get("type") if p.get("type") in PROFILS_PAR_ID else prof.type
        if p.get("appliquer_preset") == "1" or type_ != prof.type and "familles" not in p:
            data = profil_preset(type_)
        else:
            codes_secteurs = set(Secteur.objects.values_list("code", flat=True))
            noms_familles = set(Famille.objects.values_list("nom", flat=True))
            data = {
                "type": type_,
                "familles": [f for f in p.getlist("familles") if f in noms_familles],
                "secteurs": [s for s in p.getlist("secteurs") if s in codes_secteurs],
                "horizon": p.get("horizon") if p.get("horizon") in dict(Profil.HORIZONS) else "any",
                "taille": p.get("taille") if p.get("taille") in dict(Profil.TAILLES) else "any",
            }
        for k, v in data.items():
            setattr(prof, k, v)
        prof.save()
        return redirect("radar:radar")

    profil = prof.as_dict()
    top, nb, montant_total = classer(catalogue.actions_pour_scoring(), profil)
    objets = _actions_qs().in_bulk([a["id"] for a, _ in top])
    resultats = [(objets[a["id"]], sc) for a, sc in top if a["id"] in objets]
    piliers = list(Pilier.objects.prefetch_related("secteurs").order_by("numero"))
    gc_resultats, gc_nb, gc_total = gcpnd.classer_projets(profil)
    gc_opps, gc_invest = gcpnd.opportunites_profil(profil)
    return render(request, "radar/radar.html", {
        "profil": prof, "profils": PROFILS, "familles": Famille.objects.all(), "piliers": piliers,
        "resultats": resultats, "nb": nb, "montant_total": montant_total,
        "montant_top": sum(a.total for a, _ in resultats), "ids_sel": _ids_selection(request.user),
        "horizons": Profil.HORIZONS, "tailles": Profil.TAILLES,
        "presets": {p["id"]: profil_preset(p["id"]) for p in PROFILS},
        "gc_resultats": gc_resultats, "gc_nb": gc_nb, "gc_total": gc_total, "gc_opps": gc_opps, "gc_invest": gc_invest,
    })


def _get_action(code):
    return get_object_or_404(_actions_qs(), code=code)


@acces_requis
def action_detail(request, code):
    a = _get_action(code)
    inds = a.indicateurs()
    sel = Selection.objects.filter(user=request.user, action=a).first()
    voisines = _actions_qs().filter(produit=a.produit).exclude(pk=a.pk).order_by("-total")[:6]
    return render(request, "radar/action.html", {
        "a": a, "indicateurs": inds, "paragraphe": paragraphe(a, inds), "sel": sel, "voisines": voisines,
        "graph": {"annees": list(ANNEES), "valeurs": [round(v / 1000, 3) for v in a.couts], "couleur": a.couleur,
                  "max_idx": a.couts.index(max(a.couts)) if a.total else -1},
        "part_secteur": a.total / (a.secteur.total or 1) * 100,
        "annees_couts": list(zip(ANNEES, a.couts)),
        "projets_gc": list(gcpnd.tri_cout(ProjetGC.objects.filter(secteur=a.secteur))[:5]),
        "nb_projets_gc": ProjetGC.objects.filter(secteur=a.secteur).count(),
    })


def _retour(request, defaut):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(defaut)


@require_POST
@acces_requis
def selection_toggle(request, code):
    a = get_object_or_404(Action, code=code)
    sel = Selection.objects.filter(user=request.user, action=a).first()
    if sel:
        sel.delete()
        etat = False
    else:
        Selection.objects.create(user=request.user, action=a)
        etat = True
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"selected": etat, "count": request.user.selections.count()})
    messages.success(request, "Action ajoutée à votre sélection." if etat else "Action retirée de votre sélection.")
    return _retour(request, a.get_absolute_url())


@require_POST
@acces_requis
def selection_note(request, code):
    sel = get_object_or_404(Selection, user=request.user, action__code=code)
    sel.note = request.POST.get("note", "")[:5000]
    sel.save(update_fields=["note", "updated_at"])
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True})
    messages.success(request, "Note enregistrée.")
    return _retour(request, reverse("radar:selection"))


@acces_requis
def selection(request):
    sels = list(
        Selection.objects.filter(user=request.user)
        .select_related("action__pilier", "action__secteur", "action__effet", "action__produit")
        .prefetch_related("action__familles")
    )
    for s in sels:
        s.paragraphe = paragraphe(s.action)
    return render(request, "radar/selection.html", {
        "sels": sels, "total": sum(s.action.total for s in sels),
        "tout": "\n\n".join(s.paragraphe for s in sels),
    })


def _nom_fichier(base):
    return f"{base}-{timezone.localdate():%Y%m%d}"


@acces_requis
def export_action_docx(request, code):
    a = _get_action(code)
    sel = Selection.objects.filter(user=request.user, action=a).first()
    resp = HttpResponse(export.docx_action(a, sel.note if sel else ""),
                        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    resp["Content-Disposition"] = f'attachment; filename="fiche-pnd-{a.code}.docx"'
    return resp


@acces_requis
def export_selection(request, fmt):
    sels = list(
        Selection.objects.filter(user=request.user)
        .select_related("action__pilier", "action__secteur", "action__effet", "action__produit")
        .prefetch_related("action__familles")
    )
    if fmt == "docx":
        nom = request.user.get_full_name() or request.user.email
        resp = HttpResponse(export.docx_selection(sels, nom),
                            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        resp["Content-Disposition"] = f'attachment; filename="{_nom_fichier("selection-radar-pnd")}.docx"'
        return resp
    if fmt == "csv":
        notes = {s.action_id: s.note for s in sels}
        resp = HttpResponse(export.csv_actions([s.action for s in sels], avec_paragraphe=True, notes=notes),
                            content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{_nom_fichier("selection-radar-pnd")}.csv"'
        return resp
    raise Http404


def erreur_404(request, exception=None):
    return render(request, "404.html", status=404)
