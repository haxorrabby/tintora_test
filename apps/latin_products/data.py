"""
apps/latin_products/data.py — LATIN PRODUCTS catalog data layer.

The catalog is served from the Django product database: every entry is a
``catalog.Product`` row (``business_area = latinos``) imported from the two
wholesale PDF catalogs (see ``apps.catalog.management.commands.
import_wholesale_catalogs``) or created by the admin. Prices, stock, origin,
brand and images are all managed through Django Admin.

This module exposes an immutable, **public-only** view of that data:

* internal fields (``sku``, ``id``, ``created_at``) never reach a template
  or the client-side JSON payload;
* every product carries a derived ``categorySlug`` used for filtering/URLs;
* the individual retail unit is preserved (name + ``retailSize``); wholesale
  case language ("Caja …", "… Uds.") never leaks into the storefront.

Nothing here writes to the database, so re-importing a catalog revision only
means re-running the import command — no UI changes.
"""

from __future__ import annotations

import re

from apps.catalog.models import BusinessArea, Category, Product

# Only these keys are ever exposed to templates / client-side payloads.
PUBLIC_CATEGORY_FIELDS = ("slug", "name", "description", "count")
PUBLIC_PRODUCT_FIELDS = (
    "slug",
    "name",
    "nameEn",
    "brand",
    "category",
    "categorySlug",
    "subcategory",
    "retailSize",
    "image",
    "image_url",
    "price",
    "stock",
    "inStock",
    "originCountry",
    "weightGrams",
    "variants",
)

# Trailing retail size inside a DB product name (``"Andis Kola 2 L"``).
_TRAILING_SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb|uds?|u)\.?)$",
    re.IGNORECASE,
)
_UNIT_NORMALIZE = {"gr": "g", "lt": "l"}


def retail_size_from_name(name: str) -> str:
    """Individual retail unit shown in a DB product name, else ``""``.

    The import builds names as ``"Title 500 g"`` — the trailing size is the
    individual retail unit and is preserved as-is (normalised spacing).
    """
    match = _TRAILING_SIZE_RE.search(name or "")
    if not match:
        return ""
    size = " ".join(match.group(1).split())
    number, _, unit = size.partition(" ")
    unit = unit.lower().rstrip(".")
    unit = _UNIT_NORMALIZE.get(unit, unit)
    return f"{number} {unit}".strip()


def _public_product(product: Product) -> dict:
    """Public dict for one DB ``Product`` — safe for templates and JSON."""
    variants = [
        {
            "slug": variant.slug,
            "label": variant.variant_label,
            "price": float(variant.base_price),
            "stock": variant.stock,
            "inStock": variant.in_stock,
            "weightGrams": variant.weight_grams,
            "image_url": variant.primary_image_url,
        }
        for variant in product.active_variants
    ]
    return {
        "slug": product.slug,
        "name": product.name,
        "nameEn": "",
        "brand": product.brand.name if product.brand else "",
        "category": product.category.name,
        "categorySlug": product.category.slug,
        "subcategory": "",
        "retailSize": product.variant_label or retail_size_from_name(product.name),
        "image": "",
        "image_url": product.primary_image_url,
        "price": float(product.base_price),
        "stock": product.stock,
        "inStock": product.in_stock,
        "originCountry": product.origin_country or "",
        "weightGrams": product.weight_grams,
        "variants": variants,
    }


def get_catalog() -> dict:
    """
    Load the full catalog from the database.

    Returns a dict with:
      ``products``           list of public product dicts (name order)
      ``categories``         list of public category dicts (menu order)
      ``products_by_slug``   slug -> product lookup
      ``categories_by_slug`` slug -> category lookup

    The returned dict and its lists MUST NOT be mutated by callers.
    """
    categories = list(
        Category.objects.filter(
            business_area=BusinessArea.LATINOS, is_active=True
        ).order_by("order", "name")
    )
    products = list(
        Product.objects.filter(business_area=BusinessArea.LATINOS, is_active=True)
        .filter(parent_product__isnull=True)
        .select_related("category", "brand")
        .prefetch_related("images", "size_variants__images", "size_variants__category", "size_variants__brand")
        .order_by("name")
    )

    public_categories = [
        {
            "slug": category.slug,
            "name": category.name,
            "description": category.description or "",
            "count": sum(1 for p in products if p.category_id == category.id),
        }
        for category in categories
    ]
    public_products = [_public_product(product) for product in products]

    return {
        "products": public_products,
        "categories": public_categories,
        "products_by_slug": {product["slug"]: product for product in public_products},
        "categories_by_slug": {category["slug"]: category for category in public_categories},
    }


def product_total() -> int:
    """Total number of products in the catalog."""
    return Product.objects.filter(
        business_area=BusinessArea.LATINOS, is_active=True, parent_product__isnull=True
    ).count()


def products_for_category(category_slug: str) -> list:
    """Products belonging to one category, in catalog order."""
    return [
        _public_product(product)
        for product in Product.objects.filter(
            category__slug=category_slug,
            business_area=BusinessArea.LATINOS,
            is_active=True,
            parent_product__isnull=True,
        )
        .select_related("category", "brand")
        .prefetch_related("images", "size_variants__images", "size_variants__category", "size_variants__brand")
        .order_by("name")
    ]


def related_products(product: dict, limit: int = 4) -> list:
    """Other products from the same category, excluding itself."""
    related = [
        item
        for item in get_catalog()["products"]
        if item["categorySlug"] == product["categorySlug"] and item["slug"] != product["slug"]
    ]
    return related[:limit]


def brand_names(products: list) -> list:
    """Distinct brands present in ``products``, alphabetically (es, accents aware)."""
    names = {p["brand"] for p in products if p["brand"]}
    return sorted(names, key=lambda value: value.casefold())


def catalog_payload(products=None) -> dict:
    """
    JSON-serialisable payload embedded in catalog templates via ``json_script``.
    Contains public fields only — safe to expose to the browser.
    """
    catalog = get_catalog()
    return {
        "products": list(catalog["products"] if products is None else products),
        "categories": catalog["categories"],
    }


def preview_products(limit: int = 8) -> list:
    """
    Homepage preview: the first product of each distinct category, in
    catalog order — a deterministic, representative spread across the catalog.
    """
    preview = []
    seen_categories: set = set()
    for product in get_catalog()["products"]:
        if product["categorySlug"] in seen_categories:
            continue
        seen_categories.add(product["categorySlug"])
        preview.append(product)
        if len(preview) >= limit:
            break
    return preview
