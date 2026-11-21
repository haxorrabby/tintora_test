"""
Tests for the LATIN PRODUCTS catalog (database-backed storefront).

Covers dataset integrity (counts, slugs, public-field stripping, prices,
stock, origin), all three routes, the absence of any WhatsApp *ordering*
flow (the support-only concierge button remains, which is allowed), the
online add-to-cart purchase path, URL filter state and the homepage preview.

Tests seed their own small catalog (categories + products at zero and real
prices) so they run against a fresh test database.
"""

import json
import re
from decimal import Decimal
from urllib.parse import unquote

from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Brand, BusinessArea, Category, Product, ProductImage

from .data import (
    PUBLIC_PRODUCT_FIELDS,
    get_catalog,
    preview_products,
    product_total,
    products_for_category,
    retail_size_from_name,
)

PAYLOAD_RE = re.compile(
    r'<script[^>]*id="latin-catalog-data"[^>]*>(?P<json>.*?)</script>',
    re.DOTALL,
)

# WhatsApp ordering phrases that must never appear on product/checkout pages.
_ORDERING_PHRASES = (
    "pedir por whatsapp",
    "hacer pedido por whatsapp",
    "pedido por whatsapp",
    "comprar por whatsapp",
)

_WHATSAPP_LINK_RE = re.compile(r"https://wa\.me/[^\s\"'<>]+")

# --------------------------------------------------------------------------- #
# Shared seed data                                                            #
# --------------------------------------------------------------------------- #

CATEGORY_DATA = [
    ("granos-y-legumbres", "Granos y Legumbres"),
    ("cafe-y-bebidas", "Café & Refrescos"),
    ("snacks-y-dulces", "Snacks & Dulces"),
    ("conservas-latinas", "Conservas Latinas"),
    ("especias-latinas", "Especias Latinas"),
    ("congelados-latinos", "Congelados"),
    ("pastas-y-salsas", "Pastas y Salsas"),
    ("productos-africanos", "Productos Africanos"),
]

# name, slug, sku, category slug, price, stock, brand, origin, weight_grams
PRODUCT_DATA = [
    ("Andis Kola 2 L", "andis-kola-2-l", "BE001", "cafe-y-bebidas", "2.10", 30, "", "", 0),
    ("América Kola 500 ml", "america-kola-500-ml", "BE002", "cafe-y-bebidas", "0", 25, "", "", 500),
    ("Pony Malta 355 ml", "pony-malta-355-ml", "PMT001", "cafe-y-bebidas", "1.95", 40, "Pony Malta", "Colombia", 355),
    ("Quinua Blanca 500 g", "quinua-blanca-500-g", "PLG020", "granos-y-legumbres", "4.50", 20, "", "Perú", 500),
    ("Harina P.A.N. 1 kg", "harina-pan-1-kg", "HA001", "granos-y-legumbres", "0", 25, "Oriental", "Venezuela", 1000),
    ("Maní Mondado 500 g", "mani-mondado-500-g", "PLG071", "snacks-y-dulces", "0", 25, "", "", 500),
    ("Ají Panca 100 g", "aji-panca-100-g", "ES022", "especias-latinas", "0", 25, "", "", 100),
    ("Dulce de Guayaba 500 g", "dulce-de-guayaba-500-g", "PO030", "conservas-latinas", "0", 25, "", "", 500),
    ("Yuca Congelada 1 kg", "yuca-congelada-1-kg", "DOP001", "congelados-latinos", "0", 25, "", "", 1000),
    ("Salsa de Ajo 425 ml", "salsa-de-ajo-425-ml", "PLL001", "pastas-y-salsas", "0", 25, "", "", 425),
    ("Gari Ghana 500 g", "gari-ghana-500-g", "MPH012", "productos-africanos", "0", 25, "", "", 500),
]


