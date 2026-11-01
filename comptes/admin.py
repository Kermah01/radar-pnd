import csv

from django.contrib import admin, messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import path, reverse
from django.utils import timezone

from .forms import GenererCodesForm
from .models import CodeAcces


@admin.register(CodeAcces)
class CodeAccesAdmin(admin.ModelAdmin):
    list_display = ("code", "formule", "lot", "etat", "used_by", "used_at", "expires", "created_at")
    list_filter = ("formule", "actif", ("used_by", admin.EmptyFieldListFilter), "lot")
    search_fields = ("code", "lot", "used_by__email", "used_by__last_name")
    readonly_fields = ("created_at",)
    autocomplete_fields = ("used_by",)
    actions = ["exporter_csv", "revoquer", "reactiver"]
    change_list_template = "admin/comptes/codeacces/change_list.html"
    date_hierarchy = "created_at"

    @admin.display(description="État")
    def etat(self, obj):
        if not obj.actif:
            return "Révoqué"
        if not obj.used_by_id:
            return "Disponible"
        if obj.expires and obj.expires < timezone.now():
            return "Expiré"
        return "Actif"

    def get_urls(self):
        return [path("generer/", self.admin_site.admin_view(self.generer_view), name="comptes_codeacces_generer")] + super().get_urls()

    def generer_view(self, request):
        form = GenererCodesForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            d = form.cleaned_data
            codes = CodeAcces.generer(d["nombre"], d["formule"], d.get("lot", ""), d.get("valable_jusqu_au"))
            messages.success(request, f"{len(codes)} codes générés. Ils sont sélectionnables pour un export CSV.")
            url = reverse("admin:comptes_codeacces_changelist")
            return redirect(f"{url}?lot={d.get('lot', '')}" if d.get("lot") else url)
        ctx = {**self.admin_site.each_context(request), "form": form, "title": "Générer des codes d'accès",
               "opts": self.model._meta}
        return render(request, "admin/comptes/codeacces/generer.html", ctx)

    @admin.action(description="Exporter les codes sélectionnés (CSV)")
    def exporter_csv(self, request, queryset):
        resp = HttpResponse(content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="codes-radar-pnd-{timezone.localdate():%Y%m%d}.csv"'
        resp.write("﻿")
        w = csv.writer(resp, delimiter=";")
        w.writerow(["Code", "Formule", "Lot", "Activable jusqu'au", "Utilisé par", "Expire le"])
        for c in queryset:
            w.writerow([c.code, c.get_formule_display(), c.lot, c.valable_jusqu_au or "",
                        c.used_by.email if c.used_by else "", c.expires.strftime("%d/%m/%Y") if c.expires else ""])
        return resp

    @admin.action(description="Révoquer les codes sélectionnés")
    def revoquer(self, request, queryset):
        n = queryset.update(actif=False)
        self.message_user(request, f"{n} code(s) révoqué(s).", messages.WARNING)

    @admin.action(description="Réactiver les codes sélectionnés")
    def reactiver(self, request, queryset):
        n = queryset.update(actif=True)
        self.message_user(request, f"{n} code(s) réactivé(s).")
