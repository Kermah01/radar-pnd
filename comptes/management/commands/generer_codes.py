"""
Génère des codes d'accès à remettre aux acheteurs de l'ebook (Chariow).

    python manage.py generer_codes --nombre 100 --formule decouverte --lot "Chariow lancement"
    python manage.py generer_codes --nombre 20 --formule pro --csv codes_pro.csv
"""
import csv

from django.core.management.base import BaseCommand

from comptes.models import CodeAcces


class Command(BaseCommand):
    help = "Génère un lot de codes d'accès (formules : decouverte = 3 mois, pro = 12 mois)."

    def add_arguments(self, parser):
        parser.add_argument("--nombre", type=int, default=10)
        parser.add_argument("--formule", choices=[c for c, _ in CodeAcces.FORMULES], default=CodeAcces.DECOUVERTE)
        parser.add_argument("--lot", default="")
        parser.add_argument("--csv", help="Chemin d'un fichier CSV où écrire les codes générés")

    def handle(self, *args, **o):
        codes = CodeAcces.generer(o["nombre"], o["formule"], o["lot"])
        if o.get("csv"):
            with open(o["csv"], "w", newline="", encoding="utf-8-sig") as fh:
                w = csv.writer(fh, delimiter=";")
                w.writerow(["Code", "Formule", "Lot"])
                for c in codes:
                    w.writerow([c.code, c.get_formule_display(), c.lot])
            self.stdout.write(self.style.SUCCESS(f"{len(codes)} codes écrits dans {o['csv']}"))
        else:
            for c in codes:
                self.stdout.write(c.code)
            self.stdout.write(self.style.SUCCESS(f"{len(codes)} codes « {codes[0].get_formule_display()} » générés."))
