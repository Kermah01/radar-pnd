from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy

from . import views

app_name = "comptes"

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.Connexion.as_view(), name="connexion"),
    path("deconnexion/", views.Deconnexion.as_view(), name="deconnexion"),
    path("activer/", views.activer, name="activer"),
    path("", views.mon_compte, name="compte"),
    path("mot-de-passe/", auth_views.PasswordChangeView.as_view(
        template_name="comptes/mot_de_passe.html", success_url=reverse_lazy("comptes:compte")), name="mot_de_passe"),
]
