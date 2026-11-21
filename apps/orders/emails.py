from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .models import Order
from .pdf import generate_invoice_pdf


def send_order_confirmation_email(order: Order) -> bool:
    """
    Sends natural, professional Spanish confirmation email to the customer
    with full order breakdown and the official PDF invoice attached (when ready).
    """
    subject = f"Confirmación de Pedido {order.order_number} · Tintora Madrid"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "Tintora <hola@tintora.es>")
    to_email = [order.email]

    context = {
        "order": order,
        "company": settings.TINTORA_COMPANY,
        "bank_iban": getattr(settings, "TINTORA_BANK_IBAN", ""),
        "bank_bic": getattr(settings, "TINTORA_BANK_BIC", ""),
        "access_token": str(order.access_token),
    }
    html_content = render_to_string("emails/order_confirmation.html", context)
    company_address = settings.TINTORA_COMPANY.get("ADDRESS", "Madrid")
    text_content = (
        f"Hola {order.first_name},\n\n"
        f"Muchas gracias por tu pedido en Tintora. Hemos recibido correctamente tu encargo {order.order_number} "
        f"por un total de {order.total}€ (21% IVA incluido).\n\n"
        f"Nuestro equipo de taller en {company_address} ya está revisando tus especificaciones y archivos.\n\n"
        f"Puedes consultar el estado de tu pedido en cualquier momento desde tu área de cliente.\n\n"
        f"Atentamente,\n"
        f"El equipo de Tintora Madrid\n"
        f"Tinta que deja huella."
    )

    email = EmailMultiAlternatives(subject, text_content, from_email, to_email)
    email.attach_alternative(html_content, "text/html")

    if hasattr(order, "invoice") and order.invoice:
        try:
            pdf_data = generate_invoice_pdf(order.invoice)
            email.attach(
                f"Factura_{order.invoice.invoice_number}.pdf",
                pdf_data,
                "application/pdf",
            )
        except Exception:
            pass

    try:
        email.send(fail_silently=False)
        return True
    except Exception:
        return False
