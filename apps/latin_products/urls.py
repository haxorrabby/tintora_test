from django.urls import path

from .views import LatinCatalogView, LatinLandingView

app_name = "latin_products"

urlpatterns = [
    path("", LatinCatalogView.as_view(), name="index"),
    # Single entry route: resolves to a category landing page or a product
    # detail page, both living directly under /latin-products/<slug>/.
    path("<slug:slug>/", LatinLandingView.as_view(), name="entry"),
]
