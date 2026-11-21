from typing import Any

from django.db.models import Sum
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.catalog.models import Product, ProductOptionValue

from .models import Cart, CartItem, Coupon, ShippingMethod


class CartService:
    @staticmethod
    def get_cart(request: HttpRequest) -> Cart | None:
        """Return the active cart for this request WITHOUT creating one.

        Read-only: returns ``None`` when the user/session has no cart yet, so
        navigation pages, 404 renders, SEO crawls and the like never
        materialize stray empty carts. Real cart-side views call
        ``get_or_create_cart`` when they actually need to write.
        """
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).order_by("-updated_at").first()
        else:
            session_key = request.session.session_key
            cart = None
            if session_key:
                cart = Cart.objects.filter(session_key=session_key, user__isnull=True).order_by("-updated_at").first()
        if cart is not None:
            cart.recalculate()
        return cart

    @staticmethod
    def get_or_create_cart(request: HttpRequest) -> Cart:
        """
        Retrieves the active Cart for the authenticated user or guest session.
        Creates a session if one does not exist yet.
        """
        if request.user.is_authenticated:
            cart = Cart.objects.filter(user=request.user).order_by("-updated_at").first()
            if not cart:
                cart = Cart.objects.create(user=request.user)
            # If session cart exists and belongs to a guest, merge it into user's cart
            if request.session.session_key:
                guest_cart = Cart.objects.filter(
                    session_key=request.session.session_key,
                    user__isnull=True,
                ).first()
                if guest_cart and guest_cart.id != cart.id:
                    CartService.merge_carts(guest_cart, cart)
        else:
            if not request.session.session_key:
                request.session.save()
            cart = Cart.objects.filter(session_key=request.session.session_key).order_by("-updated_at").first()
            if not cart:
                cart = Cart.objects.create(session_key=request.session.session_key)

        cart.recalculate()
        return cart

    @staticmethod
    def merge_carts(source_cart: Cart, target_cart: Cart) -> None:
        """
        Merges guest cart items into user's account cart upon login.
        """
        for item in source_cart.items.all():
            item.cart = target_cart
            item.save()
        if source_cart.coupon and not target_cart.coupon:
            target_cart.coupon = source_cart.coupon
            target_cart.save()
        source_cart.delete()
        target_cart.recalculate()

    @staticmethod
    def add_item(
        cart: Cart,
        product: Product,
        quantity: int = 1,
        option_value_ids: list[int] | None = None,
        artwork_file: Any = None,
        design_later: bool = False,
        request_proof: bool = False,
        notes: str = "",
    ) -> CartItem:
        """
        Adds a new product line item to the cart with verified server-side calculations.
        """
        if quantity <= 0:
            quantity = 1
        if not product.is_active:
            raise ValueError(str(_("La variante seleccionada no está disponible.")))
        tracks_inventory = product.tracks_inventory
        if tracks_inventory and not product.in_stock:
            raise ValueError(str(_("Esta variante está agotada.")))
        if product.base_price <= 0 and not product.quantity_tiers.exists():
            raise ValueError(str(_("Esta variante aún no tiene un precio publicado.")))
        option_value_ids = option_value_ids or []
        option_values = list(ProductOptionValue.objects.filter(id__in=option_value_ids, group__product=product))
        options_dict = {ov.group.name: ov.name for ov in option_values}
        current_quantity = cart.items.filter(product=product).aggregate(total=Sum("quantity"))["total"] or 0
        if tracks_inventory and current_quantity + quantity > product.stock:
            raise ValueError(str(_("La cantidad solicitada supera el stock disponible de esta variante.")))

        if (
            not product.is_configurable
            and not option_values
            and not artwork_file
            and not design_later
            and not request_proof
            and not notes
        ):
            existing_item = cart.items.filter(product=product).first()
            if existing_item:
                existing_item.quantity += quantity
                existing_item.save(update_fields=["quantity", "updated_at"])
                existing_item.recalculate_price()
                cart.recalculate()
                return existing_item

        cart_item = CartItem.objects.create(
            cart=cart,
            product=product,
            quantity=quantity,
            selected_options=options_dict,
            artwork_file=artwork_file,
            design_later=design_later,
            request_proof=request_proof,
            notes=notes,
        )
        if option_values:
            cart_item.option_values.set(option_values)

        cart_item.recalculate_price()
        cart.recalculate()
        return cart_item

    @staticmethod
    def update_quantity(cart_item_id: int, quantity: int, cart: Cart) -> CartItem | None:
        """Updates line item quantity and verifies stock."""
        try:
            item = cart.items.get(id=cart_item_id)
        except CartItem.DoesNotExist:
            return None

        if quantity <= 0:
            item.delete()
            cart.recalculate()
            return None

        tracks_inventory = item.product.tracks_inventory
        if tracks_inventory:
            other_quantity = (
                cart.items.filter(product=item.product).exclude(pk=item.pk).aggregate(total=Sum("quantity"))["total"]
                or 0
            )
            available_quantity = item.product.stock - other_quantity
            if available_quantity <= 0:
                item.delete()
                cart.recalculate()
                return None
            quantity = min(quantity, available_quantity)

        item.quantity = quantity
        item.save()
        item.recalculate_price()
        cart.recalculate()
        return item

    @staticmethod
    def duplicate_item(cart_item_id: int, cart: Cart) -> CartItem | None:
        """Duplicates an item along with its selected configuration."""
        try:
            item = cart.items.get(id=cart_item_id)
        except CartItem.DoesNotExist:
            return None
        if item.product.tracks_inventory:
            current_quantity = cart.items.filter(product=item.product).aggregate(total=Sum("quantity"))["total"] or 0
            if current_quantity + item.quantity > item.product.stock:
                return None

        new_item = CartItem.objects.create(
            cart=cart,
            product=item.product,
            quantity=item.quantity,
            selected_options=item.selected_options,
            design_later=item.design_later,
            request_proof=item.request_proof,
            proof_price=item.proof_price,
            notes=item.notes,
        )
        new_item.option_values.set(item.option_values.all())
        new_item.recalculate_price()
        cart.recalculate()
        return new_item

    @staticmethod
    def remove_item(cart_item_id: int, cart: Cart) -> bool:
        """Removes a line item from the cart."""
        deleted_count, _ = cart.items.filter(id=cart_item_id).delete()
        if deleted_count > 0:
            cart.recalculate()
            return True
        return False

    @staticmethod
    def apply_coupon(cart: Cart, code: str) -> tuple[bool, str]:
        """Applies a coupon code to the cart if valid."""
        clean_code = code.strip().upper()
        try:
            coupon = Coupon.objects.get(code=clean_code, is_active=True)
        except Coupon.DoesNotExist:
            return False, _("El cupón '%(code)s' no existe o no es válido.") % {"code": clean_code}

        is_valid, msg = coupon.is_valid(cart.subtotal)
        if not is_valid:
            return False, msg

        cart.coupon = coupon
        cart.save(update_fields=["coupon"])
        cart.recalculate()
        return True, _("Cupón '%(code)s' aplicado correctamente.") % {"code": clean_code}

    @staticmethod
    def remove_coupon(cart: Cart) -> None:
        """Removes the applied coupon from the cart."""
        cart.coupon = None
        cart.save(update_fields=["coupon"])
        cart.recalculate()

    @staticmethod
    def set_shipping(cart: Cart, method_id: int, postal_code: str = "") -> bool:
        """Sets the selected shipping method on the cart."""
        try:
            method = ShippingMethod.objects.get(id=method_id, is_active=True)
            cart.shipping_method = method
            if postal_code:
                cart.shipping_postal_code = postal_code.strip()
            cart.save(update_fields=["shipping_method", "shipping_postal_code"])
            cart.recalculate()
            return True
        except ShippingMethod.DoesNotExist:
            return False
