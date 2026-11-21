from decimal import Decimal
from io import StringIO
import json

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from .models import BusinessArea, Category, Product, ProductImage, QuantityTierPrice


class CatalogModelTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Tarjetas de Visita",
            slug="tarjetas-de-visita-test",
            business_area=BusinessArea.IMPRESION,
        )
        self.product = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            name="Tarjetas Premium Test",
            slug="tarjetas-premium-test",
            sku="TIN-TEST-001",
            short_description="Tarjetas de prueba",
            description="Descripción completa",
            base_price=Decimal("29.00"),
            iva_percentage=Decimal("21.0"),
            is_configurable=True,
        )

    def test_iva_calculation(self):
        # 29.00 / 1.21 = 23.97
        self.assertEqual(self.product.price_without_iva, Decimal("23.97"))
        # 29.00 - 23.97 = 5.03
        self.assertEqual(self.product.iva_amount, Decimal("5.03"))

    def test_quantity_tier(self):
        tier = QuantityTierPrice.objects.create(
            product=self.product,
            min_quantity=500,
            unit_price=Decimal("0.1080"),
            total_price=Decimal("54.00"),
        )
        self.assertEqual(tier.min_quantity, 500)
        self.assertEqual(self.product.quantity_tiers.count(), 1)

    def test_sku_is_optional_for_new_products(self):
        product = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            name="Producto sin referencia",
            slug="producto-sin-referencia",
            short_description="Producto sin SKU",
            description="Descripción",
            base_price=Decimal("1.00"),
        )
        self.assertIsNone(product.sku)

    def test_size_variants_keep_independent_prices_and_stock(self):
        variant = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            parent_product=self.product,
            variant_label="500 g",
            name=self.product.name,
            slug="tarjetas-premium-test-500-g",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("5.00"),
            stock=3,
        )
        self.assertEqual(
            {(item.variant_label, item.base_price, item.stock) for item in self.product.active_variants},
            {("", Decimal("29.00"), 100), ("500 g", Decimal("5.00"), 3)},
        )
        self.assertEqual(variant.display_name, self.product.name)

    def test_verified_product_images_require_source_and_permission(self):
        image = ProductImage(
            product=self.product,
            image_url="https://example.com/product.jpg",
            verification_status=ProductImage.VerificationStatus.VERIFIED,
        )
        with self.assertRaises(ValidationError):
            image.full_clean()

        image.source_url = "https://example.com/product"
        image.license_note = "Manufacturer permission"
        image.full_clean()


