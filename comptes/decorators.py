from functools import wraps
from urllib.parse import quote

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect
from django.urls import reverse

from .models import a_acces


def acces_requis(view):
    """Réservé aux comptes disposant d'un accès en cours (code activé et non expiré)."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not a_acces(request.user):
            messages.info(request, "Votre accès a expiré ou n'est pas encore activé. Saisissez un code d'accès pour continuer.")
            return redirect(f"{reverse('comptes:activer')}?next={quote(request.get_full_path())}")
        return view(request, *args, **kwargs)

    return wrapper
