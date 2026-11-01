from django.urls import path

from . import views, views_gc

app_name = "radar"

urlpatterns = [
    path("", views.accueil, name="accueil"),
    path("radar/", views.mon_radar, name="radar"),
    path("explorer/", views.explorer, name="explorer"),
    path("tendances/", views.tendances, name="tendances"),
    path("methode-radar/", views.methode, name="methode"),
    path("a-propos/", views.apropos, name="apropos"),
    path("pilier/<str:numero>/", views.pilier_detail, name="pilier"),
    path("secteur/<str:code>/", views.secteur_detail, name="secteur"),
    path("action/<str:code>/", views.action_detail, name="action"),
    path("action/<str:code>/word/", views.export_action_docx, name="action_docx"),
    path("action/<str:code>/selection/", views.selection_toggle, name="selection_toggle"),
    path("action/<str:code>/note/", views.selection_note, name="selection_note"),
    path("ma-selection/", views.selection, name="selection"),
    path("ma-selection/export.<str:fmt>", views.export_selection, name="selection_export"),
    path("projets-gcpnd/", views_gc.projets_gc, name="projets_gc"),
    path("projets-gcpnd/<str:code>/", views_gc.projet_gc, name="projet_gc"),
    path("opportunites/", views_gc.opportunites, name="opportunites"),
    path("opportunites/<str:code>/", views_gc.opportunite, name="opportunite"),
]
