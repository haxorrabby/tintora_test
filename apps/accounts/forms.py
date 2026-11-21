import uuid

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import CustomUser, SavedAddress


class CustomerAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_verified:
            raise ValidationError(
                "Confirma tu correo electrónico antes de iniciar sesión.",
                code="email_unverified",
            )


class CustomerRegistrationForm(forms.Form):
    email = forms.EmailField(label="Correo electrónico")
    first_name = forms.CharField(label="Nombre", max_length=150)
    last_name = forms.CharField(label="Apellidos", max_length=150)
    customer_type = forms.ChoiceField(label="Tipo de cliente", choices=CustomUser.CustomerType.choices)
    company_name = forms.CharField(label="Empresa", max_length=255, required=False)
    nif_cif = forms.CharField(label="NIF / CIF / NIE", max_length=30, required=False)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "input-editorial"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise ValidationError("Ya existe una cuenta con este correo electrónico.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        if password1:
            candidate = CustomUser(
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("first_name", ""),
                last_name=cleaned_data.get("last_name", ""),
            )
            try:
                validate_password(password1, user=candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned_data

    def save(self):
        if not self.is_valid():
            raise ValueError("Cannot save an invalid registration form.")
        return CustomUser.objects.create_user(
            username=uuid.uuid4().hex,
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            customer_type=self.cleaned_data["customer_type"],
            company_name=self.cleaned_data["company_name"].strip(),
            nif_cif=self.cleaned_data["nif_cif"].strip(),
        )


class ProfileUpdateForm(UserChangeForm):
    """Form for updating customer profile"""

    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'customer_type',
            'company_name',
            'nif_cif',
            'address',
            'postal_code',
            'city',
            'province',
            'country',
            'newsletter_subscribed',
        ]
        labels = {
            'first_name': 'Nombre',
            'last_name': 'Apellidos',
            'email': 'Correo electrónico',
            'phone': 'Teléfono',
            'customer_type': 'Tipo de cliente',
            'company_name': 'Razón Social / Empresa',
            'nif_cif': 'NIF / CIF / NIE',
            'address': 'Dirección',
            'postal_code': 'Código Postal',
            'city': 'Ciudad',
            'province': 'Provincia',
            'country': 'País',
            'newsletter_subscribed': 'Suscribirse a la Gaceta Tintora',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove password field from form
        if 'password' in self.fields:
            del self.fields['password']

        # Make email readonly (username is derived from email)
        self.fields['email'].widget.attrs['readonly'] = True

        # Add CSS classes
        for _field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'h-4 w-4 accent-vermilion rounded border-ink/20 dark:border-paper/20'
            else:
                field.widget.attrs['class'] = 'input-editorial'


class SavedAddressForm(forms.ModelForm):
    """Form for creating/editing saved addresses"""

    class Meta:
        model = SavedAddress
        fields = [
            'label',
            'address_line1',
            'address_line2',
            'postal_code',
            'city',
            'province',
            'country',
            'is_default',
        ]
        labels = {
            'label': 'Etiqueta',
            'address_line1': 'Dirección línea 1',
            'address_line2': 'Dirección línea 2 (opcional)',
            'postal_code': 'Código Postal',
            'city': 'Ciudad',
            'province': 'Provincia',
            'country': 'País',
            'is_default': 'Establecer como dirección por defecto',
        }
        widgets = {
            'address_line1': forms.TextInput(attrs={'class': 'input-editorial'}),
            'address_line2': forms.TextInput(attrs={'class': 'input-editorial'}),
            'postal_code': forms.TextInput(attrs={'class': 'input-editorial'}),
            'city': forms.TextInput(attrs={'class': 'input-editorial'}),
            'province': forms.TextInput(attrs={'class': 'input-editorial'}),
            'country': forms.TextInput(attrs={'class': 'input-editorial'}),
            'label': forms.TextInput(attrs={'class': 'input-editorial'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'h-4 w-4 accent-vermilion rounded border-ink/20 dark:border-paper/20'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'input-editorial'
