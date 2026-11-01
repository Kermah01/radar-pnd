from django.contrib import admin

from .models import Action, Effet, Famille, Indicateur, Opportunite, Pilier, Produit, Profil, ProjetGC, Secteur, Selection


@admin.register(Pilier)
class PilierAdmin(admin.ModelAdmin):
    list_display = ("numero", "nom")


@admin.register(Secteur)
class SecteurAdmin(admin.ModelAdmin):
    list_display = ("code", "nom", "pilier", "total")
    list_filter = ("pilier",)
    search_fields = ("code", "nom")


@admin.register(Effet)
class EffetAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "secteur")
    search_fields = ("code", "label")
    list_filter = ("secteur__pilier",)


@admin.register(Produit)
class ProduitAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "effet")
    search_fields = ("code", "label")


@admin.register(Famille)
class FamilleAdmin(admin.ModelAdmin):
    list_display = ("nom", "slug", "ordre")


@admin.register(Action)
class ActionAdmin(admin.ModelAdmin):
    list_display = ("code", "label", "secteur", "structure", "total", "peak", "trend")
    list_filter = ("pilier", "trend", "familles")
    search_fields = ("code", "label", "structure")
    filter_horizontal = ("familles",)
    raw_id_fields = ("secteur", "effet", "produit")
    readonly_fields = ("search_text",)


@admin.register(Indicateur)
class IndicateurAdmin(admin.ModelAdmin):
    list_display = ("ident", "label", "base", "cible_2030", "source")
    search_fields = ("ident", "label", "parent")


@admin.register(Profil)
class ProfilAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "organisation", "horizon", "taille", "updated_at")
    search_fields = ("user__email", "organisation")


@admin.register(Selection)
class SelectionAdmin(admin.ModelAdmin):
    list_display = ("user", "action", "created_at")
    search_fields = ("user__email", "action__code")
    raw_id_fields = ("action",)


@admin.register(ProjetGC)
class ProjetGCAdmin(admin.ModelAdmin):
    list_display = ("code", "type", "titre", "secteur_code", "secteur_nom", "cout_millions")
    list_filter = ("type", "pilier")
    search_fields = ("code", "titre", "secteur_nom")
    raw_id_fields = ("secteur",)
    readonly_fields = ("search_text",)


@admin.register(Opportunite)
class OpportuniteAdmin(admin.ModelAdmin):
    list_display = ("code", "titre", "secteur_code", "secteur_nom", "pilier")
    list_filter = ("pilier",)
    search_fields = ("code", "titre", "secteur_nom", "resume")
    raw_id_fields = ("secteur",)
