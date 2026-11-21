"""
apps/latin_products/views.py — LATIN PRODUCTS catalog views.

All views render the database-backed catalog (``catalog.Product`` rows with
``business_area = latinos``); none of them expose internal dataset fields
(id / xref / sourcePage) to the frontend. Every product is purchased through
the normal online cart and checkout — there is no WhatsApp ordering flow.
"""

from __future__ import annotations

from django.http import Http404
from django.shortcuts import render
from django.templatetags.static import static
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView

from .data import (
    brand_names,
    catalog_payload,
    get_catalog,
    products_for_category,
    related_products,
)


class LatinCatalogView(TemplateView):
    """``/latin-products/`` — full catalog with client-side search/filter/sort."""

    template_name = "pages/latin_catalog.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        catalog = get_catalog()
        products = catalog["products"]
        context.update(
            {
                "is_index": True,
                "active_category": None,
                "page_products": products,
                "latin_categories": catalog["categories"],
                "latin_payload": catalog_payload(),
                "catalog_total": len(products),
                "brand_count": len(brand_names(products)),
            }
        )
        return context


class LatinLandingView(View):
    """
    ``/latin-products/<slug>/`` — resolves to either:

    * a **category landing page** (factual description + that category's grid), or
    * a **product detail page** (image, facts, price, stock, add-to-cart).

    A slug that matches neither raises 404.
    """

    def get(self, request, slug: str):
        catalog = get_catalog()

        # ------------------------------------------------------------ #
        # Category landing page                                        #
        # ------------------------------------------------------------ #
        category = catalog["categories_by_slug"].get(slug)
        if category is not None:
            products = products_for_category(slug)
            context = {
                "is_index": False,
                "active_category": category,
                "page_products": products,
                "latin_categories": catalog["categories"],
                "latin_payload": catalog_payload(products),
                "catalog_total": len(catalog["products"]),
                "brand_count": len(brand_names(products)),
            }
            return render(request, "pages/latin_catalog.html", context)

        # ------------------------------------------------------------ #
        # Product detail page                                          #
        # ------------------------------------------------------------ #
        product = catalog["products_by_slug"].get(slug)
        if product is not None:
            context = {
                "product": product,
                "product_category": catalog["categories_by_slug"][product["categorySlug"]],
                "related_products": related_products(product),
                "product_schema": self._product_schema(request, product),
            }
            return render(request, "pages/latin_product_detail.html", context)

        raise Http404("No latin product or category matches the given slug.")

    @staticmethod
    def _product_schema(request, product: dict) -> dict:
        """schema.org Product markup — facts plus an offer only when priced."""
        schema = {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": product["name"],
            "url": request.build_absolute_uri(reverse("latin_products:entry", args=[product["slug"]])),
            "image": [request.build_absolute_uri(product["image_url"])],
            "category": product["category"],
        }
        if product["nameEn"]:
            schema["alternateName"] = product["nameEn"]
        if product["brand"]:
            schema["brand"] = {"@type": "Brand", "name": product["brand"]}
        if product["price"] > 0:
            schema["offers"] = {
                "@type": "Offer",
                "url": request.build_absolute_uri(reverse("latin_products:entry", args=[product["slug"]])),
                "priceCurrency": "EUR",
                "price": str(product["price"]),
                "availability": (
                    "https://schema.org/InStock" if product["inStock"] else "https://schema.org/OutOfStock"
                ),
                "itemCondition": "https://schema.org/NewCondition",
            }
        return schema
