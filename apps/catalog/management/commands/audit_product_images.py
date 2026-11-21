"""Report missing, broken, and unverified product image assignments."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product, ProductImage


def _audit_rows() -> list[dict[str, str | int]]:
    from PIL import Image, UnidentifiedImageError

    rows = []
    products = Product.objects.filter(is_active=True).select_related("category").prefetch_related("images")
    for product in products:
        image_rows = list(product.images.all())
        issues = []
        image_sources = []
        for image in image_rows:
            if image.image:
                try:
                    with Image.open(image.image.path) as source:
                        source.verify()
                except (OSError, UnidentifiedImageError, ValueError):
                    issues.append(f"broken local image record {image.pk}")
                else:
                    image_sources.append(image.image.name)
            elif image.image_url and "tintora-logo-mono.svg" not in image.image_url:
                image_sources.append(image.image_url)
                if image.verification_status != ProductImage.VerificationStatus.VERIFIED:
                    issues.append(f"unverified image URL record {image.pk}")
            else:
                issues.append(f"image record {image.pk} has no usable file or URL")

        if not image_rows:
            issues.append("no image records")
        if product.image_review_status != Product.ImageReviewStatus.VERIFIED:
            issues.append(f"product image review is {product.image_review_status}")
        if issues:
            rows.append(
                {
                    "product_id": product.pk,
                    "name": product.display_name,
                    "variant": product.variant_label,
                    "category": product.category.name,
                    "slug": product.slug,
                    "image_review_status": product.image_review_status,
                    "issue": "; ".join(dict.fromkeys(issues)),
                    "assigned_images": " | ".join(image_sources),
                }
            )
    return rows


class Command(BaseCommand):
    help = "Audit image file integrity and export products still needing human image verification."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=Path,
            help="Write the UTF-8 CSV report to this file instead of standard output.",
        )
        parser.add_argument(
            "--mark-missing",
            action="store_true",
            help="Mark products with no usable assigned image as requiring manual review.",
        )
        parser.add_argument(
            "--mark-unverified",
            action="store_true",
            help="Mark every unverified product/image record in the audit as requiring manual review.",
        )

    def handle(self, *args, **options):
        rows = _audit_rows()
        if options["mark_missing"]:
            ids = [
                row["product_id"]
                for row in rows
                if "no image records" in row["issue"] or "no usable file or URL" in row["issue"]
            ]
            with transaction.atomic():
                Product.objects.filter(pk__in=ids).update(
                    image_review_status=Product.ImageReviewStatus.MANUAL_REVIEW,
                    image_review_notes="No verified product image assigned; manual review required.",
                )
                ProductImage.objects.filter(product_id__in=ids).update(
                    verification_status=ProductImage.VerificationStatus.MANUAL_REVIEW
                )
        if options["mark_unverified"]:
            product_ids = [row["product_id"] for row in rows]
            with transaction.atomic():
                Product.objects.filter(pk__in=product_ids).exclude(
                    image_review_status=Product.ImageReviewStatus.VERIFIED
                ).update(
                    image_review_status=Product.ImageReviewStatus.MANUAL_REVIEW,
                    image_review_notes="Assigned image has not been verified against the exact product package.",
                )
                ProductImage.objects.filter(product_id__in=product_ids).exclude(
                    verification_status=ProductImage.VerificationStatus.VERIFIED
                ).update(verification_status=ProductImage.VerificationStatus.MANUAL_REVIEW)

        output = io.StringIO()
        fields = (
            "product_id",
            "name",
            "variant",
            "category",
            "slug",
            "image_review_status",
            "issue",
            "assigned_images",
        )
        writer = csv.DictWriter(output, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        if options["output"]:
            options["output"].write_text(output.getvalue(), encoding="utf-8", newline="")
            self.stdout.write(f"CSV report saved to {options['output']}")
        else:
            self.stdout.write(output.getvalue(), ending="")
        self.stderr.write(f"Image audit: {len(rows)} active product records need image review.")
