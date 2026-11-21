from django import forms
from django.core.exceptions import ValidationError

from .models import QuoteRequest, WebPackage


class QuoteRequestForm(forms.ModelForm):
    privacy_accepted = forms.BooleanField(
        required=True,
        label="He leído y acepto la Política de Privacidad.",
    )
    website_url = forms.CharField(required=False, widget=forms.HiddenInput)
    budget_range = forms.ChoiceField(
        required=False,
        choices=(
            ("", "Selecciona un rango"),
            ("Menos de 1.000€", "Menos de 1.000€"),
            ("1.000€ - 3.000€", "1.000€ - 3.000€"),
            ("3.000€ - 6.000€", "3.000€ - 6.000€"),
            ("Más de 6.000€", "Más de 6.000€"),
            ("Por definir", "Por definir"),
        ),
        label="Presupuesto orientativo",
    )

    class Meta:
        model = QuoteRequest
        fields = (
            "package",
            "full_name",
            "company_name",
            "email",
            "phone",
            "nif_cif",
            "budget_range",
            "project_description",
            "attachment",
        )
        labels = {
            "package": "Paquete de interés",
            "full_name": "Nombre y apellidos",
            "company_name": "Empresa o marca",
            "email": "Correo electrónico",
            "phone": "Teléfono o WhatsApp",
            "nif_cif": "NIF / CIF (opcional)",
            "project_description": "Cuéntanos qué necesitas",
            "attachment": "Brief o archivo (opcional)",
        }
        widgets = {
            "package": forms.Select(attrs={"class": "input-editorial"}),
            "full_name": forms.TextInput(attrs={"autocomplete": "name", "class": "input-editorial"}),
            "company_name": forms.TextInput(attrs={"autocomplete": "organization", "class": "input-editorial"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "class": "input-editorial"}),
            "phone": forms.TextInput(attrs={"type": "tel", "autocomplete": "tel", "class": "input-editorial"}),
            "nif_cif": forms.TextInput(attrs={"class": "input-editorial"}),
            "project_description": forms.Textarea(attrs={"rows": 5, "class": "input-editorial"}),
            "attachment": forms.ClearableFileInput(attrs={"accept": ".pdf,.doc,.docx,.zip,.jpg,.jpeg,.png", "class": "input-editorial file:mr-4 file:py-2 file:px-4 file:border-0 file:text-xs file:font-semibold file:uppercase file:tracking-wider file:bg-ink file:text-paper hover:file:bg-ink/80 dark:file:bg-paper dark:file:text-ink cursor-pointer"}),
        }

    def __init__(self, *args, **kwargs):
        package_slug = kwargs.pop("package_slug", None)
        super().__init__(*args, **kwargs)
        self.fields["package"].queryset = WebPackage.objects.filter(is_active=True).order_by("order", "name")
        self.fields["package"].required = False
        self.fields["full_name"].widget.attrs.update({"class": "input-editorial"})
        self.fields["email"].widget.attrs.update({"class": "input-editorial"})
        self.fields["phone"].widget.attrs.update({"class": "input-editorial"})
        self.fields["project_description"].widget.attrs.update({"class": "input-editorial"})
        self.fields["budget_range"].widget.attrs.update({"class": "input-editorial"})
        self.fields["nif_cif"].widget.attrs.update({"class": "input-editorial"})
        self.fields["privacy_accepted"].widget.attrs.update({"class": "h-4 w-4 accent-vermilion rounded border-ink/20 dark:border-paper/20"})
        if package_slug:
            self.initial["package"] = WebPackage.objects.filter(slug=package_slug, is_active=True).first()

    def clean_website_url(self):
        value = self.cleaned_data.get("website_url", "").strip()
        if value:
            raise ValidationError("No se ha podido validar la solicitud.")
        return value

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if not attachment:
            return attachment
        allowed_extensions = {".pdf", ".doc", ".docx", ".zip", ".jpg", ".jpeg", ".png"}
        extension = "." + attachment.name.rsplit(".", 1)[-1].lower() if "." in attachment.name else ""
        if extension not in allowed_extensions:
            raise ValidationError("Adjunta un PDF, Word, ZIP, JPG o PNG.")
        if attachment.size > 10 * 1024 * 1024:
            raise ValidationError("El archivo no puede superar los 10 MB.")
        return attachment
