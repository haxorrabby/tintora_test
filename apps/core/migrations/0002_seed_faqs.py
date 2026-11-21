# Seed the FAQ entries that were previously hardcoded in apps/core/views.py.
# Content is factual company copy already published on the live homepage.

from django.db import migrations

FAQS = [
    {
        "group": "pagos",
        "order": 10,
        "question": "¿Los precios mostrados incluyen el IVA 21%?",
        "answer": (
            "Sí, todos los precios publicados en nuestra web incluyen el IVA del 21% conforme a la "
            "normativa fiscal española. En el carrito y en la factura siempre desglasamos la base "
            "imponible, el IVA y el total de forma separada, tal y como exige la Agencia Tributaria."
        ),
    },
    {
        "group": "disenos",
        "order": 20,
        "question": "¿Qué resolución y formato debe tener mi archivo?",
        "answer": (
            "Para imprenta recomendamos PDF/X-4 o AI/INDD con perfil de color CMYK Fogra39, a 300 dpi "
            "con 3 mm de sangrado. También aceptamos PNG y JPG a 300 dpi o superior. Nuestro equipo de "
            "preimpresión revisa cada archivo de forma gratuita antes de enviarlo a máquina."
        ),
    },
    {
        "group": "impresion",
        "order": 30,
        "question": "¿Puedo pedir una prueba de impresión antes de tiradas grandes?",
        "answer": (
            "Por supuesto. En todos los productos de impresión y sublimación puedes añadir 'Pide una "
            "prueba' durante el proceso de compra. Recibirás una muestra física de un ejemplar antes de "
            "que lancemos la tirada completa. El coste de la prueba se descuenta del pedido final."
        ),
    },
    {
        "group": "pedidos",
        "order": 40,
        "question": "¿Cuáles son los plazos de entrega?",
        "answer": (
            "Los plazos estándar son 3–5 días laborables para imprenta y 4–7 días para sublimación. El "
            "servicio express (24/48 h) está disponible para muchos productos. Los plazos exactos "
            "aparecen en la ficha de cada producto y se confirman en el resumen de pedido con la fecha "
            "estimada de entrega."
        ),
    },
    {
        "group": "envios",
        "order": 50,
        "question": "¿Qué couriers utilizan y a dónde envían?",
        "answer": (
            "Enviamos con Correos, SEUR, MRW y GLS. Cubrimos Madrid capital y área metropolitana "
            "(entrega local express), Península, Baleares, Canarias y la Unión Europea. Las tarifas de "
            "envío se calculan automáticamente por peso y zona durante el proceso de compra. También "
            "puedes recoger en nuestro taller de Atocha 45 sin coste."
        ),
    },
    {
        "group": "pagos",
        "order": 60,
        "question": "¿Emitís factura con NIF/CIF para empresas?",
        "answer": (
            "Sí. Emitimos factura ordinaria (factura simplificada para pedidos menores de 400 € a "
            "particulares) con todos los datos fiscales requeridos: número de factura secuencial, "
            "fecha, datos del emisor y receptor, NIF/CIF, base imponible, tipo de IVA y cuota. Las "
            "facturas se generan en PDF y quedan disponibles en tu área de cliente."
        ),
    },
]


def seed_faqs(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    for entry in FAQS:
        FAQ.objects.get_or_create(
            question=entry["question"],
            defaults={
                "group": entry["group"],
                "answer": entry["answer"],
                "is_published": True,
                "order": entry["order"],
            },
        )


def unseed_faqs(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    FAQ.objects.filter(question__in=[e["question"] for e in FAQS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_faqs, unseed_faqs),
    ]
