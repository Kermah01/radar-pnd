"""Modèles du référentiel PND 2026-2030 et des données propres à chaque utilisateur."""
from django.conf import settings
from django.db import models
from django.urls import reverse

ANNEES = (2026, 2027, 2028, 2029, 2030)

# Code couleur des six piliers (badges, graphiques, cartes)
COULEURS_PILIERS = {
    "1": "#3D5A80",  # Paix, sécurité : bleu ardoise
    "2": "#2F8F46",  # Agriculture : vert feuille
    "3": "#D9730D",  # Investissement privé : orange
    "4": "#8B3F78",  # Capital humain : prune
    "5": "#137C86",  # Infrastructures : bleu canard
    "6": "#9A7B2F",  # Gouvernance : bronze
}


class CoutsMixin(models.Model):
    """Coûts programmés en millions de FCFA, 2026 à 2030."""

    cost_2026 = models.FloatField("Coût 2026 (M FCFA)", default=0)
    cost_2027 = models.FloatField("Coût 2027 (M FCFA)", default=0)
    cost_2028 = models.FloatField("Coût 2028 (M FCFA)", default=0)
    cost_2029 = models.FloatField("Coût 2029 (M FCFA)", default=0)
    cost_2030 = models.FloatField("Coût 2030 (M FCFA)", default=0)
    total = models.FloatField("Total 2026-2030 (M FCFA)", default=0, db_index=True)

    class Meta:
        abstract = True

    @property
    def couts(self):
        return [self.cost_2026, self.cost_2027, self.cost_2028, self.cost_2029, self.cost_2030]

    def set_couts(self, valeurs):
        vals = list(valeurs or []) + [0] * 5
        for an, v in zip(ANNEES, vals[:5]):
            setattr(self, f"cost_{an}", float(v or 0))


class Pilier(models.Model):
    numero = models.CharField("Numéro", max_length=2, unique=True)
    nom = models.CharField(max_length=255)

    class Meta:
        ordering = ["numero"]

    def __str__(self):
        return f"Pilier {self.numero} : {self.nom}"

    @property
    def couleur(self):
        return COULEURS_PILIERS.get(self.numero, "#5B6B82")

    def get_absolute_url(self):
        return reverse("radar:pilier", args=[self.numero])


class Secteur(CoutsMixin):
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=255)
    pilier = models.ForeignKey(Pilier, on_delete=models.CASCADE, related_name="secteurs")
    resultat = models.TextField("Résultat sectoriel", blank=True)
    growth = models.FloatField("Multiplicateur 2030/2026", default=0)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.nom}"

    def get_absolute_url(self):
        return reverse("radar:secteur", args=[self.code])


class Effet(models.Model):
    code = models.CharField(max_length=16, unique=True)
    label = models.TextField()
    secteur = models.ForeignKey(Secteur, on_delete=models.CASCADE, related_name="effets")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.label[:80]}"


class Produit(models.Model):
    code = models.CharField(max_length=20, unique=True)
    label = models.TextField()
    effet = models.ForeignKey(Effet, on_delete=models.CASCADE, related_name="produits")

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} {self.label[:80]}"


class Famille(models.Model):
    """Famille d'opportunités (type de prestation attendu)."""

    nom = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=60, unique=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "nom"]
        verbose_name = "famille d'opportunités"
        verbose_name_plural = "familles d'opportunités"

    def __str__(self):
        return self.nom


