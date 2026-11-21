from django.urls import path

from .views import (
    CartAddView,
    CartApplyCouponView,
    CartDetailView,
    CartDrawerPartialView,
    CartDuplicateItemView,
    CartRemoveCouponView,
    CartRemoveItemView,
    CartSelectShippingView,
    CartUpdateItemView,
)

app_name = "cart"

urlpatterns = [
    path("", CartDetailView.as_view(), name="detail"),
    path("anadir/<slug:slug>/", CartAddView.as_view(), name="add"),
    path("actualizar/<int:item_id>/", CartUpdateItemView.as_view(), name="update"),
    path("duplicar/<int:item_id>/", CartDuplicateItemView.as_view(), name="duplicate"),
    path("eliminar/<int:item_id>/", CartRemoveItemView.as_view(), name="remove"),
    path("cupon/aplicar/", CartApplyCouponView.as_view(), name="apply_coupon"),
    path("cupon/eliminar/", CartRemoveCouponView.as_view(), name="remove_coupon"),
    path("envio/seleccionar/", CartSelectShippingView.as_view(), name="select_shipping"),
    path("drawer/", CartDrawerPartialView.as_view(), name="drawer"),
]
