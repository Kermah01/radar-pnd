from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

admin.site.site_header = "Radar PND · Administration"
admin.site.site_title = "Radar PND"
admin.site.index_title = "Gestion de la plateforme"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("compte/", include("comptes.urls")),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("", include("radar.urls")),
]

handler404 = "radar.views.erreur_404"