class Action(CoutsMixin):
    TENDANCES = ["Nouvelle", "Hausse forte", "Hausse", "Stable", "Baisse"]

    code = models.CharField(max_length=24, unique=True)
    label = models.TextField("Intitulé")
    pilier = models.ForeignKey(Pilier, on_delete=models.CASCADE, related_name="actions")
    secteur = models.ForeignKey(Secteur, on_delete=models.CASCADE, related_name="actions")
    effet = models.ForeignKey(Effet, on_delete=models.CASCADE, related_name="actions")
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name="actions")
    structure = models.CharField("Structure responsable", max_length=255, blank=True)
    peak = models.PositiveSmallIntegerField("Année de pic", null=True, blank=True)
    trend = models.CharField("Tendance", max_length=20, db_index=True)
    growth = models.FloatField("Multiplicateur 2030/2026", default=0, db_index=True)
    page = models.PositiveIntegerField("Page Tome 3", null=True, blank=True)
    ordre = models.PositiveIntegerField(default=0, db_index=True)
    familles = models.ManyToManyField(Famille, related_name="actions", blank=True)
    search_text = models.TextField(editable=False, blank=True)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.code} {self.label[:80]}"

    def get_absolute_url(self):
        return reverse("radar:action", args=[self.code])

    @property
    def couleur(self):
        return COULEURS_PILIERS.get(self.code.split(".")[0], "#5B6B82")

    def indicateurs(self):
        """Indicateurs du produit, de l'effet puis du résultat sectoriel."""
        niveaux = [(self.produit.code, "Produit"), (self.effet.code, "Effet"), (self.secteur.code, "Résultat sectoriel")]
        par_parent = {}
        for ind in Indicateur.objects.filter(parent__in=[c for c, _ in niveaux]):
            par_parent.setdefault(ind.parent, []).append(ind)
        out = []
        for code, niveau in niveaux:
            for ind in par_parent.get(code, []):
                ind.niveau_label = niveau
                out.append(ind)
        return out


class Indicateur(models.Model):
    ident = models.CharField("Identifiant", max_length=24, unique=True)
    parent = models.CharField("Code de l'élément mesuré", max_length=20, db_index=True)
    label = models.TextField()
    annee = models.CharField("Année de référence", max_length=255, blank=True)
    base = models.CharField("Valeur de référence", max_length=255, blank=True)
    source = models.CharField(max_length=255, blank=True)
    cible_2026 = models.CharField(max_length=255, blank=True)
    cible_2027 = models.CharField(max_length=255, blank=True)
    cible_2028 = models.CharField(max_length=255, blank=True)
    cible_2029 = models.CharField(max_length=255, blank=True)
    cible_2030 = models.CharField(max_length=255, blank=True)
    odd = models.CharField("ODD", max_length=255, blank=True)
    ordre = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["ordre"]

    def __str__(self):
        return f"{self.ident} {self.label[:80]}"

    @property
    def cibles(self):
        return [self.cible_2026, self.cible_2027, self.cible_2028, self.cible_2029, self.cible_2030]

    @property
    def cible_finale(self):
        if self.cible_2030:
            return self.cible_2030
        for c in reversed(self.cibles):
            if c:
                return c
        return ""

    @property
    def niveau(self):
        n = self.parent.count(".")
        return {1: "Résultat sectoriel", 2: "Effet", 3: "Produit"}.get(n, "")


# --------------------------------------------------------------------------
# Données utilisateur
# --------------------------------------------------------------------------


class Profil(models.Model):
    HORIZONS = [("any", "Indifférent"), ("early", "Court terme (pic en 2026-2027)"), ("late", "Moyen terme (pic en 2028-2030)")]
    TAILLES = [("any", "Toutes tailles"), ("s", "Moins de 10 Md FCFA"), ("m", "10 à 200 Md FCFA"), ("l", "Plus de 200 Md FCFA")]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profil_radar")
    type = models.CharField("Profil type", max_length=20, default="etudes")
    familles = models.JSONField(default=list, blank=True)
    secteurs = models.JSONField(default=list, blank=True)
    horizon = models.CharField(max_length=8, choices=HORIZONS, default="any")
    taille = models.CharField(max_length=8, choices=TAILLES, default="any")
    organisation = models.CharField("Organisation", max_length=200, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "profil radar"
        verbose_name_plural = "profils radar"

    def __str__(self):
        return f"Profil de {self.user}"

    def as_dict(self):
        return {"type": self.type, "familles": list(self.familles or []), "secteurs": list(self.secteurs or []),
                "horizon": self.horizon, "taille": self.taille}


class Selection(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="selections")
    action = models.ForeignKey(Action, on_delete=models.CASCADE, related_name="selections")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["user", "action"], name="selection_unique")]
        verbose_name = "action sélectionnée"
        verbose_name_plural = "actions sélectionnées"

    def __str__(self):
        return f"{self.user} : {self.action.code}"
