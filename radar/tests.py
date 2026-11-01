import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from comptes.models import CodeAcces
from radar.models import Action, Indicateur, Secteur, Selection
from radar.services.formatage import montant
from radar.services.scoring import classer, profil_preset, scorer

MINI = {
    "piliers": {"5": "Infrastructures stratégiques"},
    "secteurs": [{"code": "5.01", "nom": "Infrastructures routières", "pilier": "5",
                  "cost": [100, 200, 300, 400, 500], "total": 1500, "resultat": "Routes praticables"}],
    "effets": {"5.01.2": "Le maillage est amélioré"},
    "produits": {"5.01.2.1": "Réseau interurbain modernisé"},
    "actions": [
        {"code": "5.01.2.1.1", "label": "Construire la route A", "pilier": "5", "secteur": "5.01",
         "secteur_nom": "Infrastructures routières", "effet": "5.01.2", "effet_label": "", "produit": "5.01.2.1",
         "produit_label": "", "resultat_label": "", "structure": "AGEROUTE", "cost": [0, 0, 100, 200, 300],
         "total": 600, "peak": 2030, "trend": "Nouvelle", "types": ["Travaux & infrastructures"], "page": 68},
        {"code": "5.01.2.1.2", "label": "Former les agents", "pilier": "5", "secteur": "5.01",
         "secteur_nom": "Infrastructures routières", "effet": "5.01.2", "effet_label": "", "produit": "5.01.2.1",
         "produit_label": "", "resultat_label": "", "structure": "", "cost": [50, 10, 10, 10, 10],
         "total": 90, "peak": 2026, "trend": "Baisse", "types": ["Formation & renforcement de capacités"], "page": 68},
    ],
    "indicateurs": [{"id": "5.01.2.1-1", "parent": "5.01.2.1", "label": "Linéaire bitumé", "annee": "2024",
                     "base": "100 km", "source": "MEER", "cibles": ["", "", "", "", "400 km"], "odd": "9.1"}],
}


def charger_mini(test):
    tmp = Path(tempfile.mkdtemp()) / "mini.json"
    tmp.write_text(json.dumps(MINI), encoding="utf-8")
    call_command("load_pnd", fichier=str(tmp), verbosity=0, stdout=open("/dev/null", "w"))
    return tmp


class ScoringTests(TestCase):
    def test_score_maximal(self):
        a = {"familles": ["Travaux & infrastructures"], "secteur": "5.01", "peak": 2030, "trend": "Nouvelle", "total": 600}
        p = {"familles": ["Travaux & infrastructures"], "secteurs": ["5.01"], "horizon": "late", "taille": "s"}
        sc = scorer(a, p)
        self.assertEqual(sc.score, 100)  # 40 + 25 + 15 + 10 + 10
        self.assertIn("correspond à votre offre", sc.raisons)
        self.assertIn("pic en 2030", sc.raisons)
        self.assertIn("démarre après 2026", sc.raisons)

    def test_regles_partielles(self):
        a = {"familles": ["Services & autres"], "secteur": "1.01", "peak": 2026, "trend": "Baisse", "total": 500000}
        p = {"familles": ["Travaux & infrastructures"], "secteurs": ["5.01"], "horizon": "late", "taille": "s"}
        sc = scorer(a, p)
        self.assertEqual(sc.score, 1)  # seule la dynamique (baisse) rapporte
        self.assertFalse(sc.famille_ok)
        sans_profil = scorer(a, {"familles": [], "secteurs": [], "horizon": "any", "taille": "any"})
        self.assertEqual(sans_profil.score, 20 + 12 + 8 + 1 + 10)

    def test_action_non_chiffree_plafonnee(self):
        a = {"familles": ["Travaux & infrastructures"], "secteur": "5.01", "peak": None, "trend": "Stable", "total": 0}
        self.assertLessEqual(scorer(a, profil_preset("btp")).score, 20)

    def test_classement_filtre_et_trie(self):
        acts = [
            {"id": 1, "familles": ["Travaux & infrastructures"], "secteur": "5.01", "peak": 2029, "trend": "Hausse", "total": 900},
            {"id": 2, "familles": ["Communication & sensibilisation"], "secteur": "5.01", "peak": 2029, "trend": "Hausse", "total": 900},
            {"id": 3, "familles": ["Travaux & infrastructures"], "secteur": "9.99", "peak": 2026, "trend": "Baisse", "total": 50},
            {"id": 4, "familles": ["Travaux & infrastructures"], "secteur": "5.01", "peak": 2029, "trend": "Hausse", "total": 0},
        ]
        top, n, tot = classer(acts, profil_preset("btp"))
        self.assertEqual([a["id"] for a, _ in top], [1, 3])
        self.assertEqual(n, 2)
        self.assertEqual(tot, 950)

    def test_presets(self):
        p = profil_preset("inconnu")
        self.assertEqual(p["type"], "etudes")
        self.assertEqual(profil_preset("inv")["taille"], "l")

    def test_format_montant(self):
        self.assertEqual(montant(26115), "26,1 Md FCFA")
        self.assertEqual(montant(114839520), "114 840 Md FCFA")
        self.assertEqual(montant(450), "450 M FCFA")


