"""
Charge (ou recharge) le référentiel PND 2026-2030 depuis data/pnd.json.

Commande idempotente : relancée, elle met à jour les enregistrements existants
sans créer de doublons et sans toucher aux sélections des utilisateurs.

    python manage.py load_pnd
    python manage.py load_pnd --fichier autre.json --supprimer-absents
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from radar.models import ANNEES, Action, Effet, Famille, Indicateur, Pilier, Produit, Secteur
from radar.services.catalogue import invalider_cache
from radar.services.formatage import normaliser

ORDRE_FAMILLES = [
    "Travaux & infrastructures",
    "Investissement productif & PPP",
    "Études, conseil & statistiques",
    "Numérique & systèmes d’information",
    "Formation & renforcement de capacités",
    "Équipements & fournitures",
    "Appui aux entreprises & financement",
    "Communication & sensibilisation",
    "Réformes & cadre juridique",
    "Services & autres",
]


def multiplicateur(c):
    if c[0]:
        return c[4] / c[0]
    return 99.0 if c[4] else 0.0


def appliquer_couts(obj, couts, total):
    obj.set_couts(couts)
    obj.total = float(total or 0)


class Command(BaseCommand):
    help = "Charge le référentiel PND 2026-2030 (piliers, secteurs, effets, produits, actions, indicateurs)."

    def add_arguments(self, parser):
        parser.add_argument("--fichier", default=str(Path(settings.BASE_DIR) / "data" / "pnd.json"))
        parser.add_argument("--supprimer-absents", action="store_true",
                            help="Supprime les actions et indicateurs absents du fichier (et les sélections associées).")

    @transaction.atomic
    def handle(self, *args, **opts):
        chemin = Path(opts["fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")
        d = json.loads(chemin.read_text(encoding="utf-8"))

        # Piliers
        piliers = {}
        for num, nom in d["piliers"].items():
            p, _ = Pilier.objects.update_or_create(numero=num, defaults={"nom": nom})
            piliers[num] = p

        # Familles
        noms_familles = list(ORDRE_FAMILLES)
        for a in d["actions"]:
            for t in a.get("types", []):
                if t not in noms_familles:
                    noms_familles.append(t)
        familles = {}
        for i, nom in enumerate(noms_familles):
            f, _ = Famille.objects.update_or_create(nom=nom, defaults={"slug": slugify(nom)[:60] or f"famille-{i}", "ordre": i})
            familles[nom] = f

        # Secteurs
        secteurs = {s.code: s for s in Secteur.objects.all()}
        for s in d["secteurs"]:
            obj = secteurs.get(s["code"]) or Secteur(code=s["code"])
            obj.nom = s["nom"]
            obj.pilier = piliers[s["pilier"]]
            obj.resultat = s.get("resultat") or ""
            appliquer_couts(obj, s["cost"], s["total"])
            obj.growth = multiplicateur(obj.couts)
            obj.save()
            secteurs[obj.code] = obj

        # Effets et produits (complétés par les libellés portés par les actions)
        lib_effets = dict(d.get("effets", {}))
        lib_produits = dict(d.get("produits", {}))
        for a in d["actions"]:
            lib_effets.setdefault(a["effet"], a.get("effet_label") or "")
            if not lib_produits.get(a["produit"]):
                lib_produits[a["produit"]] = a.get("produit_label") or ""

        effets = {e.code: e for e in Effet.objects.all()}
        for code, label in sorted(lib_effets.items()):
            sec = secteurs.get(".".join(code.split(".")[:2]))
            if not sec:
                continue
            obj = effets.get(code) or Effet(code=code)
            obj.label = label or "Effet non libellé dans la source"
            obj.secteur = sec
            obj.save()
            effets[code] = obj

        produits = {p.code: p for p in Produit.objects.all()}
        for code, label in sorted(lib_produits.items()):
            eff = effets.get(".".join(code.split(".")[:3]))
            if not eff:
                continue
            obj = produits.get(code) or Produit(code=code)
            obj.label = label or "Produit non libellé dans la source"
            obj.effet = eff
            obj.save()
            produits[code] = obj

        # Actions
        existantes = {a.code: a for a in Action.objects.all()}
        vus, a_creer, a_maj, liens = set(), [], [], {}
        for i, a in enumerate(d["actions"]):
            code = a["code"]
            if code in vus:  # doublon dans la source : conservé sous un code distinct
                code = f"{code}-bis"
            vus.add(code)
            obj = existantes.get(code) or Action(code=code)
            obj.label = a["label"]
            obj.pilier = piliers[a["pilier"]]
            obj.secteur = secteurs[a["secteur"]]
            obj.effet = effets[a["effet"]]
            obj.produit = produits[a["produit"]]
            obj.structure = (a.get("structure") or "")[:255]
            appliquer_couts(obj, a["cost"], a["total"])
            obj.peak = a.get("peak") or None
            obj.trend = a.get("trend") or "Stable"
            obj.growth = multiplicateur(obj.couts)
            obj.page = a.get("page") or None
            obj.ordre = i
            obj.search_text = normaliser(" ".join([
                code, a["label"], obj.structure, a.get("secteur_nom", ""), lib_produits.get(a["produit"], ""),
            ]))
            (a_maj if obj.pk else a_creer).append(obj)
            liens[code] = [familles[t] for t in a.get("types", [])]

        champs = ["label", "pilier", "secteur", "effet", "produit", "structure", "total", "peak", "trend", "growth",
                  "page", "ordre", "search_text"] + [f"cost_{an}" for an in ANNEES]
        Action.objects.bulk_create(a_creer, batch_size=500)
        if a_maj:
            Action.objects.bulk_update(a_maj, champs, batch_size=500)
        ids = dict(Action.objects.values_list("code", "id"))
        Through = Action.familles.through
        Through.objects.filter(action_id__in=[ids[c] for c in liens]).delete()
        Through.objects.bulk_create(
            [Through(action_id=ids[c], famille_id=f.id) for c, fs in liens.items() for f in fs], batch_size=1000
        )

        # Indicateurs
        ind_exist = {x.ident: x for x in Indicateur.objects.all()}
        i_creer, i_maj, i_vus = [], [], set()
        for i, it in enumerate(d.get("indicateurs", [])):
            ident = it["id"]
            if ident in i_vus:
                ident = f"{ident}-bis"
            i_vus.add(ident)
            obj = ind_exist.get(ident) or Indicateur(ident=ident)
            obj.parent = it.get("parent") or ident.split("-")[0]
            obj.label = it.get("label") or ""
            obj.annee = (it.get("annee") or "")[:255]
            obj.base = (it.get("base") or "")[:255]
            obj.source = (it.get("source") or "")[:255]
            cibles = list(it.get("cibles") or []) + [""] * 5
            for an, c in zip(ANNEES, cibles[:5]):
                setattr(obj, f"cible_{an}", (c or "")[:255])
            obj.odd = (it.get("odd") or "")[:255]
            obj.ordre = i
            (i_maj if obj.pk else i_creer).append(obj)
        Indicateur.objects.bulk_create(i_creer, batch_size=500)
        if i_maj:
            Indicateur.objects.bulk_update(
                i_maj, ["parent", "label", "annee", "base", "source", "odd", "ordre"] + [f"cible_{an}" for an in ANNEES],
                batch_size=500,
            )

        if opts["supprimer_absents"]:
            n_a, _ = Action.objects.exclude(code__in=vus).delete()
            n_i, _ = Indicateur.objects.exclude(ident__in=i_vus).delete()
            self.stdout.write(f"Supprimés : {n_a} actions, {n_i} indicateurs absents du fichier.")

        invalider_cache()
        self.stdout.write(self.style.SUCCESS(
            f"Référentiel PND chargé : {Pilier.objects.count()} piliers, {Secteur.objects.count()} secteurs, "
            f"{Effet.objects.count()} effets, {Produit.objects.count()} produits, {Action.objects.count()} actions "
            f"({len(a_creer)} créées, {len(a_maj)} mises à jour), {Indicateur.objects.count()} indicateurs."
        ))
