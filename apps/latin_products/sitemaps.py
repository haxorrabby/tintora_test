"""Sitemaps for the static LATIN PRODUCTS catalog dataset."""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .data import get_catalog


class LatinCategorySitemap(Sitemap):
    """The 13 latin category landing pages."""

    changefreq = "monthly"
    priority = 0.7
    i18n = True
    alternates = True

    def items(self):
        return get_catalog()["categories"]

    def location(self, item):
        return reverse("latin_products:entry", args=[item["slug"]])


class LatinProductSitemap(Sitemap):
    """Every product detail page in the catalog."""

    changefreq = "monthly"
    priority = 0.6
    i18n = True
    alternates = True

    def items(self):
        return get_catalog()["products"]

    def location(self, item):
        return reverse("latin_products:entry", args=[item["slug"]])