class LoadPndTests(TestCase):
    def test_chargement_idempotent(self):
        f = charger_mini(self)
        self.assertEqual(Action.objects.count(), 2)
        a = Action.objects.get(code="5.01.2.1.1")
        self.assertEqual(a.couts, [0, 0, 100, 200, 300])
        self.assertEqual(a.growth, 99.0)
        self.assertEqual(list(a.familles.values_list("nom", flat=True)), ["Travaux & infrastructures"])
        self.assertIn("ageroute", a.search_text)
        self.assertEqual(len(a.indicateurs()), 1)
        u = get_user_model().objects.create_user("x@y.ci", "x@y.ci", "motdepasse-123")
        Selection.objects.create(user=u, action=a, note="garder")
        call_command("load_pnd", fichier=str(f), verbosity=0, stdout=open("/dev/null", "w"))
        self.assertEqual(Action.objects.count(), 2)
        self.assertEqual(Indicateur.objects.count(), 1)
        self.assertEqual(Secteur.objects.get(code="5.01").growth, 5.0)
        self.assertEqual(Selection.objects.get().note, "garder")

    def test_donnees_reelles(self):
        call_command("load_pnd", verbosity=0, stdout=open("/dev/null", "w"))
        self.assertEqual(Action.objects.count(), 1480)
        self.assertEqual(Secteur.objects.count(), 43)
        self.assertEqual(Indicateur.objects.count(), 1219)


class AccesTests(TestCase):
    def setUp(self):
        charger_mini(self)
        self.code = CodeAcces.generer(1, CodeAcces.DECOUVERTE, "test")[0]

    def _inscrire(self, code, email="lecteur@exemple.ci"):
        return self.client.post("/compte/inscription/", {
            "code": code, "prenom": "Awa", "nom": "Koné", "email": email, "organisation": "Bureau K",
            "password1": "Plan-2026-solide", "password2": "Plan-2026-solide",
        })

    def test_pages_publiques_et_reservees(self):
        for url in ("/", "/tendances/", "/explorer/", "/pilier/5/", "/secteur/5.01/", "/methode-radar/", "/a-propos/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in ("/radar/", "/action/5.01.2.1.1/", "/ma-selection/", "/ma-selection/export.docx"):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    def test_inscription_avec_code(self):
        r = self._inscrire(self.code.code.lower())
        self.assertRedirects(r, "/radar/")
        self.code.refresh_from_db()
        self.assertEqual(self.code.used_by.email, "lecteur@exemple.ci")
        self.assertIsNotNone(self.code.expires)
        self.assertEqual(self.client.get("/action/5.01.2.1.1/").status_code, 200)
        self.assertEqual(self.client.get("/radar/").status_code, 200)
        r = self.client.post("/action/5.01.2.1.1/selection/", HTTP_X_REQUESTED_WITH="fetch")
        self.assertEqual(r.json(), {"selected": True, "count": 1})
        r = self.client.get("/ma-selection/export.docx")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b"PK"))
        r = self.client.get("/ma-selection/export.csv")
        self.assertIn("Construire la route A", r.content.decode("utf-8-sig"))

    def test_code_invalide_ou_deja_utilise(self):
        r = self._inscrire("RPND-FAUX-CODE")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(get_user_model().objects.exists())
        self._inscrire(self.code.code)
        self.client.logout()
        r = self._inscrire(self.code.code, email="autre@exemple.ci")
        self.assertContains(r, "déjà été utilisé")
        self.assertEqual(get_user_model().objects.count(), 1)

    def test_prolongation(self):
        self._inscrire(self.code.code)
        self.code.refresh_from_db()
        fin1 = self.code.expires
        pro = CodeAcces.generer(1, CodeAcces.PRO)[0]
        self.client.post("/compte/activer/", {"code": pro.code})
        pro.refresh_from_db()
        self.assertGreater(pro.expires, fin1)
        self.assertEqual((pro.expires - fin1).days, 366)


