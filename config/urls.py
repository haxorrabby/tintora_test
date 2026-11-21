from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.shortcuts import render
from django.urls import include, path

from apps.core.sitemaps import ArticleSitemap, CategorySitemap, LegalSitemap, ProductSitemap, StaticViewSitemap
from apps.core.views import health_check, page_not_found_view, public_catalog_media, server_error_view
from apps.dashboard.views import admin_dashboard
from apps.latin_products.sitemaps import LatinCategorySitemap, LatinProductSitemap

handler404 = "apps.core.views.page_not_found_view"
handler403 = "apps.core.views.permission_denied_view"
handler500 = "apps.core.views.server_error_view"

# Clean admin URL configuration
admin_url = settings.ADMIN_URL_PATH.strip("/") + "/"
admin.site.index = admin_dashboard

# Sitemap configuration
sitemaps = {
    'static': StaticViewSitemap,
    'legal': LegalSitemap,
    'products': ProductSitemap,
    'categories': CategorySitemap,
    'articles': ArticleSitemap,
    'latin_products': LatinProductSitemap,
    'latin_categories': LatinCategorySitemap,
}

urlpatterns = [
    # Health check for monitoring (non-localized)
    path("healthz/", health_check, name="health_check"),
    # Django i18n switcher endpoint
    path("i18n/", include("django.conf.urls.i18n")),
    # Sitemap (non-localized)
    path("sitemap.xml", sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
    # Robots.txt (non-localized)
    path("robots.txt", lambda r: render(r, 'robots.txt', content_type='text/plain')),
    path(f"{admin_url}2fa/", include("apps.dashboard.urls", namespace="dashboard")),
    # Hidden Staff Admin URL
    path(admin_url, admin.site.urls),
    # Payment webhooks — non-localized so Stripe can POST without locale prefix
    path("pagos/", include("apps.payments.urls", namespace="payments")),
]

# Catalog images are public product assets; other media (invoices/artwork)
# remains private and is never exposed by this route.
if not settings.USE_S3:
    urlpatterns += [
        path(
            settings.MEDIA_URL.lstrip("/") + "catalog/<path:path>",
            public_catalog_media,
            name="public_catalog_media",
        )
    ]


# Localized URLs: /es/ and /en/
urlpatterns += i18n_patterns(
    path("", include("apps.core.urls", namespace="core")),
    path("catalogo/", include("apps.catalog.urls", namespace="catalog")),
    path("latin-products/", include("apps.latin_products.urls", namespace="latin_products")),
    path("carrito/", include("apps.cart.urls", namespace="cart")),
    path("", include("apps.orders.urls", namespace="orders")),
    path("", include("apps.accounts.urls", namespace="customer")),
    path("blog/", include("apps.blog.urls", namespace="blog")),
    path("desarrollo-web/", include("apps.quotes.urls", namespace="quotes")),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
