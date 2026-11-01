"""Codes d'accès vendus avec l'ebook (Chariow) et droits d'accès des utilisateurs."""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

# Alphabet sans caractères ambigus (0/O, 1/I/L)
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def nouveau_code(prefixe="RPND"):
    bloc = lambda: "".join(secrets.choice(ALPHABET) for _ in range(4))  # noqa: E731
    return f"{prefixe}-{bloc()}-{bloc()}"


def normaliser_code(code):
    return (code or "").strip().upper().replace(" ", "")


class CodeAcces(models.Model):
    DECOUVERTE = "decouverte"
    PRO = "pro"
    FORMULES = [(DECOUVERTE, "Découverte 3 mois"), (PRO, "Pro 12 mois")]
    DUREES_JOURS = {DECOUVERTE: 92, PRO: 366}

    code = models.CharField(max_length=32, unique=True)
    formule = models.CharField(max_length=20, choices=FORMULES, default=DECOUVERTE)
    lot = models.CharField("Lot", max_length=80, blank=True, help_text="Libellé libre pour retrouver une série de codes")
    created_at = models.DateTimeField("Créé le", auto_now_add=True)
    valable_jusqu_au = models.DateField(
        "Activable jusqu'au", null=True, blank=True, help_text="Laisser vide : activable sans limite de date"
    )
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="codes_acces",
        verbose_name="Utilisé par",
    )
    used_at = models.DateTimeField("Activé le", null=True, blank=True)
    expires = models.DateTimeField("Accès valable jusqu'au", null=True, blank=True)
    actif = models.BooleanField(default=True, help_text="Décocher pour révoquer le code")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "code d'accès"
        verbose_name_plural = "codes d'accès"

    def __str__(self):
        return self.code

    @property
    def est_utilise(self):
        return self.used_by_id is not None

    def peut_etre_active(self):
        if not self.actif or self.est_utilise:
            return False
        if self.valable_jusqu_au and timezone.localdate() > self.valable_jusqu_au:
            return False
        return True

    def activer(self, user):
        """Rattache le code à l'utilisateur. Prolonge un accès encore en cours."""
        now = timezone.now()
        depart = now
        en_cours = acces_actif(user)
        if en_cours and en_cours.expires and en_cours.expires > now:
            depart = en_cours.expires
        self.used_by = user
        self.used_at = now
        self.expires = depart + timedelta(days=self.DUREES_JOURS[self.formule])
        self.save(update_fields=["used_by", "used_at", "expires"])
        return self

    @classmethod
    def generer(cls, nombre, formule=DECOUVERTE, lot="", valable_jusqu_au=None, prefixe="RPND"):
        crees = []
        while len(crees) < nombre:
            code = nouveau_code(prefixe)
            if cls.objects.filter(code=code).exists():
                continue
            crees.append(cls.objects.create(code=code, formule=formule, lot=lot, valable_jusqu_au=valable_jusqu_au))
        return crees


def acces_actif(user):
    """Code d'accès en cours de validité pour cet utilisateur (le plus lointain), ou None."""
    if not user or not user.is_authenticated:
        return None
    return (
        CodeAcces.objects.filter(used_by=user, actif=True, expires__gt=timezone.now()).order_by("-expires").first()
    )


def a_acces(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return acces_actif(user) is not None