class SeededLatinCatalogMixin(TestCase):
    """Creates a small representative latinos catalog in the test database."""

    @classmethod
    def setUpTestData(cls):
        cls.categories = {}
        for order, (slug, name) in enumerate(CATEGORY_DATA):
            cls.categories[slug] = Category.objects.create(
                name=name,
                slug=slug,
                business_area=BusinessArea.LATINOS,
                description=f"Descripción editorial de {name}.",
                order=order,
                is_active=True,
            )
        cls.brands = {}
        for brand_name in ("Pony Malta", "Oriental"):
            cls.brands[brand_name] = Brand.objects.create(
                name=brand_name, slug=brand_name.lower().replace(" ", "-")
            )
        cls.products = []
        for item in PRODUCT_DATA:
            name, slug, sku, category_slug, price, stock, brand, origin, weight = item
            product = Product.objects.create(
                category=cls.categories[category_slug],
                business_area=BusinessArea.LATINOS,
                brand=cls.brands.get(brand),
                name=name,
                slug=slug,
                sku=sku,
                short_description=f"{name} — unidad individual.",
                description=f"{name}. Producto de despensa latina de prueba.",
                base_price=Decimal(price),
                origin_country=origin,
                weight_grams=weight,
                stock=stock,
                is_active=True,
            )
            ProductImage.objects.create(
                product=product,
                image_url="/static/images/brand/tintora-logo-mono.svg",
                alt_text=name,
                is_primary=True,
                order=0,
            )
            cls.products.append(product)
        cola = cls.products[1]
        cola.name = "América Kola"
        cola.variant_label = "500 ml"
        cola.save(update_fields=["name", "variant_label"])
        cls.cola_large = Product.objects.create(
            category=cola.category,
            business_area=BusinessArea.LATINOS,
            parent_product=cola,
            variant_label="2 l",
            name=cola.name,
            slug="america-kola-2-l",
            short_description=cola.short_description,
            description=cola.description,
            base_price=Decimal("3.25"),
            stock=8,
            weight_grams=2000,
            is_active=True,
        )


class LatinDatasetTestCase(SeededLatinCatalogMixin):
    """Public data-layer checks against the seeded catalog."""

    def test_catalog_comes_from_the_database(self):
        catalog = get_catalog()
        db_total = Product.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True, parent_product__isnull=True
        ).count()
        self.assertEqual(len(catalog["products"]), db_total)
        self.assertEqual(product_total(), db_total)
        self.assertGreater(db_total, 0)

    def test_categories_cover_all_products(self):
        catalog = get_catalog()
        counted = sum(c["count"] for c in catalog["categories"])
        self.assertEqual(counted, len(catalog["products"]))
        for category in catalog["categories"]:
            self.assertEqual(
                len(products_for_category(category["slug"])), category["count"]
            )

    def test_unique_slugs_and_required_fields(self):
        catalog = get_catalog()
        slugs = [p["slug"] for p in catalog["products"]]
        self.assertEqual(len(set(slugs)), len(slugs))
        for product in catalog["products"]:
            self.assertTrue(product["name"])
            self.assertTrue(product["category"])
            self.assertTrue(product["categorySlug"])
            self.assertGreaterEqual(product["price"], 0)
            self.assertGreaterEqual(product["stock"], 0)
            self.assertIsInstance(product["inStock"], bool)
            self.assertTrue(product["image_url"])

    def test_public_products_only_expose_public_fields(self):
        for product in get_catalog()["products"]:
            self.assertEqual(tuple(product.keys()), PUBLIC_PRODUCT_FIELDS)

    def test_no_wholesale_case_language_in_public_fields(self):
        for product in get_catalog()["products"]:
            self.assertNotIn("Caja", product["name"])
            self.assertNotIn("caja", product["retailSize"])

    def test_retail_size_is_the_individual_unit(self):
        self.assertEqual(retail_size_from_name("Andis Kola 2 L"), "2 l")
        self.assertEqual(retail_size_from_name("Quinua Blanca 500 g"), "500 g")
        self.assertEqual(retail_size_from_name("Sin Tamano"), "")

    def test_preview_spreads_across_categories(self):
        preview = preview_products(8)
        self.assertEqual(len(preview), 8)
        self.assertEqual(len({p["categorySlug"] for p in preview}), 8)

    def test_zero_price_products_are_still_visible(self):
        zero = [p for p in get_catalog()["products"] if p["price"] == 0]
        self.assertTrue(zero)  # imported products have no catalog price yet
        for product in zero:
            self.assertTrue(product["inStock"])

    def test_origin_and_brand_leak_intact(self):
        pony = next(
            p for p in get_catalog()["products"] if p["slug"] == "pony-malta-355-ml"
        )
        self.assertEqual(pony["originCountry"], "Colombia")
        self.assertEqual(pony["brand"], "Pony Malta")

    def test_grouped_variants_are_public_without_exposing_product_ids_or_skus(self):
        cola = next(p for p in get_catalog()["products"] if p["slug"] == "america-kola-500-ml")
        self.assertEqual(cola["name"], "América Kola")
        self.assertEqual(
            {(item["label"], item["price"], item["stock"]) for item in cola["variants"]},
            {("500 ml", 0.0, 25), ("2 l", 3.25, 8)},
        )
        self.assertTrue(all("sku" not in item and "id" not in item for item in cola["variants"]))

    def test_alpine_component_asset_present(self):
        from pathlib import Path

        from django.conf import settings

        self.assertTrue(
            (Path(settings.BASE_DIR) / "static" / "src" / "js" / "latin-catalog.js").is_file()
        )


