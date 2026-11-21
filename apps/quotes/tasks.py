import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="quotes.send_quote_request_notifications",
    max_retries=3,
    default_retry_delay=60,
)
def send_quote_request_notifications(self, quote_id: int) -> bool:
    from .models import QuoteRequest

    try:
        quote = QuoteRequest.objects.select_related("package").get(pk=quote_id)
    except QuoteRequest.DoesNotExist:
        logger.warning("Quote request %s no longer exists", quote_id)
        return False

    company_email = settings.TINTORA_COMPANY.get("EMAIL", settings.DEFAULT_FROM_EMAIL)
    package_name = quote.package.name if quote.package else "A medida"
    internal_body = (
        f"Nueva solicitud de Desarrollo Web\n\n"
        f"Contacto: {quote.full_name}\nEmpresa: {quote.company_name or 'No indicada'}\n"
        f"Email: {quote.email}\nTeléfono: {quote.phone}\n"
        f"Paquete: {package_name}\nPresupuesto: {quote.budget_range or 'Por definir'}\n\n"
        f"Proyecto:\n{quote.project_description}\n\nLead #{quote.pk}"
    )
    customer_body = (
        f"Hola {quote.full_name},\n\n"
        "Hemos recibido tu solicitud de presupuesto para Desarrollo Web. "
        "Revisaremos el alcance y te responderemos en un día laborable.\n\n"
        f"Paquete de interés: {package_name}\n"
        f"Referencia de solicitud: {quote.pk}\n\n"
        "Gracias por pensar en Tintora.\nTinta que deja huella."
    )
    try:
        send_mail(
            f"Nueva solicitud web · {quote.full_name}",
            internal_body,
            settings.DEFAULT_FROM_EMAIL,
            [company_email],
            fail_silently=False,
        )
        send_mail(
            "Hemos recibido tu solicitud · Tintora",
            customer_body,
            settings.DEFAULT_FROM_EMAIL,
            [quote.email],
            fail_silently=False,
        )
        return True
    except Exception as exc:
        logger.exception("Quote notification failed for lead %s", quote_id)
        raise self.retry(exc=exc) from exc


def queue_quote_request_notifications(quote_id: int) -> bool:
    if settings.DEBUG:
        try:
            return bool(send_quote_request_notifications(quote_id))
        except Exception:
            logger.exception("Development quote notification failed for lead %s", quote_id)
            return False

    try:
        send_quote_request_notifications.delay(quote_id)
        return True
    except Exception:
        logger.warning("Celery unavailable; sending quote notifications synchronously.")
        try:
            return bool(send_quote_request_notifications(quote_id))
        except Exception:
            logger.exception("Synchronous quote notification failed for lead %s", quote_id)
            return False
