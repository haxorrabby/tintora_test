"""Preview or safely group exact-name, size-only product records."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cart.models import CartItem
from apps.catalog.models import Product
from apps.orders.models import OrderItem

SIZE_SUFFIX_RE = re.compile(
    r"\s+(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\.?\s*$",
    re.IGNORECASE,
)
UNIT_FACTORS = {
    "kg": ("weight", Decimal("1000")),
    "g": ("weight", Decimal("1")),
    "gr": ("weight", Decimal("1")),
    "lb": ("weight", Decimal("453.59237")),
    "oz": ("weight", Decimal("28.349523125")),
    "l": ("volume", Decimal("1000")),
    "cl": ("volume", Decimal("10")),
    "ml": ("volume", Decimal("1")),
}


def _size_sort_key(label: str) -> tuple[str, Decimal, str]:
    match = re.fullmatch(r"\s*(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|cl|oz|lb)\.?\s*", label, re.I)
    if not match:
        return "other", Decimal("0"), label.casefold()
    amount = Decimal(match.group(1).replace(",", "."))
    dimension, factor = UNIT_FACTORS[match.group(2).casefold()]
    return dimension, amount * factor, label.casefold()


def _candidate_groups() -> list[dict]:
    grouped = defaultdict(list)
    products = (
        Product.objects.filter(is_active=True, parent_product__isnull=True)
        .select_related("brand", "category")
        .order_by("pk")
    )
    for product in products:
        match = SIZE_SUFFIX_RE.search(product.name)
        if not match:
            continue
        base_name = " ".join(product.name[: match.start()].split())
        key = (base_name.casefold(), product.category_id, product.brand_id, product.business_area)
        grouped[key].append((product, base_name, match.group(1).strip()))

    candidates = []
    for rows in grouped.values():
        if len(rows) < 2 or len({label.casefold() for _product, _base, label in rows}) < 2:
            continue
        rows.sort(key=lambda row: _size_sort_key(row[2]))
        candidates.append(
            {
                "base_name": rows[0][1],
                "category": rows[0][0].category.name,
                "brand": rows[0][0].brand.name if rows[0][0].brand_id else "",
                "products": [
                    {
                        "id": product.pk,
                        "name": product.name,
                        "slug": product.slug,
                        "variant_label": label,
                        "price": str(product.base_price),
                        "stock": product.stock,
                        "orders": OrderItem.objects.filter(product_id=product.pk).count(),
                        "cart_items": CartItem.objects.filter(product_id=product.pk).count(),
                    }
                    for product, _base, label in rows
                ],
            }
        )
    return sorted(candidates, key=lambda group: (group["category"].casefold(), group["base_name"].casefold()))


class Command(BaseCommand):
    help = (
        "Preview exact product-name groups differing only by a trailing size. "
        "Use --apply to link records without deleting products or changing prices/stock."
    )

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Apply the previewed parent/variant links.")

    def handle(self, *args, **options):
        candidates = _candidate_groups()
        summary = {
            "mode": "apply" if options["apply"] else "dry-run",
            "candidate_groups": len(candidates),
            "product_records": sum(len(group["products"]) for group in candidates),
            "groups": candidates,
        }
        self.stdout.write(json.dumps(summary, ensure_ascii=True, indent=2))
        if not options["apply"]:
            self.stderr.write(self.style.WARNING("Dry run only. Re-run with --apply to group these records."))
            return

        grouped_records = 0
        with transaction.atomic():
            for group in candidates:
                root_id = group["products"][0]["id"]
                root = Product.objects.get(pk=root_id, parent_product__isnull=True)
                root.name = group["base_name"]
                root.variant_label = group["products"][0]["variant_label"]
                root.save(update_fields=["name", "variant_label", "updated_at"])
                for item in group["products"][1:]:
                    Product.objects.filter(pk=item["id"], parent_product__isnull=True).update(
                        parent_product=root,
                        variant_label=item["variant_label"],
                    )
                grouped_records += len(group["products"])

        self.stderr.write(
            self.style.SUCCESS(
                f"Grouped {grouped_records} existing product records into {len(candidates)} parent products. "
                "No product, cart, or order rows were deleted."
            )
        )