class LatinCatalogViewsTestCase(SeededLatinCatalogMixin):
    """Route rendering, payload hygiene and site integration."""

    def _payload(self, response):
        match = PAYLOAD_RE.search(response.content.decode("utf-8"))
        self.assertIsNotNone(match, "latin-catalog-data payload missing from response")
        return json.loads(match.group("json"))

    @staticmethod
    def _assert_no_whatsapp_ordering(response):
        """The page must never offer WhatsApp as a way to buy/order.

        Support-only WhatsApp links (floating concierge button, contact page)
        are allowed; links whose prefilled message references the product/order
        are ordering flows and must be absent.
        """
        content = response.content.decode("utf-8").lower()
        for phrase in _ORDERING_PHRASES:
            assert phrase not in content, f"whatsapp ordering phrase found: {phrase}"
        for link in _WHATSAPP_LINK_RE.findall(response.content.decode("utf-8")):
            decoded = unquote(link).lower()
            assert "producto" not in decoded and "sku" not in decoded, link

    # ------------------------------------------------------------------ #
    # Index                                                              #
    # ------------------------------------------------------------------ #
    def test_index_view(self):
        response = self.client.get("/es/latin-products/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Productos Latinos")
        self.assertNotContains(response, "Catálogo 2022–2024")
        self.assertContains(response, "id=\"latin-catalog-root\"")
        self.assertContains(response, "x-cloak")

    def test_index_embeds_full_public_dataset(self):
        response = self.client.get("/es/latin-products/")
        payload = self._payload(response)
        db_total = Product.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True, parent_product__isnull=True
        ).count()
        self.assertEqual(len(payload["products"]), db_total)
        self.assertGreater(len(payload["categories"]), 0)
        for product in payload["products"]:
            self.assertEqual(tuple(product.keys()), PUBLIC_PRODUCT_FIELDS)

    def test_index_never_leaks_internal_fields(self):
        response = self.client.get("/es/latin-products/")
        content = response.content.decode("utf-8")
        self.assertNotIn("sourcePage", content)
        self.assertNotIn("xref", content)
        self.assertNotIn('"sku":', content)
        self.assertNotIn('"id":', content)

    def test_index_renders_every_product_card(self):
        response = self.client.get("/es/latin-products/")
        for product in get_catalog()["products"]:
            self.assertContains(response, product["slug"], msg_prefix=product["slug"])

    def test_index_filter_state_in_url_is_tolerated(self):
        response = self.client.get(
            "/es/latin-products/?category=congelados-latinos&search=arepa&brand=Oriental&sort=az&page=2"
        )
        self.assertEqual(response.status_code, 200)

    def test_index_available_in_english_locale(self):
        response = self.client.get("/en/latin-products/")
        self.assertEqual(response.status_code, 200)

    # ------------------------------------------------------------------ #
    # Category landing pages                                             #
    # ------------------------------------------------------------------ #
    def test_category_landing_view(self):
        category = Category.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True
        ).first()
        response = self.client.get(
            reverse("latin_products:entry", args=[category.slug])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, category.name)
        self.assertContains(response, f"{category.products.filter(is_active=True).count()} ")

    def test_category_page_renders_only_its_own_products(self):
        category = Category.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True
        ).first()
        response = self.client.get(
            reverse("latin_products:entry", args=[category.slug])
        )
        own = {p["slug"] for p in products_for_category(category.slug)}
        payload = self._payload(response)
        self.assertEqual({p["slug"] for p in payload["products"]}, own)

    def test_every_category_slug_resolves(self):
        for category in Category.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True
        ):
            url = reverse("latin_products:entry", args=[category.slug])
            self.assertTrue(url.endswith(f"/{category.slug}/"))
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200, category.slug)

    # ------------------------------------------------------------------ #
    # Product detail pages                                               #
    # ------------------------------------------------------------------ #
    def _detail_samples(self):
        products = get_catalog()["products"]
        return [products[0], products[len(products) // 2], products[-1]]

    def test_product_detail_view(self):
        for product in self._detail_samples():
            response = self.client.get(reverse("latin_products:entry", args=[product["slug"]]))
            self.assertEqual(response.status_code, 200, product["slug"])
            self.assertContains(response, product["name"])
            self.assertContains(response, product["category"])
            if product["retailSize"]:
                self.assertContains(response, product["retailSize"])
            self.assertRegex(
                response.content.decode("utf-8"),
                r'x-data="\{[\s\S]*unitPrice: Number\(',
            )

    def test_product_detail_offers_online_purchase(self):
        """Every product page offers the normal cart — never WhatsApp ordering."""
        for product in self._detail_samples():
            response = self.client.get(reverse("latin_products:entry", args=[product["slug"]]))
            add_url = reverse("cart:add", args=[product["slug"]])
            self.assertContains(response, add_url, msg_prefix=add_url)
            if not product["inStock"]:
                self.assertContains(response, "Agotado")
                self.assertContains(response, "disabled")
            elif product["price"] > 0:
                self.assertContains(response, "Añadir a la Cesta")
                self.assertNotContains(response, "disabled")
            else:
                self.assertContains(response, "Precio pendiente")
                self.assertContains(response, "disabled")
            self._assert_no_whatsapp_ordering(response)

    def test_product_detail_never_leaks_internal_fields(self):
        for product in self._detail_samples():
            response = self.client.get(reverse("latin_products:entry", args=[product["slug"]]))
            content = response.content.decode("utf-8")
            self.assertNotIn("sourcePage", content, product["slug"])
            self.assertNotIn("xref", content, product["slug"])
            self.assertNotIn('"sku":', content, product["slug"])

    def test_grouped_product_detail_selects_a_specific_variant_for_cart(self):
        response = self.client.get(
            reverse("latin_products:entry", args=["america-kola-500-ml"])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="variant_slug"')
        self.assertContains(response, 'value="america-kola-2-l"')
        self.assertContains(response, "2 l")

    def test_every_product_slug_resolves(self):
        for product in get_catalog()["products"]:
            url = reverse("latin_products:entry", args=[product["slug"]])
            self.assertTrue(url.endswith(f"/{product['slug']}/"))

    def test_unknown_slug_404(self):
        response = self.client.get("/es/latin-products/no-existe-ningun-producto/")
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------ #
    # Site integration                                                   #
    # ------------------------------------------------------------------ #
    def test_homepage_shows_latin_preview(self):
        response = self.client.get("/es/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sabores que te llevan a casa")
        self.assertContains(response, "Imagen no disponible")
        self.assertNotContains(response, 'src="/static/images/brand/tintora-logo-mono.svg"')
        preview = preview_products(8)
        for item in preview:
            self.assertContains(response, item["slug"], msg_prefix=item["slug"])

    def test_header_mega_menu_links_to_real_categories(self):
        response = self.client.get("/es/")
        for category in Category.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True
        )[:5]:
            self.assertContains(response, f"/es/latin-products/{category.slug}/")

    def test_footer_links_to_catalog(self):
        response = self.client.get("/es/")
        self.assertContains(response, "/es/latin-products/")

    def test_sitemap_includes_latin_pages(self):
        response = self.client.get("/sitemap.xml")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("/latin-products/", content)

    # ------------------------------------------------------------------ #
    # Purchase flow                                                      #
    # ------------------------------------------------------------------ #
    def test_imported_product_can_be_added_to_the_online_cart(self):
        """An imported catalog product can be purchased through the normal cart."""
        product = (
            Product.objects.filter(business_area=BusinessArea.LATINOS, is_active=True, parent_product__isnull=True)
            .filter(base_price__gt=0)
            .first()
        )
        self.assertIsNotNone(product, "expected at least one imported product")
        response = self.client.post(
            reverse("cart:add", args=[product.slug]), {"quantity": 1}
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("cart:detail"))

    def test_imported_product_full_checkout_to_confirmation(self):
        """Add → cart → checkout → order confirmation works for an imported product."""
        from apps.cart.models import ShippingMethod, ShippingZone
        from apps.orders.models import Order

        product = (
            Product.objects.filter(business_area=BusinessArea.LATINOS, is_active=True, parent_product__isnull=True)
            .filter(base_price__gt=0)
            .first()
        )
        self.assertIsNotNone(product, "expected at least one imported product")

        zone, _ = ShippingZone.objects.get_or_create(
            code=ShippingZone.ZoneCode.PENINSULA,
            defaults={"name": "Zona Test", "is_active": True},
        )
        method, _ = ShippingMethod.objects.get_or_create(
            zone=zone,
            name="Envío Test",
            defaults={
                "courier": ShippingMethod.Courier.SEUR,
                "base_rate": "3.90",
                "estimated_days": "24/48h",
                "is_active": True,
            },
        )

        # 1. Add to cart from the latin product page
        response = self.client.post(
            reverse("cart:add", args=[product.slug]), {"quantity": 2}, follow=True
        )
        self.assertEqual(response.status_code, 200)

        # 2. View cart
        response = self.client.get(reverse("cart:detail"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, product.name)

        # 3. Checkout page renders with online payment options (no WhatsApp)
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="bizum"')
        self.assertContains(response, 'value="transfer"')
        self._assert_no_whatsapp_ordering(response)

        # 4. Process checkout → order confirmation
        before = Order.objects.count()
        response = self.client.post(
            reverse("orders:checkout_process"),
            {
                "customer_type": "individual",
                "first_name": "María",
                "last_name": "García Rodríguez",
                "email": "maria@test.es",
                "phone": "+34 612 345 678",
                "nif_cif": "12345678Z",
                "company_name": "",
                "shipping_address_line1": "Calle Gran Vía 1",
                "shipping_address_line2": "3º A",
                "shipping_postal_code": "28013",
                "shipping_city": "Madrid",
                "shipping_province": "Madrid",
                "shipping_method_id": str(method.id),
                "payment_method": "transfer",
                "customer_notes": "",
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), before + 1)
        order = Order.objects.order_by("-created_at").first()
        self.assertEqual(order.email, "maria@test.es")
        self.assertEqual(order.payment_method, "transfer")
        self.assertEqual(order.items.first().product_id, product.id)
        # 5. Confirmation page renders for the new order
        response = self.client.get(
            reverse("orders:confirmation", args=[order.order_number])
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, order.order_number)