from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailBackend(ModelBackend):
    """Connexion par adresse électronique (ou nom d'utilisateur pour l'administration)."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        ident = (username or kwargs.get("email") or "").strip()
        if not ident or password is None:
            return None
        user = User.objects.filter(email__iexact=ident).order_by("id").first() or User.objects.filter(
            username__iexact=ident
        ).first()
        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        User().set_password(password)  # temps constant
        return None
