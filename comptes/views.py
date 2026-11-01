from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from radar.models import Profil
from radar.services.scoring import profil_preset

from .forms import ActivationForm, ConnexionForm, InscriptionForm
from .models import CodeAcces, acces_actif

User = get_user_model()


def _next(request, defaut="radar:radar"):
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return defaut


def inscription(request):
    if request.user.is_authenticated:
        return redirect("comptes:activer")
    initial = {"code": request.GET.get("code", "")}
    form = InscriptionForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            code = CodeAcces.objects.select_for_update().get(pk=form.code_obj.pk)
            if not code.peut_etre_active():
                form.add_error("code", "Ce code d'accès vient d'être utilisé.")
                return render(request, "comptes/inscription.html", {"form": form})
            user = User.objects.create_user(username=d["email"], email=d["email"], password=d["password1"],
                                            first_name=d["prenom"], last_name=d["nom"])
            code.activer(user)
            Profil.objects.create(user=user, organisation=d.get("organisation", ""), **profil_preset("etudes"))
        login(request, user, backend="comptes.backends.EmailBackend")
        messages.success(request, f"Bienvenue {user.first_name}. Votre accès {code.get_formule_display()} est actif "
                                  f"jusqu'au {code.expires:%d/%m/%Y}. Commencez par choisir votre profil.")
        return redirect("radar:radar")
    return render(request, "comptes/inscription.html", {"form": form})


class Connexion(LoginView):
    template_name = "comptes/connexion.html"
    authentication_form = ConnexionForm
    redirect_authenticated_user = True


class Deconnexion(LogoutView):
    pass


@login_required
def activer(request):
    form = ActivationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            code = CodeAcces.objects.select_for_update().get(pk=form.code_obj.pk)
            if code.peut_etre_active():
                code.activer(request.user)
                messages.success(request, f"Code activé : accès {code.get_formule_display()} valable jusqu'au "
                                          f"{code.expires:%d/%m/%Y}.")
                return redirect(_next(request))
            form.add_error("code", "Ce code d'accès vient d'être utilisé.")
    return render(request, "comptes/activer.html", {"form": form, "acces": acces_actif(request.user),
                                                     "next": request.GET.get("next", "")})


@login_required
def mon_compte(request):
    prof, _ = Profil.objects.get_or_create(user=request.user, defaults=profil_preset("etudes"))
    if request.method == "POST":
        prof.organisation = request.POST.get("organisation", "")[:200]
        prof.save(update_fields=["organisation", "updated_at"])
        u = request.user
        u.first_name = request.POST.get("prenom", u.first_name)[:80]
        u.last_name = request.POST.get("nom", u.last_name)[:80]
        u.save(update_fields=["first_name", "last_name"])
        messages.success(request, "Vos informations ont été mises à jour.")
        return redirect("comptes:compte")
    return render(request, "comptes/compte.html", {
        "profil": prof, "acces": acces_actif(request.user),
        "codes": request.user.codes_acces.order_by("-used_at"),
    })
