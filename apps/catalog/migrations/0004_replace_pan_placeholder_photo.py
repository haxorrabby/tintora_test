from django.db import migrations


PLACEHOLDER_URL = "/static/images/placeholders/harina-pan.svg"
PRODUCT_IMAGE = "catalog/products/2026/10/ha011_tk3IGho.jpg"
PRODUCT_SKU = "TIN-LAT-PAN-001"


def replace_pan_placeholder(apps, schema_editor):
    product_image = apps.get_model("catalog", "ProductImage")
    product_image.objects.using(schema_editor.connection.alias).filter(
        product__sku=PRODUCT_SKU,
        image="",
        image_url=PLACEHOLDER_URL,
    ).update(image=PRODUCT_IMAGE, image_url="")


def restore_pan_placeholder(apps, schema_editor):
    product_image = apps.get_model("catalog", "ProductImage")
    product_image.objects.using(schema_editor.connection.alias).filter(
        product__sku=PRODUCT_SKU,
        image=PRODUCT_IMAGE,
        image_url="",
    ).update(image="", image_url=PLACEHOLDER_URL)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0003_product_image_review_notes_and_more"),
    ]

    operations = [
        migrations.RunPython(replace_pan_placeholder, restore_pan_placeholder),
    ]