MINI_GC = {
    "source": "test",
    "projets": [
        {"type": "PUB", "code": "5.01-001", "secteur": "5.01", "secteur_nom": "Infrastructures routières", "pilier": "5",
         "cout": 250000.0, "titre": "Autoroute de test", "pdf": "https://www.gcpnd.gouv.ci/uploads/fiches/projets/fr/5.01-001_FR.pdf"},
        {"type": "PPP", "code": "5.01-002", "secteur": "5.01", "secteur_nom": "Infrastructures routières", "pilier": "5",
         "cout": None, "titre": "Pont à péage de Bouaké", "pdf": "https://www.gcpnd.gouv.ci/uploads/fiches/projets/fr/5.01-002_FR.pdf"},
        {"type": "PRI", "code": "9.99-001", "secteur": "9.99", "secteur_nom": "Secteur inconnu", "pilier": "5",
         "cout": 1500.0, "titre": "Projet hors matrice", "pdf": ""},
    ],
    "opportunites": [
        {"code": "OP_5.01-001", "secteur": "5.01", "secteur_nom": "Infrastructures routières", "pilier": "5",
         "titre": "Entretien routier", "pdf": "https://www.gcpnd.gouv.ci/x.pdf", "resume": "Marché en croissance.",
         "chiffres": ["10 000 km"], "segments": ["Entretien"], "incitations": ["Exonérations"], "emplois": "5 000", "montant": ""},
        {"code": "OP_x.xx-070", "secteur": "x.xx", "secteur_nom": "Économie circulaire", "pilier": "5",
         "titre": "Écoconception", "pdf": "https://www.gcpnd.gouv.ci/y.pdf"},
    ],
}


def charger_mini_gc():
    charger_mini(None)
    tmp = Path(tempfile.mkdtemp()) / "gc.json"
    tmp.write_text(json.dumps(MINI_GC), encoding="utf-8")
    call_command("load_gcpnd", fichier=str(tmp), verbosity=0, stdout=open("/dev/null", "w"))
    return tmp


class LoadGcpndTests(TestCase):
    def test_chargement_idempotent_et_rattachement(self):
        from radar.models import Opportunite, ProjetGC

        f = charger_mini_gc()
        self.assertEqual(ProjetGC.objects.count(), 3)
        p = ProjetGC.objects.get(code="5.01-001")
        self.assertEqual(p.secteur.code, "5.01")
        self.assertEqual(p.pilier.numero, "5")
        self.assertEqual(p.cout_millions, 250000.0)
        self.assertIn("autoroute", p.search_text)
        self.assertIsNone(ProjetGC.objects.get(code="5.01-002").cout_millions)
        hors = ProjetGC.objects.get(code="9.99-001")
        self.assertIsNone(hors.secteur)
        self.assertEqual(hors.pilier.numero, "5")
        o = Opportunite.objects.get(code="OP_5.01-001")
        self.assertTrue(o.detaillee)
        self.assertEqual(o.chiffres, ["10 000 km"])
        circ = Opportunite.objects.get(code="OP_x.xx-070")
        self.assertIsNone(circ.secteur)
        self.assertFalse(circ.detaillee)
        call_command("load_gcpnd", fichier=str(f), verbosity=0, stdout=open("/dev/null", "w"))
        self.assertEqual(ProjetGC.objects.count(), 3)
        self.assertEqual(Opportunite.objects.count(), 2)

    def test_donnees_reelles(self):
        from radar.models import Opportunite, ProjetGC
        from radar.services.gcpnd import chiffres_gc, invalider_cache_gc

        call_command("load_pnd", verbosity=0, stdout=open("/dev/null", "w"))
        call_command("load_gcpnd", verbosity=0, stdout=open("/dev/null", "w"))
        self.assertEqual(ProjetGC.objects.count(), 337)
        self.assertEqual(Opportunite.objects.count(), 66)
        self.assertFalse(ProjetGC.objects.filter(secteur__isnull=True).exists())
        self.assertEqual(Opportunite.objects.filter(secteur__isnull=True).count(), 6)  # Économie circulaire
        invalider_cache_gc()
        c = {k["type"]: k for k in chiffres_gc()["par_type"]}
        self.assertEqual((c["PUB"]["n"], c["PPP"]["n"], c["PRI"]["n"]), (207, 98, 32))
        self.assertEqual(round(c["PUB"]["t"] / 1000), 24125)
        self.assertEqual(round(c["PPP"]["t"] / 1000), 42576)
        self.assertEqual(round(c["PRI"]["t"] / 1000), 14808)


class ProjetsGcVueTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        charger_mini_gc()

    def _connecter(self):
        code = CodeAcces.generer(1, CodeAcces.DECOUVERTE, "test")[0]
        self.client.post("/compte/inscription/", {
            "code": code.code, "prenom": "Awa", "nom": "Koné", "email": "gc@exemple.ci", "organisation": "",
            "password1": "Plan-2026-solide", "password2": "Plan-2026-solide",
        })

    def test_liste_publique_filtres_et_tri(self):
        r = self.client.get("/projets-gcpnd/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Autoroute de test")
        self.assertContains(r, "250 Md")
        self.assertContains(r, "Non défini")
        self.assertContains(r, "Fiche officielle (PDF)")
        self.assertContains(r, "gcpnd.gouv.ci). Coûts estimatifs indicatifs.")
        self.assertNotContains(r, "Exporter en CSV")
        self.assertEqual([p.code for p in r.context["lignes"]], ["5.01-001", "9.99-001", "5.01-002"])
        r = self.client.get("/projets-gcpnd/?type=PPP")
        self.assertEqual([p.code for p in r.context["lignes"]], ["5.01-002"])
        self.assertEqual({k["type"]: k["n"] for k in r.context["kpis"]}, {"PUB": 1, "PPP": 1, "PRI": 1})
        r = self.client.get("/projets-gcpnd/?q=peage")
        self.assertEqual([p.code for p in r.context["lignes"]], ["5.01-002"])
        r = self.client.get("/projets-gcpnd/?cout=gt1000")  # plus de 1 000 Md : aucun
        self.assertEqual(r.context["nb"], 0)
        r = self.client.get("/projets-gcpnd/?cout=50-250&tri=titre")
        self.assertEqual([p.code for p in r.context["lignes"]], [])
        r = self.client.get("/projets-gcpnd/?cout=250-1000")
        self.assertEqual([p.code for p in r.context["lignes"]], ["5.01-001"])

    def test_apercu_public_limite(self):
        from django.test import override_settings
        from django.conf import settings

        with override_settings(RADAR={**settings.RADAR, "APERCU_GC": 2}):
            r = self.client.get("/projets-gcpnd/")
        self.assertEqual(len(r.context["lignes"]), 2)
        self.assertContains(r, "Aperçu limité aux 2 premiers projets")

    def test_acces_detail_export(self):
        for url in ("/projets-gcpnd/5.01-001/", "/opportunites/OP_5.01-001/"):
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.assertEqual(self.client.get("/projets-gcpnd/?format=csv").status_code, 302)
        r = self.client.get("/opportunites/")
        self.assertContains(r, "Entretien routier")
        self.assertNotContains(r, "Marché en croissance.")
        self.assertContains(self.client.get("/secteur/5.01/"), "Projets du Groupe consultatif")
        self._connecter()
        r = self.client.get("/projets-gcpnd/5.01-001/")
        self.assertContains(r, "inscription-et-prise-de-rendez-vous")
        self.assertContains(r, "5.01.2.1.1")  # action de la matrice du même secteur
        self.assertContains(r, "pilier 5 (Infrastructures stratégiques), secteur 5.01 Infrastructures routières")
        self.assertContains(self.client.get("/opportunites/"), "Marché en croissance.")
        self.assertEqual(self.client.get("/opportunites/OP_x.xx-070/").status_code, 200)
        self.assertContains(self.client.get("/action/5.01.2.1.1/"), "Projets GCPND du même secteur")
        r = self.client.get("/projets-gcpnd/?format=csv")
        txt = r.content.decode("utf-8-sig")
        self.assertIn("Autoroute de test", txt)
        self.assertIn(";250\u00a0000;250;", txt)
        self.client.post("/radar/", {"type": "btp", "appliquer_preset": "1"})
        r = self.client.get("/radar/")
        self.assertContains(r, "Projets et opportunités du Groupe consultatif pour votre profil")
        self.assertEqual(r.context["gc_resultats"][0][0].code, "5.01-001")
