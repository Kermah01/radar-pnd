"""
Charge (ou recharge) les projets et opportunités du Groupe consultatif pour le financement
du PND 2026-2030 depuis data/gcpnd.json (source : gcpnd.gouv.ci).

Commande idempotente : relancée, elle met à jour les enregistrements existants sans doublon.
Les secteurs sont rattachés au référentiel PND par leur code (à charger avant avec load_pnd).

    python manage.py load_gcpnd
    python manage.py load_gcpnd --fichier autre.json --supprimer-absents
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from radar.models import Opportunite, Pilier, ProjetGC, Secteur
from radar.services.formatage import normaliser
from radar.services.gcpnd import invalider_cache_gc

TYPES = {t for t, _ in ProjetGC.TYPES}


def _liste(v):
    if not v:
        return []
    if isinstance(v, str):
        return [v]
    return [str(x).strip() for x in v if str(x).strip()]


class Command(BaseCommand):
    help = "Charge les projets et opportunités du Groupe consultatif pour le financement du PND (gcpnd.gouv.ci)."

    def add_arguments(self, parser):
        parser.add_argument("--fichier", default=str(Path(settings.BASE_DIR) / "data" / "gcpnd.json"))
        parser.add_argument("--supprimer-absents", action="store_true",
                            help="Supprime les projets et opportunités absents du fichier.")

    @transaction.atomic
    def handle(self, *args, **opts):
        chemin = Path(opts["fichier"])
        if not chemin.exists():
            raise CommandError(f"Fichier introuvable : {chemin}")
        d = json.loads(chemin.read_text(encoding="utf-8"))
        secteurs = {s.code: s for s in Secteur.objects.select_related("pilier")}
        piliers = {p.numero: p for p in Pilier.objects.all()}

        # Projets
        existants = {p.code: p for p in ProjetGC.objects.all()}
        vus, creer, maj, non_rattaches = set(), [], [], 0
        for i, it in enumerate(d.get("projets", [])):
            code = it["code"].strip()
            if code in vus:
                continue
            vus.add(code)
            typ = (it.get("type") or "").upper()
            if typ not in TYPES:
                raise CommandError(f"Type de projet inconnu pour {code} : {typ}")
            obj = existants.get(code) or ProjetGC(code=code)
            sec = secteurs.get(it.get("secteur") or "")
            non_rattaches += sec is None
            obj.type = typ
            obj.secteur = sec
            obj.secteur_code = (it.get("secteur") or "")[:10]
            obj.secteur_nom = (it.get("secteur_nom") or (sec.nom if sec else ""))[:255]
            obj.pilier = sec.pilier if sec else piliers.get(str(it.get("pilier") or ""))
            cout = it.get("cout")
            obj.cout_millions = float(cout) if cout not in (None, "") else None
            obj.titre = (it.get("titre") or "").strip()
            obj.pdf_url = (it.get("pdf") or "")[:400]
            obj.ordre = i
            obj.search_text = normaliser(" ".join([code, obj.titre, obj.secteur_nom, obj.get_type_display()]))
            (maj if obj.pk else creer).append(obj)
        ProjetGC.objects.bulk_create(creer, batch_size=500)
        if maj:
            ProjetGC.objects.bulk_update(maj, ["type", "secteur", "secteur_code", "secteur_nom", "pilier",
                                               "cout_millions", "titre", "pdf_url", "ordre", "search_text"],
                                         batch_size=500)

        # Opportunités
        o_exist = {o.code: o for o in Opportunite.objects.all()}
        o_vus, o_creer, o_maj = set(), [], []
        for i, it in enumerate(d.get("opportunites", [])):
            code = it["code"].strip()
            if code in o_vus:
                continue
            o_vus.add(code)
            obj = o_exist.get(code) or Opportunite(code=code)
            sec = secteurs.get(it.get("secteur") or "")
            obj.secteur = sec
            obj.secteur_code = (it.get("secteur") or "")[:10]
            obj.secteur_nom = (it.get("secteur_nom") or (sec.nom if sec else ""))[:255]
            obj.pilier = sec.pilier if sec else piliers.get(str(it.get("pilier") or ""))
            obj.titre = (it.get("titre") or "").strip()
            obj.pdf_url = (it.get("pdf") or "")[:400]
            obj.localisation = it.get("localisation") or ""
            obj.resume = it.get("resume") or ""
            obj.chiffres = _liste(it.get("chiffres"))
            obj.segments = _liste(it.get("segments"))
            obj.incitations = _liste(it.get("incitations"))
            obj.emplois = it.get("emplois") or ""
            obj.montant = it.get("montant") or ""
            obj.ordre = i
            (o_maj if obj.pk else o_creer).append(obj)
        Opportunite.objects.bulk_create(o_creer, batch_size=500)
        if o_maj:
            Opportunite.objects.bulk_update(o_maj, ["secteur", "secteur_code", "secteur_nom", "pilier", "titre", "pdf_url",
                                                    "localisation", "resume", "chiffres", "segments", "incitations",
                                                    "emplois", "montant", "ordre"], batch_size=500)

        if opts["supprimer_absents"]:
            n_p, _ = ProjetGC.objects.exclude(code__in=vus).delete()
            n_o, _ = Opportunite.objects.exclude(code__in=o_vus).delete()
            self.stdout.write(f"Supprimés : {n_p} projets, {n_o} opportunités absents du fichier.")

        invalider_cache_gc()
        if non_rattaches:
            self.stdout.write(self.style.WARNING(
                f"{non_rattaches} projet(s) sans secteur correspondant dans le référentiel PND (lancer load_pnd avant)."))
        self.stdout.write(self.style.SUCCESS(
            f"Groupe consultatif chargé : {ProjetGC.objects.count()} projets ({len(creer)} créés, {len(maj)} mis à jour), "
            f"{Opportunite.objects.count()} opportunités ({len(o_creer)} créées, {len(o_maj)} mises à jour)."
        ))
