from django.conf import settings

from comptes.models import a_acces


def radar(request):
    user = getattr(request, "user", None)
    acces = a_acces(user)
    nb_sel = 0
    if acces:
        nb_sel = user.selections.count()
    return {
        "a_acces": acces,
        "nb_selection": nb_sel,
        "chariow_url": settings.RADAR.get("CHARIOW_URL") or "",
        "contact_email": settings.RADAR.get("CONTACT_EMAIL"),
    }
