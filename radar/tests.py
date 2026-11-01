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
