import json
import re
import tempfile
import xml.etree.ElementTree as ElementTree
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings

from apps.blog.models import Article
from apps.catalog.models import BusinessArea, Category, Product


class CoreViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def test_healthz_endpoint(self):
        response = self.client.get("/healthz/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    def test_seed_data_sample_accounts_have_no_usable_password(self):
        call_command("seed_data", stdout=StringIO())
        users = get_user_model().objects.filter(
            email__in=["admin@tintora.es", "cliente@estudio-alcala.es"]
        )

        self.assertEqual(users.count(), 2)
        self.assertTrue(all(not user.has_usable_password() for user in users))

    def test_static_svg_assets_are_valid_xml(self):
        image_dir = settings.BASE_DIR / "static" / "images"
        for svg_path in image_dir.rglob("*.svg"):
            with self.subTest(svg=svg_path.relative_to(image_dir)):
                ElementTree.parse(svg_path)

    def test_public_catalog_photo_is_served_from_media(self):
        with tempfile.TemporaryDirectory() as media_root:
            photo = Path(media_root) / "catalog" / "products" / "sample.jpg"
            photo.parent.mkdir(parents=True)
            photo.write_bytes(b"sample product photo")

            with override_settings(MEDIA_ROOT=media_root, USE_S3=False):
                response = self.client.get("/media/catalog/products/sample.jpg")
                photo_content = b"".join(response.streaming_content)
                response.close()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(photo_content, b"sample product photo")

    def test_spanish_home_view(self):
        response = self.client.get("/es/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tintora")
        self.assertContains(response, "Tinta que deja huella")
        self.assertContains(response, "Impresión")
        self.assertContains(response, "Sublimación")
        self.assertContains(response, "Productos Latinos")
        self.assertContains(response, "Desarrollo Web")

    def test_english_home_view(self):
        response = self.client.get("/en/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tintora")

    def test_contact_page_shows_current_address_and_structured_location(self):
        response = self.client.get("/es/contacto/")
        address = "C. Núñez de Balboa, 30, Loc 1, 28902 Getafe, Madrid, Spain"

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, address)
        self.assertContains(response, f"taller en {address}")

        schema_address = response.context["organization_schema"]["@graph"][1]["address"]
        self.assertEqual(schema_address["streetAddress"], "C. Núñez de Balboa, 30, Loc 1")
        self.assertEqual(schema_address["postalCode"], "28902")
        self.assertEqual(schema_address["addressLocality"], "Getafe")
        self.assertEqual(schema_address["addressRegion"], "Madrid")
        self.assertEqual(schema_address["addressCountry"], "Spain")

    def test_homepage_shows_real_priced_new_arrivals(self):
        category = Category.objects.create(
            name="Novedades",
            slug="novedades-test",
            business_area=BusinessArea.IMPRESION,
        )
        Product.objects.create(
            category=category,
            business_area=BusinessArea.IMPRESION,
            name="Producto recién llegado",
            slug="producto-recien-llegado-test",
            sku="TIN-NEW-001",
            short_description="Producto nuevo de prueba",
            description="Descripción de prueba",
            base_price="8.50",
            stock=5,
        )
        response = self.client.get("/es/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Novedades de Tintora")
        self.assertContains(response, "Producto recién llegado")

    def test_styleguide_view(self):
        response = self.client.get("/es/styleguide/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tokens & Componentes Tintora")
        self.assertContains(response, "#E8392B")  # Vermilion
        self.assertContains(response, "#C9A96A")  # Gold

    def test_hidden_admin_url(self):
        # /admin/ should return 404
        response_standard_admin = self.client.get("/admin/")
        self.assertEqual(response_standard_admin.status_code, 404)

        # /gestion-tintora/ should return 302 redirect to login or 200
        admin_url = "/" + settings.ADMIN_URL_PATH.strip("/") + "/login/"
        response_hidden_admin = self.client.get(admin_url)
        self.assertIn(response_hidden_admin.status_code, [200, 302])

    @override_settings(DEBUG=False)
    def test_not_found_uses_branded_error_page(self):
        response = self.client.get("/es/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Esta página no se encuentra en el taller", status_code=404)

    def test_admin_language_switcher_translates_dashboard(self):
        user = get_user_model().objects.create_superuser(
            username="admin-language-test",
            email="admin-language-test@example.com",
            password="test-password-that-is-not-used",
        )
        self.client.force_login(user)
        admin_url = f"/{settings.ADMIN_URL_PATH.strip('/')}/"

        response = self.client.get(admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="language"')
        self.assertContains(response, "Resumen del taller y la tienda")

        response = self.client.post(
            "/i18n/setlang/",
            {"language": "en", "next": admin_url},
        )
        self.assertEqual(response.status_code, 302)

        response = self.client.get(admin_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workshop and store overview")
        self.assertContains(response, "English")
        self.assertNotContains(response, "Resumen del taller y la tienda")

    def test_sitemap_contains_resolvable_public_and_bilingual_urls(self):
        category = Category.objects.create(
            name="Categoría SEO",
            slug="categoria-seo-core-test",
            business_area=BusinessArea.IMPRESION,
        )
        product = Product.objects.create(
            category=category,
            business_area=BusinessArea.IMPRESION,
            name="Producto SEO",
            slug="producto-seo-core-test",
            sku="SEO-CORE-001",
            short_description="Producto para comprobar el sitemap.",
            description="Ficha publicada para validar las URL canónicas y sus alternates.",
            base_price="12.10",
        )
        article = Article.objects.create(
            title="Guía SEO de imprenta",
            slug="guia-seo-imprenta-core-test",
            excerpt="Una guía para publicar productos impresos en línea.",
            content="Contenido editorial de prueba.",
            status=Article.Status.PUBLISHED,
        )

        response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        root = ElementTree.fromstring(response.content)
        locations = {node.text for node in root.findall("{*}url/{*}loc")}
        self.assertIn(f"http://testserver/es/catalogo/producto/{product.slug}/", locations)
        self.assertIn(f"http://testserver/en/catalogo/producto/{product.slug}/", locations)
        self.assertIn(f"http://testserver/es/blog/{article.slug}/", locations)
        alternates = root.findall("{*}url/{*}link")
        self.assertTrue(any(link.attrib.get("hreflang") == "en" for link in alternates))

    def test_robots_points_to_site_root_sitemap(self):
        response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sitemap: http://testserver/sitemap.xml")
        self.assertContains(response, f"Disallow: /{settings.ADMIN_URL_PATH}")

    def test_public_pages_emit_hreflang_and_query_free_canonical(self):
        response = self.client.get("/es/?utm_source=phase8")
        content = response.content.decode()

        self.assertContains(response, 'hreflang="es"')
        self.assertContains(response, 'hreflang="en"')
        self.assertIn('<link rel="canonical" href="http://testserver/es/">', content)
        self.assertNotIn("utm_source", re.search(r'<link rel="canonical"[^>]+>', content).group(0))

    def test_product_and_article_render_structured_data(self):
        category = Category.objects.create(
            name="Desayuno SEO",
            slug="desayuno-seo-core-test",
            business_area=BusinessArea.LATINOS,
        )
        product = Product.objects.create(
            category=category,
            business_area=BusinessArea.LATINOS,
            name="Café SEO 250 g",
            slug="cafe-seo-core-test",
            sku="SEO-CORE-002",
            short_description="Café de origen para desayunos.",
            description="Café tostado de prueba.",
            base_price="8.50",
            stock=4,
        )
        article = Article.objects.create(
            title="Notas de impresión digital",
            slug="notas-impresion-digital-core-test",
            excerpt="Consejos para preparar artes finales.",
            content="Artículo publicado de prueba.",
            status=Article.Status.PUBLISHED,
        )

        product_response = self.client.get(product.get_absolute_url())
        article_response = self.client.get(article.get_absolute_url())
        product_json = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            product_response.content.decode(),
            re.DOTALL,
        )
        article_json = re.search(
            r'<script type="application/ld\+json">(.*?)</script>',
            article_response.content.decode(),
            re.DOTALL,
        )
        self.assertIsNotNone(product_json)
        self.assertIsNotNone(article_json)

        product_schemas = [json.loads(match) for match in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            product_response.content.decode(),
            re.DOTALL,
        )]
        article_schemas = [json.loads(match) for match in re.findall(
            r'<script type="application/ld\+json">(.*?)</script>',
            article_response.content.decode(),
            re.DOTALL,
        )]
        self.assertTrue(any(schema.get("@type") == "Product" for schema in product_schemas))
        self.assertTrue(any(schema.get("@type") == "BlogPosting" for schema in article_schemas))
