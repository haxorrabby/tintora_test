"""Import the two supplied wholesale PDF catalogs as individual retail units.

Distributor catalogs list case formats (``Caja 24 Uds.``) with **no retail
prices**. Each distributor code becomes one active ``Product`` with its
individual size preserved (``weight_grams`` + display name), ``base_price=0``
and a operational default stock — the admin sets the real PVP and adjusts
stock in Django Admin. Origins are only set when the catalog states them
explicitly; images are attached only when a product photo can be
positionally matched on the catalog page.

Idempotent: re-running skips codes (``sku``) and (name, size) pairs that
already exist. Products imported by a previous run are updated in place
(category, size, stock, activation, description) while admin-set prices
(``base_price > 0``) and slugs are always preserved.

Example::

    python manage.py import_wholesale_catalogs --dry-run
    python manage.py import_wholesale_catalogs
    python manage.py import_wholesale_catalogs --skip-images --report
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.catalog.models import Brand, BusinessArea, Category, Product
from apps.catalog.wholesale_import import (
    column_bounds_for_names,
    dedupe_entries,
    match_images_to_names,
    normalize_size_display,
    oriented_image_jpeg,
    orientation_status,
    parse_america_spans,
    parse_latinoandina_spans,
    title_name,
    weight_grams_from_size,
)

AMERICA_DEFAULT = Path("E:/H/HASAN SPAIN/WEB/catalogo-america-FEB2022.pdf")
LATINOANDINA_DEFAULT = Path(
    "E:/H/HASAN SPAIN/WEB/Catalogo-Latinoandina_Latinos-y-Africanos_2024_web.pdf"
)

# Default operational stock for imported retail units. This is an inventory
# default (not catalog data) so the products can be sold while the admin
# adjusts real availability in Django Admin.
DEFAULT_STOCK = 25

# Distributor section → (category slug, category name). Missing categories
# are created under the latinos business area.
AMERICA_SECTIONS = {
    "BEBIDAS REFRESCANTES": ("cafe-y-bebidas", None),
    "ZUMOS": ("cafe-y-bebidas", None),
    "MALTA": ("cafe-y-bebidas", None),
    "CERVEZAS Y BEBIDAS ALCOHÓLICAS": ("cafe-y-bebidas", None),
    "SNACKS": ("snacks-y-dulces", None),
    "GALLETAS, GOLOSINAS Y CHOCOLATES": ("snacks-y-dulces", None),
    "POSTRES": ("snacks-y-dulces", None),
    "HARINAS": ("harinas-y-granos", None),
    "GRANOS Y LEGUMBRES": ("granos-y-legumbres", "Granos y Legumbres"),
    "CONSERVAS": ("conservas-latinas", "Conservas Latinas"),
    "PASTAS Y SALSAS": ("pastas-y-salsas", "Pastas y Salsas"),
    "ESPECIAS": ("especias-latinas", "Especias Latinas"),
    "FIDEOS": ("fideos-latinos", "Fideos"),
    "CONGELADOS": ("congelados-latinos", "Congelados"),
    "REFRIGERADOS": ("refrigerados-latinos", "Refrigerados"),
    "INSTANTÁNEOS": ("instantaneos-latinos", "Instantáneos"),
    "YERBA MATE": ("yerba-mate", "Yerba Mate"),
    "MATERIA PRIMA": ("materia-prima", "Materia Prima"),
    "HOGAR": ("hogar-latino", "Hogar"),
    "PRODUCTOS AFRICANOS": ("productos-africanos", "Productos Africanos"),
    "PRODUCTOS ARGENTINOS": ("productos-argentinos", "Productos Argentinos"),
}

# Latinoandina code-prefix family → category slug (None = reuse mapping below
# with an auto-created category name).
LATINO_FAMILIES = {
    "PLG": "granos-y-legumbres", "GRA": "granos-y-legumbres",
    "GRH": "granos-y-legumbres", "RIC": "granos-y-legumbres",
    "ZAI": "granos-y-legumbres", "CAM": "granos-y-legumbres",
    "LLH": "granos-y-legumbres", "KBE": "granos-y-legumbres",
    "PAR": "harinas-y-granos",
    "PLL": "conservas-latinas", "PLC": "conservas-latinas",
    "PIR": "conservas-latinas", "REA": "conservas-latinas",
    "PLA": "conservas-latinas",
    "DOP": "congelados-latinos", "FMP": "congelados-latinos",
    "DOC": "congelados-latinos", "DOA": "congelados-latinos",
    "FFI": "congelados-latinos", "FFM": "congelados-latinos",
    "COL": "cafe-y-bebidas", "BEV": "cafe-y-bebidas",
    "ACH": "cafe-y-bebidas", "VGL": "cafe-y-bebidas",
    "CBS": "yerba-mate", "LLB": "yerba-mate",
    "CAS": "snacks-y-dulces", "NES": "snacks-y-dulces",
    "DOS": "snacks-y-dulces", "UNI": "snacks-y-dulces",
    "PIP": "snacks-y-dulces", "COM": "snacks-y-dulces",
    "ECU": "snacks-y-dulces",
    "PER": "especias-latinas", "LLC": "especias-latinas",
    "ROY": "especias-latinas",
    "LLP": "pastas-y-salsas",
    "BAB": "productos-africanos", "MPH": "productos-africanos",
    "PRA": "productos-africanos",
    "VEL": "hogar-latino",
}

SOURCE_LABELS = {
    "america": "América Foods (feb-2022)",
    "latinoandina": "Distribuidora Latinoandina (2024)",
}


def extract_spans(pdf_path: Path) -> list:
    """Flatten a PDF into plain span dicts (true Unicode via raw char codes)."""
    try:
        import pymupdf  # noqa: PLC0415
    except ImportError as exc:
        raise CommandError(
            "PyMuPDF is required for catalog import (pip install PyMuPDF)."
        ) from exc
    doc = pymupdf.open(str(pdf_path))
    spans = []
    for page_no, page in enumerate(doc):
        raw = page.get_text("rawdict")
        for block in raw.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = "".join(c["c"] for c in span["chars"])
                    spans.append(
                        {
                            "text": text,
                            "font": span["font"],
                            "size": span["size"],
                            "bbox": tuple(span["bbox"]),
                            "page": page_no + 1,
                        }
                    )
    return spans


def category_for_entry(entry: dict, cache: dict) -> Category:
    """Resolve (creating when needed) the DB category for an entry."""
    slug, name = "despensa-latina", "Despensa Latina"
    if entry["source"] == "america":
        section = (entry.get("section") or "").upper()
        for key, (s, n) in AMERICA_SECTIONS.items():
            if key in section or section in key:
                slug, name = s, n
                break
    else:
        code = (entry.get("code") or "").upper()
        for prefix, target in LATINO_FAMILIES.items():
            if code.startswith(prefix):
                slug = target
                break
        name = None
    if slug in cache:
        return cache[slug]
    try:
        category = Category.objects.get(slug=slug)
    except Category.DoesNotExist:
        category = Category.objects.create(
            name=name or slug.replace("-", " ").title(),
            slug=slug,
            business_area=BusinessArea.LATINOS,
            description="",
            order=90,
            is_active=True,
        )
    cache[slug] = category
    return category


def brand_for_entry(entry: dict) -> Brand | None:
    """Resolve (creating when needed) the explicit catalog brand, if any."""
    name = (entry.get("brand") or "").strip()
    if not name:
        return None
    brand, _created = Brand.objects.get_or_create(
        name=name, defaults={"slug": slugify(name)[:140] or name.lower()}
    )
    return brand


def build_product_kwargs(entry: dict, category: Category, taken_slugs: set) -> dict:
    """Retail-unit ``Product`` kwargs — individual unit, price pending admin."""
    name = title_name(entry["name"])
    size = normalize_size_display(entry.get("size", ""))
    display = f"{name} {size}".strip() if size else name
    base_slug = slugify(display)[:170] or slugify(entry["code"].lower())
    slug = base_slug
    suffix = 2
    while slug in taken_slugs or Product.objects.filter(slug=slug).exists():
        slug = f"{base_slug}-{suffix}"
        suffix += 1
    taken_slugs.add(slug)
    case = entry.get("case_qty") or ""
    source = SOURCE_LABELS.get(entry["source"], entry["source"])
    description = (
        f"{display}. Unidad individual de {size}." if size else f"{display}."
    )
    if case and case != "1":
        description += f" Formato mayorista en origen: Caja {case} uds."
    elif entry["source"] == "america":
        description += " Referencia de unidad suelta en el catálogo mayorista."
    description += (
        f" Importado del catálogo {source} (código {entry['code']}"
        f"{', pág. ' + str(entry['page']) if entry.get('page') else ''})."
        " Precio pendiente de configuración — el PVP con IVA se fija en la administración."
    )
    return {
        "category": category,
        "business_area": BusinessArea.LATINOS,
        "name": display[:200],
        "slug": slug,
        "sku": entry["code"].upper(),
        "short_description": (
            f"{display} — unidad individual"
            f"{' de ' + size if size else ''}. Precio pendiente de publicación."[:300]
        ),
        "description": description,
        "base_price": Decimal("0.00"),
        "weight_grams": weight_grams_from_size(size),
        "origin_country": (entry.get("origin") or "").strip(),
        "stock": DEFAULT_STOCK,
        "is_active": True,
        "is_featured": False,
    }


def apply_import_updates(product: Product, entry: dict, kwargs: dict) -> None:
    """Refresh an existing imported row without touching admin-set data.

    ``base_price`` is preserved when the admin has priced the product
    (``> 0``); ``slug`` is preserved so URLs never break. Everything else
    (category, size, stock, origin, activation, descriptions) reflects the
    latest catalog import.
    """
    product.category = kwargs["category"]
    product.name = kwargs["name"]
    product.short_description = kwargs["short_description"]
    product.description = kwargs["description"]
    product.weight_grams = kwargs["weight_grams"]
    product.origin_country = kwargs["origin_country"]
    product.stock = kwargs["stock"]
    product.is_active = True
    if product.base_price <= 0:
        product.base_price = kwargs["base_price"]
    brand = brand_for_entry(entry)
    if brand is not None or product.brand_id:
        product.brand = brand
    product.save(
        update_fields=[
            "category",
            "name",
            "short_description",
            "description",
            "weight_grams",
            "origin_country",
            "stock",
            "is_active",
            "base_price",
            "brand",
        ]
    )


def latino_photo_rect(
    page, x0: float, x1: float, name_top: float, top_limit: float = 200.0
) -> object:
    """Page rect of the product photo printed directly above a name box.

    The Latinoandina catalog flattens every page into one raster with the
    product names drawn as separate text. For each name we sample the column
    strip above it, find the nearest contiguous block of non-white pixels
    (the photo) and return its bounding rectangle in page coordinates, or
    ``None`` when no photo-like block is found.
    """
    import pymupdf  # noqa: PLC0415

    top = max(0.0, name_top - top_limit)
    clip = pymupdf.Rect(x0, top, x1, name_top)
    if clip.height <= 0 or clip.width <= 0:
        return None
    try:
        pix = page.get_pixmap(clip=clip, dpi=72)
    except Exception:
        return None
    n, w, h = pix.n, pix.width, pix.height
    if n < 3 or w == 0 or h == 0:
        return None
    samples = pix.samples
    scale = clip.height / h
    step = 2 if w > 200 else 1
    per_row = len(range(0, w, step))
    threshold = per_row * 0.10
    fractions = []
    for yy in range(h):
        base = yy * w * n
        nonwhite = 0
        for xx in range(0, w, step):
            i = base + xx * n
            if samples[i] < 240 or samples[i + 1] < 240 or samples[i + 2] < 240:
                nonwhite += 1
        fractions.append(nonwhite)
    row = h - 1
    while row >= 0 and fractions[row] < threshold:
        row -= 1
    if row < 0:
        return None
    band_end = row
    while row >= 0 and fractions[row] >= threshold:
        row -= 1
    band_start = row + 1
    y_bottom = top + (band_end + 1) * scale
    y_top = top + band_start * scale
    if y_bottom - y_top < 30:
        return None
    return pymupdf.Rect(x0, y_top, x1, y_bottom)


class Command(BaseCommand):
    help = "Import wholesale PDF catalogs as individual retail units."

    def add_arguments(self, parser):
        parser.add_argument("--america-pdf", default=str(AMERICA_DEFAULT))
        parser.add_argument("--latinoandina-pdf", default=str(LATINOANDINA_DEFAULT))
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--skip-images", action="store_true")
        parser.add_argument(
            "--report",
            action="store_true",
            help="Write a full verification report to docs/catalog-import-report.md",
        )

        parser.add_argument(
            "--fix-orientations",
            action="store_true",
            help=(
                "Re-encode América photos whose pixels are still stored in the "
                "raw (mirrored) order the PDF keeps them in"
            ),
        )

    def handle(self, *args, **options):
        america_pdf = Path(options["america_pdf"])
        latino_pdf = Path(options["latinoandina_pdf"])
        for path in (america_pdf, latino_pdf):
            if not path.is_file():
                raise CommandError(f"Catalog PDF not found: {path}")
        dry_run = options["dry_run"]

        america_entries = parse_america_spans(extract_spans(america_pdf))
        latino_entries = parse_latinoandina_spans(extract_spans(latino_pdf))
        self.stdout.write(f"America: {len(america_entries)} unit entries parsed")
        self.stdout.write(f"Latinoandina: {len(latino_entries)} unit entries parsed")

        entries = america_entries + latino_entries
        if options["limit"]:
            entries = entries[: options["limit"]]
        unique_entries, skipped = dedupe_entries(entries)
        self.stdout.write(
            f"Unique catalog entries: {len(unique_entries)} · skipped duplicates: {len(skipped)}"
        )

        existing_skus = {s.upper() for s in Product.objects.values_list("sku", flat=True)}
        to_update = [e for e in unique_entries if e["code"].upper() in existing_skus]
        to_create = [e for e in unique_entries if e["code"].upper() not in existing_skus]
        self.stdout.write(
            f"To create: {len(to_create)} · existing to refresh: {len(to_update)} (prices preserved)"
        )

        if options["fix_orientations"]:
            status_counts = self._fix_orientations(america_pdf, america_entries, dry_run)
            summary = " · ".join(
                f"{label}={status_counts[label]}"
                for label in ("stale", "correct", "drawn-as-stored", "unrelated", "unreadable")
                if label in status_counts
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"América photo orientation ({'dry run' if dry_run else 'rewritten'}): "
                    f"{summary or 'no photos examined'}"
                )
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run — no changes written."))
            return

        taken_slugs = set(Product.objects.values_list("slug", flat=True))
        category_cache: dict = {}
        created, updated = 0, 0
        boxes_by_page: dict = {"america": {}, "latinoandina": {}}
        for entry in to_create + to_update:
            category = category_for_entry(entry, category_cache)
            kwargs = build_product_kwargs(entry, category, taken_slugs)
            product = Product.objects.filter(sku=kwargs["sku"]).first()
            if product is not None:
                apply_import_updates(product, entry, kwargs)
                updated += 1
            else:
                product = Product.objects.create(**kwargs)
                brand = brand_for_entry(entry)
                if brand is not None:
                    product.brand = brand
                    product.save(update_fields=["brand"])
                created += 1
            if not options["skip_images"] and entry.get("_box"):
                boxes_by_page[entry["source"]].setdefault(
                    entry.get("page", 0), []
                ).append((entry, product))
        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created} products · refreshed {updated} existing products"
            )
        )

        attached = {"america": 0, "latinoandina": 0}
        if not options["skip_images"]:
            for source, pdf_path in (
                ("america", america_pdf),
                ("latinoandina", latino_pdf),
            ):
                pairs = boxes_by_page.get(source) or {}
                if not pairs:
                    continue
                count = self._attach_images(
                    pdf_path, pairs, source, skip_if_images=True
                )
                attached[source] = count
        self.stdout.write(
            self.style.SUCCESS(
                "Attached product images: "
                f"america={attached['america']} · latinoandina={attached['latinoandina']}"
            )
        )

        if options["report"]:
            self._write_report(america_entries, latino_entries, created, updated, len(skipped), attached)

    # ------------------------------------------------------------------ #
    # Images                                                              #
    # ------------------------------------------------------------------ #

    def _attach_images(
        self,
        pdf_path: Path,
        boxes_by_page: dict,
        source: str,
        skip_if_images: bool = True,
    ) -> int:
        """Positionally match catalog photos to products and attach them.

        América Foods embeds each product photo as its own image, so those are
        matched by geometry (see ``match_images_to_names``). The Latinoandina
        catalog flattens each page into a single full-page raster with the
        product names printed as separate text, so each photo is recovered by
        rendering the cell region directly above the product name box (see
        ``_latino_photo_rect``). Products that already have images are never
        overwritten.
        """
        import pymupdf  # noqa: PLC0415

        doc = pymupdf.open(str(pdf_path))
        attached = 0
        for page, pairs, rects, box_index in self._iter_page_regions(
            doc, boxes_by_page, source
        ):
            crop_cache = {}
            for entry, product in pairs:
                if skip_if_images and product.images.exists():
                    continue
                ui = box_index.get(tuple(entry.get("_box") or ()))
                if ui is None or ui not in rects:
                    continue
                if ui not in crop_cache:
                    crop_cache[ui] = self._render_region(page, rects[ui])
                data = crop_cache[ui]
                if not data:
                    continue
                product.images.create(
                    image=ContentFile(data, name=f"{product.sku.lower()}.jpg"),
                    image_url="",
                    alt_text=product.name[:200],
                    is_primary=True,
                    order=0,
                )
                attached += 1
        return attached

    def _fix_orientations(self, pdf_path: Path, entries: list, dry_run: bool) -> int:
        """Re-encode América photos that are still stored in raw (mirrored) order.

        The PDF draws most embedded photos through a vertical flip, so the
        samples PyMuPDF extracts are upside-down versions of what the catalog
        shows. Files written before the extractor learned to re-orient them
        are rewritten **in place** — same path, same ``ProductImage`` row — so
        every photo stays on the product it already belongs to. Files that
        already match the drawn orientation are left untouched, which keeps
        the pass repeatable.
        """
        import pymupdf  # noqa: PLC0415

        boxes_by_page: dict = {}
        for entry in entries:
            if not entry.get("_box"):
                continue
            product = Product.objects.filter(sku=entry["code"].upper()).first()
            if product is None or not product.images.exclude(image="").exists():
                continue
            boxes_by_page.setdefault(entry.get("page", 0), []).append((entry, product))

        doc = pymupdf.open(str(pdf_path))
        status_counts: dict = {}
        for page, pairs, rects, box_index in self._iter_page_regions(
            doc, boxes_by_page, "america"
        ):
            for entry, product in pairs:
                ui = box_index.get(tuple(entry.get("_box") or ()))
                if ui is None or ui not in rects:
                    continue
                x0, y0, x1, y1, xref = rects[ui]
                bbox = (x0, y0, x1, y1)
                for image in product.images.exclude(image=""):
                    path = image.image.path
                    try:
                        status = orientation_status(path, page, xref, bbox)
                    except Exception:  # pragma: no cover - defensive
                        status = "unreadable"
                    status_counts[status] = status_counts.get(status, 0) + 1
                    if status != "stale" or dry_run:
                        continue
                    data = oriented_image_jpeg(page, xref, bbox)
                    if not data:
                        continue
                    with open(path, "wb") as handle:
                        handle.write(data)
        return status_counts

    @staticmethod
    def _iter_page_regions(doc, boxes_by_page: dict, source: str):
        """Yield ``(page, pairs, rects, box_index)`` for one catalog source.

        Several entries can share one name box (one product name with two size
        variants = one shared photo), so boxes are de-duplicated first and each
        unique box is matched/extracted once.
        """
        for page_num, pairs in boxes_by_page.items():
            try:
                page = doc[page_num - 1]
            except IndexError:
                continue
            unique_boxes = []
            box_index = {}
            for entry, _product in pairs:
                box = tuple(entry.get("_box") or ())
                if not box:
                    continue
                if box not in box_index:
                    box_index[box] = len(unique_boxes)
                    unique_boxes.append(box)
            if not unique_boxes:
                continue
            if source == "america":
                rects = Command._america_image_rects(page, unique_boxes)
            else:
                rects = Command._latino_photo_rects(page, unique_boxes)
            if not rects:
                continue
            yield page, pairs, rects, box_index

    @staticmethod
    def _america_image_rects(page, unique_boxes: list) -> dict:
        """`{unique_box_index: (x0, y0, x1, y1, xref)}` for América pages."""
        page_area = page.rect.width * page.rect.height
        images = []
        for img in page.get_images(full=True):
            try:
                bbox = page.get_image_bbox(img)
            except ValueError:
                continue
            area = bbox.width * bbox.height
            if area < page_area * 0.015 or area > page_area * 0.6 or bbox.height < 60:
                continue
            images.append((bbox.x0, bbox.y0, bbox.x1, bbox.y1, img[0]))
        if not images:
            return {}
        order = match_images_to_names(
            unique_boxes,
            [(x0, y0, x1, y1) for x0, y0, x1, y1, _ in images],
        )
        return {ui: images[ii] for ui, ii in order.items()}

    @staticmethod
    def _latino_photo_rects(page, unique_boxes: list) -> dict:
        """`{unique_box_index: pymupdf.Rect}` — cell region above each name."""
        bounds = column_bounds_for_names(unique_boxes, page.rect.width)
        rects = {}
        for ui, box in enumerate(unique_boxes):
            rect = latino_photo_rect(page, bounds[ui][0], bounds[ui][1], box[1])
            if rect is not None:
                rects[ui] = rect
        return rects

    @staticmethod
    def _render_region(page, rect) -> bytes | None:
        """Render a page rectangle to JPEG bytes at print-friendly density."""
        import pymupdf  # noqa: PLC0415

        if isinstance(rect, tuple) and len(rect) == 5:  # América: (x0,y0,x1,y1,xref)
            # Raw samples are stored mirrored for most América placements, so
            # they are re-oriented to match how the catalog page draws them.
            return oriented_image_jpeg(page, rect[4], rect[:4])
        try:
            dpi = 200 if min(rect.width, rect.height) < 100 else 150
            return page.get_pixmap(clip=rect, dpi=dpi).tobytes("jpg")
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # Verification report                                                  #
    # ------------------------------------------------------------------ #

    def _write_report(
        self,
        america_entries: list,
        latino_entries: list,
        created: int,
        updated: int,
        skipped: int,
        attached: dict,
    ) -> None:
        """Full verification report — stdout + docs/catalog-import-report.md."""
        latinos = Product.objects.filter(business_area=BusinessArea.LATINOS)
        total = latinos.count()
        with_price = latinos.filter(base_price__gt=0).count()
        with_images = latinos.filter(images__isnull=False).distinct().count()
        with_origin = latinos.exclude(origin_country="").count()
        with_brand = latinos.filter(brand__isnull=False).count()
        no_price = total - with_price
        no_images = total - with_images

        by_source = {
            "América Foods (feb-2022)": len(america_entries),
            "Distribuidora Latinoandina (2024)": len(latino_entries),
        }
        categories = Category.objects.filter(business_area=BusinessArea.LATINOS).order_by("name")
        category_lines = [
            f"| {c.name} | {c.products.filter(is_active=True).count()} |" for c in categories
        ]

        lines = [
            "# Catalog Import Report",
            "",
            "Generated by `python manage.py import_wholesale_catalogs --report`.",
            "",
            "## Products identified in the PDFs",
            "",
            f"- América Foods (feb-2022): **{by_source['América Foods (feb-2022)']}** individual retail-unit entries",
            f"- Distribuidora Latinoandina (2024): **{by_source['Distribuidora Latinoandina (2024)']}** individual retail-unit entries",
            f"- **Total identifiable entries: {len(america_entries) + len(latino_entries)}**",
            "",
            "## Import result",
            "",
            f"- Products created: **{created}**",
            f"- Existing products updated: **{updated}**",
            f"- Duplicates skipped: **{skipped}**",
            f"- Images attached — América: **{attached.get('america', 0)}** · Latinoandina: **{attached.get('latinoandina', 0)}**",
            "",
            "## Database state (Productos Latinos)",
            "",
            f"- Total products: **{total}**",
            f"- With individual retail price: **{with_price}**",
            f"- Missing individual price (pending admin PVP): **{no_price}**",
            f"- With product image: **{with_images}**",
            f"- Missing product image: **{no_images}**",
            f"- With explicit origin: **{with_origin}**",
            f"- With explicit brand: **{with_brand}**",
            "",
            "## Categories",
            "",
            "| Category | Products |",
            "|---|---|",
            *category_lines,
            "",
            "## Manual review required",
            "",
            f"- **{no_price}** products have no retail price — the wholesale catalogs do not show prices. Set the PVP (IVA included) in Django Admin → Productos.",
            f"- **{no_images}** products have no photo — no product image could be matched on the catalog page. Assign images in Django Admin.",
            f"- **{total - with_origin}** products have no country of origin — the catalogs do not state origins (except Pony Malta: Colombia). Leave blank until verified.",
            f"- **{total - with_brand}** products have no brand — brands are only set when the catalog explicitly names them (Oriental, Tesoro Natural, Pony Malta).",
            "- The 3 admin-created products (TIN-LAT-*) keep their admin-set prices and are never overwritten by re-imports.",
            "",
            "## Idempotency",
            "",
            "Re-running the command is safe: products are matched by distributor code (SKU) and by normalised (name, size); existing rows are updated in place, never duplicated. Admin-set prices (base_price > 0) and slugs are preserved.",
            "",
        ]
        report_path = Path(__file__).resolve().parents[4] / "docs" / "catalog-import-report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"Report written to {report_path}"))