class CatalogViewsTestCase(TestCase):
    def setUp(self):
        self.category_print = Category.objects.create(
            name="Tarjetas de Visita",
            slug="tarjetas-de-visita",
            business_area=BusinessArea.IMPRESION,
            description="Tarjetas corporativas de máxima calidad en Madrid",
        )
        self.category_latin = Category.objects.create(
            name="Harinas & Granos",
            slug="harinas-y-granos",
            business_area=BusinessArea.LATINOS,
            description="Harina PAN y granos de importación",
        )

        self.prod_print = Product.objects.create(
            category=self.category_print,
            business_area=BusinessArea.IMPRESION,
            name="Tarjetas Letterpress Artesanales",
            slug="tarjetas-letterpress",
            sku="TIN-TEST-PRINT-1",
            short_description="Tarjetas con relieve en papel de algodón",
            description="Impresas artesanalmente en nuestro taller de Atocha.",
            base_price=Decimal("45.00"),
            iva_percentage=Decimal("21.0"),
            is_active=True,
            is_featured=True,
            is_configurable=True,
            allows_file_upload=True,
            allows_proof=True,
        )

        self.prod_latin = Product.objects.create(
            category=self.category_latin,
            business_area=BusinessArea.LATINOS,
            name="Harina PAN Amarilla 1kg",
            slug="harina-pan-amarilla-1kg",
            sku="TIN-TEST-LAT-1",
            short_description="Harina de maíz precocida amarilla",
            description="Ideal para arepas, empanadas y hallacas.",
            base_price=Decimal("2.95"),
            iva_percentage=Decimal("21.0"),
            is_active=True,
            is_featured=False,
            is_configurable=False,
            origin_country="Colombia",
            weight_grams=1000,
            stock=50,
        )

    def test_catalog_index_view(self):
        response = self.client.get("/es/catalogo/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catálogo General")
        self.assertContains(response, "Tarjetas Letterpress Artesanales")
        self.assertContains(response, "Harina PAN Amarilla 1kg")

    def test_catalog_index_filter_by_area(self):
        response = self.client.get("/es/catalogo/?area=impresion")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarjetas Letterpress Artesanales")
        self.assertNotContains(response, "Harina PAN Amarilla 1kg")

    def test_category_detail_view(self):
        response = self.client.get("/es/catalogo/categoria/tarjetas-de-visita/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarjetas de Visita")
        self.assertContains(response, "Tarjetas Letterpress Artesanales")

    def test_category_detail_htmx_partial(self):
        response = self.client.get(
            "/es/catalogo/categoria/tarjetas-de-visita/?partial=product_list&sort=price_desc",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarjetas Letterpress Artesanales")
        # Ensure base layout is NOT rendered in partial
        self.assertNotContains(response, "<html")

    def test_category_search_and_stock_filter(self):
        response = self.client.get(
            "/es/catalogo/categoria/tarjetas-de-visita/?q=letterpress&in_stock=1"
        )
        self.assertContains(response, "Tarjetas Letterpress Artesanales")

        self.prod_print.stock = 0
        self.prod_print.save(update_fields=["stock"])
        response = self.client.get(
            "/es/catalogo/categoria/tarjetas-de-visita/?q=letterpress&in_stock=1"
        )
        self.assertNotContains(response, "Tarjetas Letterpress Artesanales")

    def test_print_product_detail_view(self):
        response = self.client.get("/es/catalogo/producto/tarjetas-letterpress/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tarjetas Letterpress Artesanales")
        self.assertContains(response, "Preparación de Archivo & Preimpresión")
        self.assertContains(response, "Pide una prueba previa física")

    def test_unpriced_product_is_not_shown_as_free_or_offered_for_purchase(self):
        product = Product.objects.create(
            category=self.category_print,
            business_area=BusinessArea.IMPRESION,
            name="Producto sin precio",
            slug="producto-sin-precio",
            sku="TIN-TEST-UNPRICED",
            short_description="Precio pendiente",
            description="Descripción de prueba",
            base_price=Decimal("0.00"),
            stock=10,
        )
        response = self.client.get(f"/es/catalogo/producto/{product.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Precio pendiente")
        self.assertContains(response, "disabled")
        self.assertNotContains(response, "0.00€")
        self.assertNotContains(response, '"price": "0.00"')

    def test_latin_product_detail_view(self):
        image = ProductImage.objects.create(
            product=self.prod_latin,
            image_url="/media/catalog/products/test-pan.jpg",
            is_primary=True,
        )
        response = self.client.get("/es/catalogo/producto/harina-pan-amarilla-1kg/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Harina PAN Amarilla 1kg")
        self.assertContains(response, "Despensa Latina")
        self.assertContains(response, "Colombia")
        self.assertContains(response, "1000 g")
        self.assertContains(response, "selectedImage:")
        self.assertContains(response, image.image_url)

    def test_grouped_products_render_one_card_with_variant_selector(self):
        variant = Product.objects.create(
            category=self.category_latin,
            business_area=BusinessArea.LATINOS,
            parent_product=self.prod_latin,
            variant_label="500 g",
            name=self.prod_latin.name,
            slug="harina-pan-500-g",
            short_description=self.prod_latin.short_description,
            description=self.prod_latin.description,
            base_price=Decimal("1.75"),
            stock=4,
        )
        response = self.client.get(f"/es/catalogo/categoria/{self.category_latin.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["products"]), [self.prod_latin])
        self.assertContains(response, 'name="variant_slug"')
        self.assertContains(response, variant.slug)

        detail = self.client.get(f"/es/catalogo/producto/{self.prod_latin.slug}/")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "Tamaño / presentación")
        self.assertContains(detail, variant.variant_label)
        self.assertContains(detail, "selectedImage = option.dataset.image")

    def test_instant_search_htmx_partial(self):
        response = self.client.get(
            "/es/catalogo/buscar/?q=harina",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Harina PAN Amarilla 1kg")
        self.assertNotContains(response, "<html")

    def test_instant_search_page(self):
        response = self.client.get("/es/catalogo/buscar/?q=letterpress")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resultados de Búsqueda")
        self.assertContains(response, "Tarjetas Letterpress Artesanales")


class LoadPublicDemoCatalogCommandTestCase(TestCase):
    def test_public_demo_catalog_command_imports_once(self):
        call_command("load_public_demo_catalog", stdout=StringIO())
        imported_count = Product.objects.count()
        self.assertGreater(imported_count, 0)
        self.assertTrue(Product.objects.filter(sku="TIN-LAT-PAN-001").exists())

        call_command("load_public_demo_catalog", stdout=StringIO())

        self.assertEqual(Product.objects.count(), imported_count)


class GroupProductVariantsCommandTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Arroz",
            slug="arroz-variants",
            business_area=BusinessArea.LATINOS,
        )
        self.small = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.LATINOS,
            name="Arroz Basmati 500 g",
            slug="arroz-basmati-500-g",
            sku="RICE-500",
            short_description="Arroz",
            description="Arroz basmati",
            base_price=Decimal("2.50"),
            stock=11,
        )
        self.large = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.LATINOS,
            name="Arroz Basmati 1 kg",
            slug="arroz-basmati-1-kg",
            sku="RICE-1KG",
            short_description="Arroz",
            description="Arroz basmati",
            base_price=Decimal("4.25"),
            stock=7,
        )

    def test_dry_run_does_not_change_product_records(self):
        output = StringIO()
        call_command("group_product_variants", stdout=output, stderr=StringIO())
        report = json.loads(output.getvalue())
        self.assertEqual(report["candidate_groups"], 1)
        self.assertEqual(report["product_records"], 2)
        self.small.refresh_from_db()
        self.large.refresh_from_db()
        self.assertIsNone(self.small.parent_product_id)
        self.assertIsNone(self.large.parent_product_id)

    def test_apply_preserves_records_prices_stock_and_is_idempotent(self):
        output = StringIO()
        call_command("group_product_variants", "--apply", stdout=output, stderr=StringIO())
        self.small.refresh_from_db()
        self.large.refresh_from_db()
        self.assertEqual(self.small.name, "Arroz Basmati")
        self.assertEqual(self.small.variant_label, "500 g")
        self.assertEqual(self.large.parent_product_id, self.small.pk)
        self.assertEqual((self.small.base_price, self.small.stock), (Decimal("2.50"), 11))
        self.assertEqual((self.large.base_price, self.large.stock), (Decimal("4.25"), 7))
        self.assertEqual(self.large.slug, "arroz-basmati-1-kg")

        output = StringIO()
        call_command("group_product_variants", stdout=output, stderr=StringIO())
        self.assertEqual(json.loads(output.getvalue())["candidate_groups"], 0)

