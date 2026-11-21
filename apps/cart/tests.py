from decimal import Decimal
from django.test import Client, TestCase
from django.utils import timezone

from apps.accounts.models import CustomUser
from apps.catalog.models import (
    BusinessArea,
    Category,
    Product,
    ProductOptionGroup,
    ProductOptionValue,
    QuantityTierPrice,
)
from .models import Cart, CartItem, Coupon, ShippingMethod, ShippingZone
from .services import CartService


class CartModelsTestCase(TestCase):
    def setUp(self):
        self.category = Category.objects.create(
            name="Tarjetas de Visita",
            slug="tarjetas-de-visita-test",
            business_area=BusinessArea.IMPRESION,
        )
        self.product = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            name="Tarjetas Offset Premium",
            slug="tarjetas-offset-premium",
            sku="TIN-TEST-CART-1",
            short_description="Tarjetas en papel verjurado",
            description="Descripción técnica",
            base_price=Decimal("30.00"),
            iva_percentage=Decimal("21.0"),
            is_configurable=True,
            allows_proof=True,
        )
        self.tier = QuantityTierPrice.objects.create(
            product=self.product,
            min_quantity=500,
            unit_price=Decimal("0.1000"),
            total_price=Decimal("50.00"),
        )
        self.opt_group = ProductOptionGroup.objects.create(
            product=self.product,
            name="Plastificado",
            code="plastificado",
        )
        self.opt_val = ProductOptionValue.objects.create(
            group=self.opt_group,
            name="Soft Touch Mate",
            price_modifier=Decimal("8.00"),
        )

        self.zone_madrid = ShippingZone.objects.create(
            code=ShippingZone.ZoneCode.MADRID_LOCAL,
            name="Madrid Local",
            order=1,
        )
        self.shipping_seur = ShippingMethod.objects.create(
            zone=self.zone_madrid,
            courier=ShippingMethod.Courier.SEUR,
            name="SEUR 24h Madrid",
            base_rate=Decimal("3.90"),
            free_threshold=Decimal("50.00"),
        )
        self.shipping_pickup = ShippingMethod.objects.create(
            zone=self.zone_madrid,
            courier=ShippingMethod.Courier.PICKUP,
            name="Recogida en Atocha 45",
            base_rate=Decimal("0.00"),
        )

        self.coupon_percent = Coupon.objects.create(
            code="MADRID10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            min_spend=Decimal("30.00"),
        )

    def test_cart_item_server_side_calculation(self):
        cart = Cart.objects.create(session_key="test-session-1")
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=500,
            request_proof=True,
            proof_price=Decimal("12.00"),
        )
        item.option_values.add(self.opt_val)
        item.recalculate_price()

        # 50.00 (tier 500) + 8.00 (soft touch) + 12.00 (proof) = 70.00€
        self.assertEqual(item.line_total, Decimal("70.00"))
        # 70.00 / 500 = 0.1400€/ud
        self.assertEqual(item.unit_price, Decimal("0.1400"))
        self.assertEqual(item.artwork_status, CartItem.ArtworkStatus.PROOF_REQUESTED)

    def test_cart_totals_and_iva_breakdown(self):
        cart = Cart.objects.create(session_key="test-session-2")
        item = CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=100,  # Below 500 -> base_price 30.00€
            line_total=Decimal("30.00"),
            unit_price=Decimal("0.3000"),
        )
        cart.shipping_method = self.shipping_seur
        cart.coupon = self.coupon_percent
        cart.save()

        # Subtotal: 30.00€
        self.assertEqual(cart.subtotal, Decimal("30.00"))
        # Discount 10% on 30.00 = 3.00€
        self.assertEqual(cart.discount_amount, Decimal("3.00"))
        # Shipping: 3.90€ (subtotal 30.00 < 50.00 free threshold)
        self.assertEqual(cart.shipping_cost, Decimal("3.90"))
        # Total: 30.00 - 3.00 + 3.90 = 30.90€
        self.assertEqual(cart.total, Decimal("30.90"))

        # Base imponible: 30.90 / 1.21 = 25.54€
        self.assertEqual(cart.taxable_base, Decimal("25.54"))
        # Cuota IVA: 30.90 - 25.54 = 5.36€
        self.assertEqual(cart.iva_amount, Decimal("5.36"))

    def test_free_shipping_threshold(self):
        cart = Cart.objects.create(session_key="test-session-3")
        CartItem.objects.create(
            cart=cart,
            product=self.product,
            quantity=500,
            line_total=Decimal("60.00"),  # Above 50.00€
            unit_price=Decimal("0.1200"),
        )
        cart.shipping_method = self.shipping_seur
        self.assertEqual(cart.shipping_cost, Decimal("0.00"))


class CartViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.category = Category.objects.create(
            name="Papelería Corporativa",
            slug="papeleria-corporativa",
            business_area=BusinessArea.IMPRESION,
        )
        self.product = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            name="Sobres Impresos Premium",
            slug="sobres-impresos-premium",
            sku="TIN-TEST-ENV-1",
            short_description="Sobres con logotipo",
            description="Sobres en papel verjurado de autor.",
            base_price=Decimal("40.00"),
            iva_percentage=Decimal("21.0"),
            is_active=True,
            is_configurable=True,
            allows_proof=True,
        )
        self.zone = ShippingZone.objects.create(
            code=ShippingZone.ZoneCode.MADRID_LOCAL,
            name="Madrid Local",
        )
        self.method = ShippingMethod.objects.create(
            zone=self.zone,
            courier=ShippingMethod.Courier.PICKUP,
            name="Recogida en taller",
            base_rate=Decimal("0.00"),
        )
        self.coupon = Coupon.objects.create(
            code="MADRID10",
            discount_type=Coupon.DiscountType.PERCENTAGE,
            discount_value=Decimal("10.00"),
            min_spend=Decimal("20.00"),
            is_active=True,
        )

    def test_cart_detail_empty(self):
        response = self.client.get("/es/carrito/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tu cesta de compra está vacía")
        self.assertContains(response, "Explorar Catálogo")

    def test_cart_add_item_post(self):
        response = self.client.post(
            f"/es/carrito/anadir/{self.product.slug}/",
            data={
                "quantity": 2,
                "design_later": "true",
            },
        )
        self.assertRedirects(response, "/es/carrito/")

        # Verify cart now contains the item
        cart_response = self.client.get("/es/carrito/")
        self.assertEqual(cart_response.status_code, 200)
        self.assertContains(cart_response, "Sobres Impresos Premium")
        self.assertContains(cart_response, "Diseñar / enviar más tarde")

    def test_selected_size_variants_have_independent_cart_lines_and_stock(self):
        small = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            parent_product=self.product,
            variant_label="250 g",
            name=self.product.name,
            slug="sobres-250-g",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("3.00"),
            stock=2,
            sku=None,
        )
        large = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            parent_product=self.product,
            variant_label="500 g",
            name=self.product.name,
            slug="sobres-500-g",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("5.00"),
            stock=5,
            sku=None,
        )
        add_url = f"/es/carrito/anadir/{self.product.slug}/"

        self.client.post(add_url, {"variant_slug": small.slug, "quantity": 2})
        self.client.post(add_url, {"variant_slug": large.slug, "quantity": 3})
        self.client.post(add_url, {"variant_slug": small.slug, "quantity": 1})

        cart = Cart.objects.first()
        items = {item.product_id: item for item in cart.items.select_related("product")}
        self.assertEqual(len(items), 2)
        self.assertEqual(items[small.pk].quantity, 2)
        self.assertEqual(items[small.pk].line_total, Decimal("6.00"))
        self.assertEqual(items[large.pk].line_total, Decimal("15.00"))
        self.assertEqual(items[small.pk].product.variant_label, "250 g")

        update_url = f"/es/carrito/actualizar/{items[small.pk].pk}/"
        self.client.post(update_url, {"action": "inc"}, HTTP_HX_REQUEST="true")
        items[small.pk].refresh_from_db()
        items[large.pk].refresh_from_db()
        self.assertEqual(items[small.pk].quantity, 2)
        self.assertEqual(items[large.pk].quantity, 3)

        self.client.post(f"/es/carrito/eliminar/{items[small.pk].pk}/", HTTP_HX_REQUEST="true")
        self.assertFalse(cart.items.filter(product=small).exists())
        self.assertTrue(cart.items.filter(product=large).exists())

    def test_selected_variant_stock_limit_is_enforced(self):
        variant = Product.objects.create(
            category=self.category,
            business_area=BusinessArea.IMPRESION,
            parent_product=self.product,
            variant_label="250 g",
            name=self.product.name,
            slug="sobres-stock-limited",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("3.00"),
            stock=1,
            sku=None,
        )
        self.client.post(
            f"/es/carrito/anadir/{self.product.slug}/",
            {"variant_slug": variant.slug, "quantity": 2},
        )
        self.assertFalse(CartItem.objects.filter(product=variant).exists())

    def test_cart_update_quantity_htmx(self):
        # First add product
        self.client.post(f"/es/carrito/anadir/{self.product.slug}/", data={"quantity": 1})
        cart = Cart.objects.first()
        item = cart.items.first()

        # Increment quantity via HTMX
        response = self.client.post(
            f"/es/carrito/actualizar/{item.id}/",
            data={"action": "inc"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

    def test_cart_apply_and_remove_coupon(self):
        self.client.post(f"/es/carrito/anadir/{self.product.slug}/", data={"quantity": 1})

        # Apply valid coupon
        response = self.client.post(
            "/es/carrito/cupon/aplicar/",
            data={"code": "MADRID10"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MADRID10")
        self.assertContains(response, "Descuento aplicado")

        # Remove coupon
        response_del = self.client.post(
            "/es/carrito/cupon/eliminar/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response_del.status_code, 200)
        self.assertNotContains(response_del, "Descuento aplicado")

    def test_cart_duplicate_and_remove_item(self):
        self.client.post(f"/es/carrito/anadir/{self.product.slug}/", data={"quantity": 1})
        cart = Cart.objects.first()
        item = cart.items.first()

        # Duplicate item
        self.client.post(f"/es/carrito/duplicar/{item.id}/")
        self.assertEqual(cart.items.count(), 2)

        # Remove an item
        response = self.client.post(
            f"/es/carrito/eliminar/{item.id}/",
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="header-cart-badge"')
        self.assertContains(response, 'hx-swap-oob="true"')
        self.assertEqual(cart.items.count(), 1)

    def test_removing_last_item_hides_header_cart_badge(self):
        self.client.post(f"/es/carrito/anadir/{self.product.slug}/", data={"quantity": 1})
        cart = Cart.objects.first()
        item = cart.items.first()

        response = self.client.post(
            f"/es/carrito/eliminar/{item.id}/",
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertRegex(
            response.content.decode("utf-8"),
            r'id="header-cart-badge"[^>]*class="[^"]*\bhidden\b[^"]*"[^>]*>0</span>',
        )
