from django.urls import path

from .views import (
    CatalogIndexView,
    CategoryDetailView,
    InstantSearchView,
    ProductDetailView,
)

app_name = "catalog"

urlpatterns = [
    path("", CatalogIndexView.as_view(), name="index"),
    path("buscar/", InstantSearchView.as_view(), name="search"),
    path("categoria/<slug:slug>/", CategoryDetailView.as_view(), name="category_detail"),
    path("producto/<slug:slug>/", ProductDetailView.as_view(), name="product_detail"),
]
