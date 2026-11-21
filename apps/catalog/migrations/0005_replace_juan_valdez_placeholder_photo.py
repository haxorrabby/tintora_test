from django.db import migrations


PLACEHOLDER_URL = "/static/images/placeholders/cafe-colombia.svg"
PRODUCT_IMAGE_URL = "/static/img/latin-products/juan.jpg"
PRODUCT_SKU = "TIN-LAT-CAF-002"


def replace_cafe_placeholder(apps, schema_editor):
    product_image = apps.get_model("catalog", "ProductImage")
    product_image.objects.using(schema_editor.connection.alias).filter(
        product__sku=PRODUCT_SKU,
        image="",
        image_url=PLACEHOLDER_URL,
    ).update(image_url=PRODUCT_IMAGE_URL)


def restore_cafe_placeholder(apps, schema_editor):
    product_image = apps.get_model("catalog", "ProductImage")
    product_image.objects.using(schema_editor.connection.alias).filter(
        product__sku=PRODUCT_SKU,
        image="",
        image_url=PRODUCT_IMAGE_URL,
    ).update(image_url=PLACEHOLDER_URL)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0004_replace_pan_placeholder_photo"),
    ]

    operations = [
        migrations.RunPython(replace_cafe_placeholder, restore_cafe_placeholder),
    ]
