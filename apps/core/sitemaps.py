from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import Article
from apps.catalog.models import Category, Product


class StaticViewSitemap(Sitemap):
    """Sitemap for public, named landing pages."""
    priority = 0.5
    changefreq = "monthly"
    i18n = True
    alternates = True

    def items(self):
        return [
            "core:home",
            "catalog:index",
            "quotes:development",
            "blog:article_list",
            "latin_products:index",
            "core:faq",
            "core:contact",
        ]

    def location(self, item):
        return reverse(item)


class LegalSitemap(Sitemap):
    """Sitemap for the legal notice pages (aviso legal, privacidad, cookies…)."""
    priority = 0.2
    changefreq = "yearly"
    i18n = True
    alternates = True

    LEGAL_SLUGS = [
        "aviso-legal",
        "politica-privacidad",
        "politica-cookies",
        "condiciones-venta",
        "envios-devoluciones",
    ]

    def items(self):
        return self.LEGAL_SLUGS

    def location(self, item):
        return reverse("core:legal", args=[item])


class ProductSitemap(Sitemap):
    """Sitemap for products"""
    changefreq = 'weekly'
    priority = 0.8
    i18n = True
    alternates = True

    def items(self):
        return Product.objects.filter(is_active=True, category__is_active=True).select_related("category")

    def lastmod(self, obj):
        return obj.updated_at


class CategorySitemap(Sitemap):
    """Sitemap for categories"""
    changefreq = 'monthly'
    priority = 0.6
    i18n = True
    alternates = True

    def items(self):
        return Category.objects.filter(is_active=True)

    def lastmod(self, obj):
        return obj.updated_at


class ArticleSitemap(Sitemap):
    """Sitemap for blog articles"""
    changefreq = 'weekly'
    priority = 0.7
    i18n = True
    alternates = True

    def items(self):
        return Article.objects.filter(status=Article.Status.PUBLISHED)

    def lastmod(self, obj):
        return obj.published_at or obj.updated_at
