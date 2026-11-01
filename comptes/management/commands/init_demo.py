"""
Crée le compte administrateur, un compte de démonstration et quelques codes d'accès de démonstration.
Commande idempotente.

    python manage.py init_demo
    python manage.py init_demo --sans-codes-demo

Variables d'environnement reconnues :
    ADMIN_EMAIL, ADMIN_PASSWORD, DEMO_EMAIL, DEMO_PASSWORD
Aucun mot de passe par défaut n'est utilisé en production (DEBUG=False) : sans ADMIN_PASSWORD,
le compte administrateur n'est pas créé ; sans DEMO_PASSWORD, le compte de démonstration n'est pas créé.
"""
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from comptes.models import CodeAcces
from radar.models import Profil
from radar.services.scoring import profil_preset

CODES_DEMO = [
    ("DEMO-DECO-0001", CodeAcces.DECOUVERTE), ("DEMO-DECO-0002", CodeAcces.DECOUVERTE),
    ("DEMO-DECO-0003", CodeAcces.DECOUVERTE), ("DEMO-PRO0-0001", CodeAcces.PRO), ("DEMO-PRO0-0002", CodeAcces.PRO),
]


class Command(BaseCommand):
    help = "Initialise les comptes administrateur et démonstration, et des codes d'accès de démonstration."

    def add_arguments(self, parser):
        parser.add_argument("--sans-codes-demo", action="store_true")

    def handle(self, *args, **o):
        User = get_user_model()
        ae = os.environ.get("ADMIN_EMAIL", "admin@radar-pnd.local")
        ap = os.environ.get("ADMIN_PASSWORD") or ("admin-local-dev" if settings.DEBUG else None)
        admin = User.objects.filter(username=ae).first()
        if not admin and not ap:
            self.stdout.write(self.style.WARNING("ADMIN_PASSWORD absent : compte administrateur non créé."))
        elif not admin:
            admin = User.objects.create_superuser(username=ae, email=ae, password=ap, first_name="Administrateur")
            self.stdout.write(f"Superutilisateur créé : {ae}")
        else:
            self.stdout.write(f"Superutilisateur déjà présent : {ae}")

        de = os.environ.get("DEMO_EMAIL", "demo@radar-pnd.local")
        dp = os.environ.get("DEMO_PASSWORD") or ("demo-local-dev" if settings.DEBUG else None)
        demo = User.objects.filter(username=de).first()
        if not demo and not dp:
            self.stdout.write(self.style.WARNING("DEMO_PASSWORD absent : compte de démonstration non créé."))
            self.stdout.write(self.style.SUCCESS("Initialisation terminée."))
            return
        if not demo:
            demo = User.objects.create_user(username=de, email=de, password=dp, first_name="Compte", last_name="Démo")
            self.stdout.write(f"Compte de démonstration créé : {de}")
        Profil.objects.get_or_create(user=demo, defaults={**profil_preset("etudes"), "organisation": "Démonstration"})
        code_demo, _ = CodeAcces.objects.get_or_create(code="DEMO-COMPTE-0000", defaults={"formule": CodeAcces.PRO,
                                                                                            "lot": "Démonstration"})
        if code_demo.used_by_id != demo.id or not code_demo.expires or code_demo.expires < timezone.now():
            code_demo.used_by = demo
            code_demo.used_at = timezone.now()
            code_demo.expires = timezone.now() + timedelta(days=366)
            code_demo.actif = True
            code_demo.save()

        if not o["sans_codes_demo"]:
            for code, formule in CODES_DEMO:
                CodeAcces.objects.get_or_create(code=code, defaults={"formule": formule, "lot": "Démonstration"})
            libres = CodeAcces.objects.filter(lot="Démonstration", used_by__isnull=True).values_list("code", flat=True)
            self.stdout.write("Codes de démonstration disponibles : " + ", ".join(libres))
        self.stdout.write(self.style.SUCCESS("Initialisation terminée."))