def _span(text, font="RobotoCondensed-Bold", size=8.0, page=1, bbox=(0, 0, 10, 10)):
    return {"text": text, "font": font, "size": size, "page": page, "bbox": bbox}


def _pdf_with_asymmetric_photo():
    """A tiny PDF whose single photo has a unique appearance in all 8 orientations.

    The asymmetric blocks, chiral diagonal and corner marker make every dihedral
    transform distinguishable, and ``page.insert_image`` draws it through a
    placement that shows the samples exactly as stored.
    """
    import pymupdf

    doc = pymupdf.open()
    page = doc.new_page(width=300, height=400)
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 60, 120))
    pixmap.clear_with(0)
    for y in range(120):
        for x in range(60):
            if x < 30 and y < 40:
                color = (220, 40, 40)
            elif x >= 30 and y < 80:
                color = (40, 200, 60)
            elif x < 20 and y >= 80:
                color = (30, 60, 220)
            else:
                color = (235, 235, 235)
            if abs(x * 2 - y) < 2:  # diagonal keeps the pattern chiral
                color = (10, 10, 10)
            if 4 <= x < 10 and 4 <= y < 10:  # corner marker kills symmetry
                color = (255, 255, 0)
            pixmap.set_pixel(x, y, color)
    bbox = (20, 30, 140, 270)
    xref = page.insert_image(pymupdf.Rect(*bbox), pixmap=pixmap)
    return doc, page, xref, bbox


