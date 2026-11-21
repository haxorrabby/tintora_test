from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

EMAIL_VERIFICATION_SALT = "tintora.accounts.email-verification"
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24


def make_email_verification_token(user) -> str:
    return signing.dumps({"user_id": user.pk, "email": user.email}, salt=EMAIL_VERIFICATION_SALT)


def send_email_verification(user, request) -> bool:
    token = make_email_verification_token(user)
    verify_url = request.build_absolute_uri(
        reverse("customer:verify_email", kwargs={"token": token})
    )
    body = (
        f"Hola {user.first_name or user.email},\n\n"
        "Gracias por crear tu cuenta en Tintora. Confirma tu correo desde este enlace, válido durante 24 horas:\n\n"
        f"{verify_url}\n\n"
        "Si no has solicitado esta cuenta, puedes ignorar este mensaje.\n\n"
        "Tintora · Tinta que deja huella."
    )
    return bool(
        send_mail(
            "Confirma tu correo electrónico · Tintora",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
    )
