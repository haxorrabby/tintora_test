# Generated manually for Phase 4 — access_token + confirmation_email_sent + transfer default

import uuid

from django.db import migrations, models


def fill_access_tokens(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    for order in Order.objects.filter(access_token__isnull=True):
        order.access_token = uuid.uuid4()
        order.save(update_fields=["access_token"])


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="access_token",
            field=models.UUIDField(
                db_index=True,
                default=uuid.uuid4,
                editable=False,
                help_text="Permite consultar confirmación y factura sin iniciar sesión",
                verbose_name="Token de acceso",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="confirmation_email_sent",
            field=models.BooleanField(
                default=False,
                verbose_name="Email de confirmación enviado",
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("stripe", "Tarjeta Bancaria (Stripe)"),
                    ("bizum", "Bizum"),
                    ("redsys", "Redsys (TPV Virtual)"),
                    ("transfer", "Transferencia Bancaria"),
                ],
                default="transfer",
                max_length=25,
                verbose_name="Método de pago",
            ),
        ),
        migrations.RunPython(fill_access_tokens, migrations.RunPython.noop),
    ]