def _pdf_with_mirrored_photo():
    """Same photo, but drawn through a *mirroring* placement — the América case.

    The América Foods catalog draws most of its photos through a vertically
    negated scale, so the samples PyMuPDF hands back are upside-down versions
    of what the page shows. This rebuilds that situation on a one-image page
    by writing the placement matrix by hand.
    """
    doc, page, xref, bbox = _pdf_with_asymmetric_photo()
    name = page.get_images()[0][7]  # resource name of the inserted image
    if not name.startswith("/"):
        name = "/" + name
    x0, y0, x1, y1 = bbox
    content = f"q {x1 - x0} 0 0 {-(y1 - y0)} {x0} {y1} cm {name} Do Q".encode()
    stream_xref = doc.get_new_xref()
    doc.update_object(stream_xref, "<< >>")
    doc.update_stream(stream_xref, content, compress=False)
    doc.xref_set_key(page.xref, "Contents", f"{stream_xref} 0 R")
    # the mirrored placement lands the photo on a different part of the page
    placed = page.get_image_bbox(page.get_images(full=True)[0])
    return doc, page, xref, (placed.x0, placed.y0, placed.x1, placed.y1)


class WholesaleImportHelpersTestCase(TestCase):
    """Pure parser/normalisation helpers — no PDFs, no DB writes."""

    def test_parse_america_name_with_two_variants(self):
        from .wholesale_import import parse_america_spans

        spans = [
            _span("BEBIDAS REFRESCANTES •", "RobotoCondensed-Bold", 12.0),
            _span("AMÉRICA KOLA", "RobotoCondensed-Bold", 8.0),
            _span("BE001 • 2 L • Caja 6 Uds.", "RobotoCondensed-Regular", 7.0),
            _span("BE002 • 500 ml • Caja 12 Uds.", "RobotoCondensed-Regular", 7.0),
        ]
        entries = parse_america_spans(spans)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["code"], "BE001")
        self.assertEqual(entries[0]["name"], "AMÉRICA KOLA")
        self.assertEqual(entries[0]["size"], "2 L")
        self.assertEqual(entries[0]["case_qty"], "6")
        self.assertEqual(entries[0]["section"], "BEBIDAS REFRESCANTES")
        self.assertEqual(entries[1]["code"], "BE002")

    def test_parse_america_unit_reference(self):
        from .wholesale_import import parse_america_spans

        spans = [
            _span("HARINA DE TRIGO", "RobotoCondensed-Bold", 8.0),
            _span("HA006 • 1 Kg • UNIDAD", "RobotoCondensed-Regular", 7.0),
        ]
        entries = parse_america_spans(spans)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["case_qty"], "1")

    def test_parse_latinoandina_triple_and_bare_size(self):
        from .wholesale_import import parse_latinoandina_spans

        spans = [
            _span("Gandul Verde", "Calibri-Bold", 11.0),
            _span("Cod: PLL000", "Calibri", 11.0),
            _span("425ml x 24", "Calibri", 11.0),
            _span("Maíz Mote Primera", "Calibri-Bold", 11.0),
            _span("Cod: GRA000", "Calibri", 11.0),
            _span("25kg", "Calibri", 11.0),
        ]
        entries = parse_latinoandina_spans(spans)
        self.assertEqual(len(entries), 2)
        self.assertEqual((entries[0]["code"], entries[0]["size"], entries[0]["case_qty"]), ("PLL000", "425ml", "24"))
        self.assertEqual((entries[1]["code"], entries[1]["size"], entries[1]["case_qty"]), ("GRA000", "25kg", "1"))

    def test_normalize_size_and_weight(self):
        from .wholesale_import import normalize_size_display, weight_grams_from_size

        self.assertEqual(normalize_size_display("425ml"), "425 ml")
        self.assertEqual(normalize_size_display("3Kg"), "3 kg")
        self.assertEqual(normalize_size_display("500 gr"), "500 g")
        self.assertEqual(weight_grams_from_size("1 kg"), 1000)
        self.assertEqual(weight_grams_from_size("500 g"), 500)
        self.assertEqual(weight_grams_from_size("2 L"), 0)

    def test_dedupe_is_idempotent(self):
        from .wholesale_import import dedupe_entries

        batch = [
            {"code": "BE001", "name": "América Kola", "brand": "", "size": "2 L"},
            {"code": "BE001", "name": "América Kola", "brand": "", "size": "2 L"},
            {"code": "BE002", "name": "América Kola", "brand": "", "size": "500 ml"},
        ]
        new, skipped = dedupe_entries(batch)
        self.assertEqual(len(new), 2)
        self.assertEqual(len(skipped), 1)

    def test_title_name_consistency(self):
        from .wholesale_import import title_name

        self.assertEqual(title_name("AMÉRICA KOLA"), "América Kola")
        self.assertEqual(title_name("ANDIS KOLA"), "Andis Kola")
        self.assertEqual(title_name("HARINA P.A.N."), "Harina P.A.N.")
        self.assertEqual(title_name("CAFÉ PAN"), "Café PAN")

    def test_origin_statement_and_brand_are_explicit_only(self):
        from .wholesale_import import brand_for_name, origin_from_statement

        # The only origin statement in the catalogs (América, display font).
        self.assertEqual(origin_from_statement("Fabricada en Colombia desde 1953"), "Colombia")
        self.assertEqual(origin_from_statement("BE001 • 2 L • Caja 6 Uds."), "")
        # Brands only when the catalog's MARCAS DESTACADAS name appears.
        self.assertEqual(brand_for_name("SALSA CHINA ORIENTAL"), "Oriental")
        self.assertEqual(brand_for_name("LECHE DE COCO TESORO NATURAL"), "Tesoro Natural")
        self.assertEqual(brand_for_name("PONY MALTA"), "Pony Malta")
        self.assertEqual(brand_for_name("AMÉRICA KOLA"), "")

    def test_pack_formats_parse_the_individual_unit(self):
        from .wholesale_import import parse_latinoandina_spans

        def _latino(name, lines):
            spans = [_span(name, "Calibri-Bold", 11.0)]
            spans += [_span(line, "Calibri", 11.0) for line in lines]
            return parse_latinoandina_spans(spans)

        cases = [
            (["Cod: T1", "2 x 160g x 12"], ("T1", "160g", "12")),
            (["Cod: T2", "5g x 50 Unid. x 24"], ("T2", "5g", "24")),
            (["Cod: T3", "24 Unid x 17g x 15"], ("T3", "17g", "15")),
            (["Cod: T4", "2 Unid. x 12"], ("T4", "2 uds.", "12")),
            (["Cod: T5", "2 unid. (260g) x 5"], ("T5", "260g", "5")),
            (["Cod: T6", "5kg x 300-500g 1"], ("T6", "5kg", "1")),
            (["Cod: T7", "12 Unid. 100g x 40"], ("T7", "100g", "40")),
            (["Cod: T8", "50g x 12 Displ. x 12"], ("T8", "50g", "12")),
        ]
        for lines, expected in cases:
            entries = _latino("Test Product", lines)
            self.assertEqual(len(entries), 1, lines)
            self.assertEqual(
                (entries[0]["code"], entries[0]["size"], entries[0]["case_qty"]),
                expected,
                lines,
            )

    def test_hyphenated_codes_and_imperial_units(self):
        from .wholesale_import import parse_latinoandina_spans, weight_grams_from_size

        spans = [
            _span("Mocochinchi", "Calibri-Bold", 11.0),
            _span("Cod: PLG077-1", "Calibri", 11.0),
            _span("250g x 30", "Calibri", 11.0),
        ]
        entries = parse_latinoandina_spans(spans)
        self.assertEqual(entries[0]["code"], "PLG077-1")
        self.assertEqual(weight_grams_from_size("2 lb"), 907)
        self.assertEqual(weight_grams_from_size("8 oz"), 227)

    def test_country_flags_never_guess(self):
        from apps.core.templatetags.core_tags import country_flags

        self.assertEqual(country_flags(""), [])
        self.assertEqual(country_flags("Atlántida"), [])
        flags = country_flags("Venezuela / Colombia")
        self.assertEqual([f["code"] for f in flags], ["VE", "CO"])
        self.assertEqual(country_flags("Colombia")[0]["flag"], "🇨🇴")

    def test_match_images_prefers_overlap_over_exact_containment(self):
        from .wholesale_import import match_images_to_names

        # Name sits just below its photo (1 pt gap) — exact containment fails,
        # overlap/gap scoring still matches the correct image.
        photos = [(0, 0, 100, 100), (120, 0, 220, 100)]
        names = [(10, 101, 90, 120), (130, 5, 210, 20)]
        order = match_images_to_names(names, photos)
        # name 0 (y101-120) -> photo 0 (gap 1 pt); name 1 overlaps photo 1.
        self.assertEqual(order, {0: 0, 1: 1})

    def test_match_images_never_uses_a_photo_too_far_away(self):
        from .wholesale_import import match_images_to_names

        photos = [(0, 0, 100, 80)]
        names = [(10, 200, 90, 220)]  # gap 120 pt > 45 -> no match
        self.assertEqual(match_images_to_names(names, photos), {})

    def test_column_bounds_for_names(self):
        from .wholesale_import import column_bounds_for_names

        names = [
            (70, 0, 130, 20),   # col A
            (200, 0, 260, 20),  # col B
            (330, 0, 390, 20),  # col C
            (130, 100, 150, 120),  # edge name snapped to col B
        ]
        bounds = column_bounds_for_names(names, 600.0)
        self.assertEqual(len(bounds), 4)
        # The staggered name (centre 140) merges into col A; col B then spans
        # from the A/B midpoint (175) to the B/C midpoint (295).
        self.assertAlmostEqual(bounds[1][0], 175.0, places=1)
        self.assertAlmostEqual(bounds[1][1], 295.0, places=1)
        self.assertAlmostEqual(bounds[0][1], 175.0, places=1)
        self.assertAlmostEqual(bounds[2][0], 295.0, places=1)


