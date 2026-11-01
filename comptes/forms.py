from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm

from .models import CodeAcces, normaliser_code

User = get_user_model()


def _verifier_code(valeur):
    code = normaliser_code(valeur)
    obj = CodeAcces.objects.filter(code=code).first()
    if not obj:
        raise forms.ValidationError("Ce code d'accès est inconnu. Vérifiez la saisie (format RPND-XXXX-XXXX).")
    if obj.est_utilise:
        raise forms.ValidationError("Ce code d'accès a déjà été utilisé.")
    if not obj.peut_etre_active():
        raise forms.ValidationError("Ce code d'accès n'est plus valable. Contactez-nous si vous pensez qu'il s'agit d'une erreur.")
    return obj


class InscriptionForm(forms.Form):
    code = forms.CharField(label="Code d'accès", max_length=32,
                           help_text="Il figure dans l'ebook ou dans le courriel de confirmation de votre achat.",
                           widget=forms.TextInput(attrs={"placeholder": "RPND-XXXX-XXXX", "autocomplete": "off",
                                                         "autocapitalize": "characters", "spellcheck": "false"}))
    prenom = forms.CharField(label="Prénom", max_length=80)
    nom = forms.CharField(label="Nom", max_length=80)
    email = forms.EmailField(label="Adresse électronique", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    organisation = forms.CharField(label="Organisation (facultatif)", max_length=200, required=False)
    password1 = forms.CharField(label="Mot de passe", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                help_text="8 caractères au minimum, pas uniquement des chiffres.")
    password2 = forms.CharField(label="Confirmez le mot de passe", strip=False,
                                widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    def clean_code(self):
        self.code_obj = _verifier_code(self.cleaned_data["code"])
        return self.code_obj.code

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError(
                "Un compte existe déjà avec cette adresse. Connectez-vous, puis activez votre code depuis votre compte."
            )
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Les deux mots de passe ne correspondent pas.")
        if p1:
            tmp = User(username=data.get("email") or "", email=data.get("email") or "",
                       first_name=data.get("prenom") or "", last_name=data.get("nom") or "")
            try:
                password_validation.validate_password(p1, tmp)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return data


class ActivationForm(forms.Form):
    code = forms.CharField(label="Code d'accès", max_length=32,
                           widget=forms.TextInput(attrs={"placeholder": "RPND-XXXX-XXXX", "autocomplete": "off",
                                                         "autocapitalize": "characters"}))

    def clean_code(self):
        self.code_obj = _verifier_code(self.cleaned_data["code"])
        return self.code_obj.code


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(label="Adresse électronique",
                               widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "email"}))
    error_messages = {
        "invalid_login": "Adresse électronique ou mot de passe incorrect.",
        "inactive": "Ce compte est désactivé.",
    }


class GenererCodesForm(forms.Form):
    formule = forms.ChoiceField(choices=CodeAcces.FORMULES)
    nombre = forms.IntegerField(min_value=1, max_value=1000, initial=50)
    lot = forms.CharField(max_length=80, required=False, help_text="Exemple : Chariow novembre 2026")
    valable_jusqu_au = forms.DateField(required=False, label="Activable jusqu'au (facultatif)",
                                       widget=forms.DateInput(attrs={"type": "date"}))
