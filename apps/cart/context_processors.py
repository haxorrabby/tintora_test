from apps.cart.services import CartService


def cart_context(request):
    """
    Exposes active Cart object and item count across all views.
    Handles lazy initialization so pages that do not render cart info do not trigger extra queries.
    """
    # Exclude admin and internal paths
    if (
        request.path.startswith("/gestion-tintora/")
        or request.path.startswith("/admin/")
        or request.path.startswith("/healthz/")
    ):
        return {}

    try:
        cart = CartService.get_cart(request)
        return {
            "cart": cart,
            "cart_item_count": cart.item_count if cart is not None else 0,
        }
    except Exception:
        return {
            "cart": None,
            "cart_item_count": 0,
        }
