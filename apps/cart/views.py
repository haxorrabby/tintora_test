from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView, View

from apps.catalog.models import Product

from .models import ShippingMethod, ShippingZone
from .services import CartService


def _shipping_methods(cart) -> list[ShippingMethod]:
    """Active shipping methods annotated with ``current_cost`` for the
    template (``calculate_cost`` is a method and cannot be called with the
    required subtotal argument from template land)."""
    methods = list(ShippingMethod.objects.filter(is_active=True).select_related("zone"))
    for method in methods:
        method.current_cost = method.calculate_cost(cart.subtotal, 0)
    return methods


class CartDetailView(TemplateView):
    """
    Main Cart Page with editorial layout, item list, artwork statuses,
    coupon application, Madrid local & national shipping calculator,
    and 21% IVA breakdown.
    """

    template_name = "pages/cart_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cart = CartService.get_or_create_cart(self.request)
        shipping_zones = ShippingZone.objects.filter(is_active=True).prefetch_related("methods")
        shipping_methods = _shipping_methods(cart)

        context.update(
            {
                "cart": cart,
                "shipping_zones": shipping_zones,
                "shipping_methods": shipping_methods,
                "page_title": _("Cesta de Compra · Tintora Madrid"),
            }
        )
        return context


class CartAddView(View):
    """
    Adds a product with its full configuration (tirada, papers, artwork, proof)
    into the active cart. Supports both standard POST and HTMX instant addition.
    """

    def post(self, request: HttpRequest, slug: str) -> HttpResponse:
        product = get_object_or_404(Product, slug=slug, is_active=True)
        root_product = product.variant_root
        product = root_product
        variant_slug = request.POST.get("variant_slug", "").strip()
        variant_id = request.POST.get("variant_id")
        if variant_slug:
            selected = get_object_or_404(Product, slug=variant_slug, is_active=True)
            if selected.pk != root_product.pk and selected.parent_product_id != root_product.pk:
                messages.error(request, _("Selecciona una variante válida."))
                return redirect(root_product.get_absolute_url())
            product = selected
        elif variant_id:
            try:
                variant_pk = int(variant_id)
            except (TypeError, ValueError):
                messages.error(request, _("Selecciona una variante válida."))
                return redirect(root_product.get_absolute_url())
            if variant_pk != product.pk:
                product = get_object_or_404(
                    Product,
                    pk=variant_pk,
                    parent_product=root_product,
                    is_active=True,
                )
        cart = CartService.get_or_create_cart(request)

        try:
            quantity = int(request.POST.get("quantity", 1))
        except (ValueError, TypeError):
            quantity = 1

        # Collect selected option value IDs
        option_value_ids = []
        for key, value in request.POST.items():
            if key.startswith("option_") and value:
                try:
                    option_value_ids.append(int(value))
                except (ValueError, TypeError):
                    pass

        # Artwork & proof flags
        design_later = request.POST.get("design_later") in ["true", "1", "on", True]
        request_proof = request.POST.get("request_proof") in ["true", "1", "on", True]
        artwork_file = request.FILES.get("artwork_file")
        notes = request.POST.get("notes", "").strip()

        try:
            CartService.add_item(
                cart=cart,
                product=product,
                quantity=quantity,
                option_value_ids=option_value_ids,
                artwork_file=artwork_file,
                design_later=design_later,
                request_proof=request_proof,
                notes=notes,
            )
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect(product.get_absolute_url())

        messages.success(request, _("Producto '%(name)s' añadido al carrito.") % {"name": product.name})

        if request.headers.get("HX-Request"):
            if request.GET.get("target") == "drawer":
                return render(
                    request,
                    "components/cart_drawer_partial.html",
                    {"cart": cart, "just_added": True},
                )
            return render(request, "components/cart_summary_partial.html", {"cart": cart})

        return redirect("cart:detail")


class CartUpdateItemView(View):
    """Updates line item quantity via inline stepper or HTMX."""

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        action = request.POST.get("action")
        qty_val = request.POST.get("quantity")

        item = cart.items.filter(id=item_id).first()
        if not item:
            return redirect("cart:detail")

        if action == "inc":
            new_qty = item.quantity + 1
        elif action == "dec":
            new_qty = max(1, item.quantity - 1)
        elif qty_val:
            try:
                new_qty = max(1, int(qty_val))
            except ValueError:
                new_qty = item.quantity
        else:
            new_qty = item.quantity

        CartService.update_quantity(item_id, new_qty, cart)

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartDuplicateItemView(View):
    """Duplicates a cart item with the same paper, finish and configuration."""

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        duplicated = CartService.duplicate_item(item_id, cart)
        if duplicated is None:
            messages.error(request, _("No hay stock suficiente para duplicar esta variante."))
        else:
            messages.info(request, _("Línea duplicada con la misma configuración."))

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartRemoveItemView(View):
    """Removes a line item from the cart."""

    def post(self, request: HttpRequest, item_id: int) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        CartService.remove_item(item_id, cart)
        messages.info(request, _("Producto retirado de la cesta."))

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartApplyCouponView(View):
    """Applies a promotional or corporate coupon code."""

    def post(self, request: HttpRequest) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        code = request.POST.get("code", "")
        success, message = CartService.apply_coupon(cart, code)

        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartRemoveCouponView(View):
    """Removes currently applied coupon."""

    def post(self, request: HttpRequest) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        CartService.remove_coupon(cart)
        messages.info(request, _("Cupón retirado."))

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartSelectShippingView(View):
    """Updates shipping method and postal code calculation."""

    def post(self, request: HttpRequest) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        method_id = request.POST.get("shipping_method_id")
        postal_code = request.POST.get("postal_code", "28012")

        if method_id:
            try:
                CartService.set_shipping(cart, int(method_id), postal_code)
            except (ValueError, TypeError):
                pass

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/cart_items_partial.html",
                {
                    "cart": cart,
                    "shipping_methods": _shipping_methods(cart),
                },
            )
        return redirect("cart:detail")


class CartDrawerPartialView(View):
    """Returns the HTMX partial for the header slide-over cart drawer."""

    def get(self, request: HttpRequest) -> HttpResponse:
        cart = CartService.get_or_create_cart(request)
        return render(request, "components/cart_drawer_partial.html", {"cart": cart})
