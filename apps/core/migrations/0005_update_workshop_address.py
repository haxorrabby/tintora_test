from django.db import migrations


OLD_ADDRESS = "Atocha 45"
NEW_ADDRESS = "Getafe (C. Núñez de Balboa, 30, Loc 1, 28902)"


def update_faq_address(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    for faq in FAQ.objects.filter(answer__contains=OLD_ADDRESS):
        faq.answer = faq.answer.replace(OLD_ADDRESS, NEW_ADDRESS)
        faq.save(update_fields=["answer"])


def restore_faq_address(apps, schema_editor):
    FAQ = apps.get_model("core", "FAQ")
    for faq in FAQ.objects.filter(answer__contains=NEW_ADDRESS):
        faq.answer = faq.answer.replace(NEW_ADDRESS, OLD_ADDRESS)
        faq.save(update_fields=["answer"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_portfolioitem_and_more"),
    ]

    operations = [
        migrations.RunPython(update_faq_address, restore_faq_address),
    ]