class EmbeddedImageOrientationTestCase(TestCase):
    """The extracted photo must look exactly like the catalog page draws it."""

    def test_orientation_from_matrix_reads_the_standard_flip(self):
        from .wholesale_import import orientation_from_matrix

        # The plain [w 0 0 -h x y] placement: samples are drawn mirrored.
        self.assertEqual(orientation_from_matrix((60, 0, 0, -113, 10, 200)), "flip_v")
        # A mirrored placement that also rotates by a quarter turn.
        self.assertEqual(orientation_from_matrix((0, -134, -80, 0, 50, 300)), "transverse")
        # Straight half-turn, no mirroring.
        self.assertEqual(orientation_from_matrix((-60, 0, 0, -113, 10, 200)), "r180")
        # Columns travelling down and rows travelling right: upright, no fix.
        self.assertEqual(orientation_from_matrix((60, 0, 0, 113, 10, 200)), "identity")

    def test_every_orientation_has_a_self_consistent_inverse(self):
        from .wholesale_import import _INVERSE_ORIENTATION, _iter_orientations
        from PIL import Image

        image = Image.new("RGB", (12, 20), "white")
        for name, candidate in _iter_orientations(image):
            inverse = _INVERSE_ORIENTATION[name]
            back = candidate
            for other, transformed in _iter_orientations(candidate):
                if other == inverse:
                    back = transformed
            self.assertEqual(back.tobytes(), image.tobytes(), name)

    def test_oriented_jpeg_matches_the_rendered_page(self):
        """End-to-end: extract from a PDF, compare against the page render."""
        import io

        import pymupdf
        from PIL import Image

        from .wholesale_import import oriented_image_jpeg, orientation_from_pixels

        _doc, page, xref, bbox = _pdf_with_asymmetric_photo()
        data = oriented_image_jpeg(page, xref, bbox)
        self.assertIsNotNone(data)
        extracted = Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(extracted.getexif().get(0x0112, 1), 1)  # no EXIF flip

        rendered = page.get_pixmap(
            clip=pymupdf.Rect(*bbox), dpi=72, colorspace=pymupdf.csRGB
        )
        drawn = Image.open(io.BytesIO(rendered.tobytes("png"))).convert("RGB")
        op, confident = orientation_from_pixels(extracted, drawn)
        self.assertEqual(op, "identity")
        self.assertTrue(confident, "extracted photo must match the drawn photo")

    def test_mirrored_photo_is_extracted_upright(self):
        """Root cause fixed: a mirrored placement still yields an upright JPEG."""
        import io

        import pymupdf
        from PIL import Image

        from .wholesale_import import oriented_image_jpeg, orientation_from_pixels

        _doc, page, xref, bbox = _pdf_with_mirrored_photo()
        data = oriented_image_jpeg(page, xref, bbox)
        self.assertIsNotNone(data)
        extracted = Image.open(io.BytesIO(data)).convert("RGB")
        self.assertEqual(extracted.getexif().get(0x0112, 1), 1)  # no EXIF flip

        rendered = page.get_pixmap(
            clip=pymupdf.Rect(*bbox), dpi=72, colorspace=pymupdf.csRGB
        )
        drawn = Image.open(io.BytesIO(rendered.tobytes("png"))).convert("RGB")
        op, confident = orientation_from_pixels(extracted, drawn)
        self.assertEqual(op, "identity")
        self.assertTrue(confident, "extracted photo must match the drawn photo")

        # the raw samples really are mirrored, so the fix does change pixels
        raw = pymupdf.Pixmap(page.parent, xref)
        if raw.n - raw.alpha > 3:
            raw = pymupdf.Pixmap(pymupdf.csRGB, raw)
        raw_image = Image.open(io.BytesIO(raw.tobytes("png"))).convert("RGB")
        raw_op, _ = orientation_from_pixels(raw_image, drawn)
        self.assertNotEqual(raw_op, "identity")

    def test_repair_pass_is_idempotent(self):
        """A file holding the raw samples is flagged; the corrected one is not."""
        import io
        import tempfile
        from pathlib import Path

        import pymupdf
        from PIL import Image

        from .wholesale_import import oriented_image_jpeg, orientation_status

        doc, page, xref, bbox = _pdf_with_mirrored_photo()
        raw = pymupdf.Pixmap(page.parent, xref)
        if raw.n - raw.alpha > 3:
            raw = pymupdf.Pixmap(pymupdf.csRGB, raw)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "photo.jpg"
            # exactly what the pre-fix extractor wrote: the raw samples
            Image.open(io.BytesIO(raw.tobytes("png"))).convert("RGB").save(
                path, format="JPEG"
            )
            raw_status = orientation_status(path, page, xref, bbox)

            path.write_bytes(oriented_image_jpeg(page, xref, bbox))
            fixed_status = orientation_status(path, page, xref, bbox)

        # The photo is drawn mirrored, so raw samples must be reported stale…
        self.assertEqual(raw_status, "stale")
        # …and the corrected file must never be touched again.
        self.assertEqual(fixed_status, "correct")

    def test_a_correct_file_is_reported_as_drawn_as_stored(self):
        """Nothing is flagged when the catalog draws the samples as they are."""
        import io
        import tempfile
        from pathlib import Path

        import pymupdf
        from PIL import Image

        from .wholesale_import import orientation_status

        doc, page, xref, bbox = _pdf_with_asymmetric_photo()
        raw = pymupdf.Pixmap(page.parent, xref)
        if raw.n - raw.alpha > 3:
            raw = pymupdf.Pixmap(pymupdf.csRGB, raw)

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "photo.jpg"
            Image.open(io.BytesIO(raw.tobytes("png"))).convert("RGB").save(
                path, format="JPEG"
            )
            self.assertEqual(orientation_status(path, page, xref, bbox), "drawn-as-stored")
