"""
Tests for apps.orders — checkout (sin Stripe), invoice PDF, confirmation, gateways.
"""
from decimal import Decimal

from django.test import TestCase, Client, override_settings
from django.urls import reverse

from apps.catalog.models import Category, Product
from apps.cart.models import Cart, CartItem, ShippingMethod, ShippingZone
from apps.orders.models import Invoice, Order, OrderItem
from apps.orders.pdf import generate_invoice_pdf
from apps.orders.services import CheckoutValidationError, copy_cart_items_to_order, validate_checkout_payload
from apps.payments.models import Payment


def make_product(name="Test Folleto A5", sku="TEST-001", price="1.00"):
    cat, _ = Category.objects.get_or_create(
        slug="test",
        defaults={"name": "Test", "business_area": "impresion"},
    )
    return Product.objects.create(
        category=cat,
        name=name,
        slug=sku.lower(),
        sku=sku,
        short_description="Producto de prueba para tests de checkout.",
        description="Descripción completa del producto de prueba Tintora.",
        base_price=Decimal(price),
        business_area="impresion",
        is_active=True,
        is_featured=False,
    )


def make_shipping_zone():
    zone, _ = ShippingZone.objects.get_or_create(
        code=ShippingZone.ZoneCode.PENINSULA,
        defaults={"name": "Zona Test", "is_active": True},
    )
    method, _ = ShippingMethod.objects.get_or_create(
        zone=zone,
        name="Envío Test",
        defaults={
            "courier": ShippingMethod.Courier.SEUR,
            "base_rate": Decimal("3.90"),
            "estimated_days": "24/48h",
            "is_active": True,
        },
    )
    return zone, method


CHECKOUT_FORM_DATA = {
    "customer_type": "individual",
    "first_name": "María",
    "last_name": "García Rodríguez",
    "email": "maria@test.es",
    "phone": "+34 612 345 678",
    "nif_cif": "12345678Z",
    "company_name": "",
    "shipping_address_line1": "Calle Gran Vía 1",
    "shipping_address_line2": "3º A",
    "shipping_postal_code": "28013",
    "shipping_city": "Madrid",
    "shipping_province": "Madrid",
    "payment_method": "transfer",
    "customer_notes": "Dejar en conserjería.",
}


class OrderModelTestCase(TestCase):
    def setUp(self):
        self.product = make_product()

    def _make_order(self, **kwargs):
        defaults = dict(
            order_number="TIN-2026-0001",
            first_name="Luis",
            last_name="Martínez",
            email="luis@test.es",
            phone="+34 611 000 000",
            nif_cif="B12345678",
            shipping_address_line1="Calle Mayor 5",
            shipping_postal_code="28001",
            shipping_city="Madrid",
            shipping_method_name="SEUR 24h",
            courier="SEUR",
            payment_method=Order.PaymentMethod.TRANSFER,
            subtotal=Decimal("100.00"),
            taxable_base=Decimal("82.64"),
            iva_amount=Decimal("17.36"),
            total=Decimal("100.00"),
        )
        defaults.update(kwargs)
        return Order.objects.create(**defaults)

    def test_order_number_format(self):
        order = self._make_order()
        self.assertTrue(order.order_number.startswith("TIN-"))
        self.assertEqual(len(order.order_number.split("-")), 3)

    def test_full_name_individual(self):
        order = self._make_order(
            order_number="TIN-2026-0002",
            customer_type=Order.CustomerType.INDIVIDUAL,
            first_name="Ana",
            last_name="López",
        )
        self.assertEqual(order.full_name, "Ana López")

    def test_full_name_business(self):
        order = self._make_order(
            order_number="TIN-2026-0003",
            customer_type=Order.CustomerType.BUSINESS,
            first_name="Carlos",
            last_name="Sáenz",
            company_name="Imprenta S.L.",
        )
        self.assertIn("Imprenta S.L.", order.full_name)

    def test_is_paid_property(self):
        order = self._make_order(order_number="TIN-2026-0004")
        self.assertFalse(order.is_paid)
        order.payment_status = Order.PaymentStatus.PAID
        order.save()
        self.assertTrue(order.is_paid)

    def test_order_item_snapshots_selected_variant_and_price(self):
        variant = Product.objects.create(
            category=self.product.category,
            business_area=self.product.business_area,
            parent_product=self.product,
            variant_label="500 g",
            name=self.product.name,
            slug="test-folleto-a5-500-g",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("3.25"),
            stock=6,
            sku=None,
        )
        cart = Cart.objects.create(session_key="variant-order-session")
        cart_item = CartItem.objects.create(cart=cart, product=variant, quantity=2)
        cart_item.recalculate_price()
        order = self._make_order(order_number="TIN-2026-0099")

        copy_cart_items_to_order(order, cart)

        item = order.items.get()
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.variant_label, "500 g")
        self.assertEqual(item.unit_price, Decimal("3.25"))
        self.assertEqual(item.line_total, Decimal("6.50"))
        self.assertEqual(item.product_sku, "")

    def test_checkout_rejects_variant_that_went_out_of_stock(self):
        variant = Product.objects.create(
            category=self.product.category,
            business_area=self.product.business_area,
            parent_product=self.product,
            variant_label="500 g",
            name=self.product.name,
            slug="test-folleto-a5-out-of-stock",
            short_description=self.product.short_description,
            description=self.product.description,
            base_price=Decimal("3.25"),
            stock=0,
            sku=None,
        )
        cart = Cart.objects.create(session_key="out-of-stock-variant-session")
        CartItem.objects.create(cart=cart, product=variant, quantity=1)
        with self.assertRaises(CheckoutValidationError):
            validate_checkout_payload({}, cart)

    def test_invoice_sequential_numbering(self):
        order1 = self._make_order(order_number="TIN-2026-0010")
        order2 = self._make_order(order_number="TIN-2026-0011")
        inv1 = Invoice.objects.create(
            invoice_number=Invoice.generate_next_number(),
            order=order1,
            taxable_base=Decimal("82.64"),
            iva_amount=Decimal("17.36"),
            total=Decimal("100.00"),
        )
        inv2 = Invoice.objects.create(
            invoice_number=Invoice.generate_next_number(),
            order=order2,
            taxable_base=Decimal("82.64"),
            iva_amount=Decimal("17.36"),
            total=Decimal("100.00"),
        )
        self.assertNotEqual(inv1.invoice_number, inv2.invoice_number)
        seq1 = int(inv1.invoice_number.split("-")[-1])
        seq2 = int(inv2.invoice_number.split("-")[-1])
        self.assertEqual(seq2, seq1 + 1)


@override_settings(
    PAYMENTS_STRIPE_ENABLED=False,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="Tintora <hola@tintora.es>",
)
class CheckoutProcessViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.product = make_product()
        _, self.shipping_method = make_shipping_zone()

    def test_checkout_page_empty_cart_redirects(self):
        url = reverse("orders:checkout")
        response = self.client.get(url, follow=False)
        self.assertEqual(response.status_code, 302)

    def test_checkout_page_renders_with_cart(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 10})
        response = self.client.get(reverse("orders:checkout"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'value="stripe"')
        self.assertContains(response, 'value="transfer"')

    def test_checkout_process_creates_order_and_invoice(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 100})

        data = dict(CHECKOUT_FORM_DATA)
        data["shipping_method_id"] = str(self.shipping_method.id)
        data["payment_method"] = "bizum"
        process_url = reverse("orders:checkout_process")
        response = self.client.post(process_url, data, follow=True)

        self.assertEqual(response.status_code, 200)
        orders = Order.objects.all()
        self.assertEqual(orders.count(), 1)
        order = orders.first()
        self.assertEqual(order.email, "maria@test.es")
        self.assertEqual(order.payment_method, "bizum")
        self.assertTrue(hasattr(order, "invoice"))
        self.assertTrue(order.invoice.invoice_number.startswith("FAC-"))
        payment = Payment.objects.filter(order=order).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.COMPLETED)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PAID)

    def test_checkout_rejects_stripe_while_disabled(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 10})
        data = dict(CHECKOUT_FORM_DATA)
        data["payment_method"] = "stripe"
        response = self.client.post(reverse("orders:checkout_process"), data, follow=True)
        self.assertRedirects(response, reverse("orders:checkout"))
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_process_missing_nif_redirects(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 10})
        bad_data = dict(CHECKOUT_FORM_DATA)
        bad_data["nif_cif"] = ""
        response = self.client.post(reverse("orders:checkout_process"), bad_data, follow=True)
        self.assertRedirects(response, reverse("orders:checkout"))

    def test_checkout_transfer_payment_pending(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 10})
        data = dict(CHECKOUT_FORM_DATA)
        data["payment_method"] = "transfer"
        self.client.post(reverse("orders:checkout_process"), data)
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertEqual(order.payment_status, Order.PaymentStatus.PENDING)
        self.assertTrue(hasattr(order, "invoice"))

    def test_order_items_copy_from_cart(self):
        add_url = reverse("cart:add", kwargs={"slug": self.product.slug})
        self.client.post(add_url, {"quantity": 500})
        self.client.post(reverse("orders:checkout_process"), CHECKOUT_FORM_DATA)
        order = Order.objects.first()
        self.assertEqual(order.items.count(), 1)
        item = order.items.first()
        self.assertEqual(item.product_name, self.product.name)
        self.assertEqual(item.quantity, 500)


class OrderConfirmationViewTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.order = Order.objects.create(
            order_number="TIN-2026-9999",
            first_name="Pedro",
            last_name="Alonso",
            email="pedro@test.es",
            phone="+34 600 000 001",
            nif_cif="87654321B",
            shipping_address_line1="Av. de la Castellana 100",
            shipping_postal_code="28046",
            shipping_city="Madrid",
            shipping_method_name="GLS 24h",
            courier="GLS",
            payment_method=Order.PaymentMethod.BIZUM,
            payment_status=Order.PaymentStatus.PAID,
            subtotal=Decimal("250.00"),
            taxable_base=Decimal("206.61"),
            iva_amount=Decimal("43.39"),
            total=Decimal("250.00"),
        )
        self.invoice = Invoice.objects.create(
            invoice_number="FAC-2026-9999",
            order=self.order,
            taxable_base=self.order.taxable_base,
            iva_amount=self.order.iva_amount,
            total=self.order.total,
        )

    def test_confirmation_with_token(self):
        url = reverse("orders:confirmation", kwargs={"order_number": self.order.order_number})
        response = self.client.get(url, {"token": str(self.order.access_token)})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "TIN-2026-9999")

    def test_confirmation_denied_without_access(self):
        url = reverse("orders:confirmation", kwargs={"order_number": self.order.order_number})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_invoice_download_with_token(self):
        url = reverse("orders:download_invoice", kwargs={"order_number": self.order.order_number})
        response = self.client.get(url, {"token": str(self.order.access_token)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")


class InvoicePDFTestCase(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            order_number="TIN-2026-PDF1",
            first_name="Jorge",
            last_name="Blanco",
            email="jorge@test.es",
            phone="+34 600 123 456",
            nif_cif="X1234567A",
            shipping_address_line1="Gran Vía 28",
            shipping_postal_code="28013",
            shipping_city="Madrid",
            shipping_method_name="MRW 24h",
            courier="MRW",
            payment_method=Order.PaymentMethod.TRANSFER,
            subtotal=Decimal("500.00"),
            taxable_base=Decimal("413.22"),
            iva_amount=Decimal("86.78"),
            total=Decimal("500.00"),
        )
        self.invoice = Invoice.objects.create(
            invoice_number="FAC-2026-PDF1",
            order=self.order,
            taxable_base=self.order.taxable_base,
            iva_amount=self.order.iva_amount,
            total=self.order.total,
        )

    def test_pdf_generates_and_is_bytes(self):
        pdf_data = generate_invoice_pdf(self.invoice)
        self.assertIsInstance(pdf_data, bytes)
        self.assertTrue(pdf_data.startswith(b"%PDF"))


class PaymentGatewayTestCase(TestCase):
    def setUp(self):
        self.order = Order.objects.create(
            order_number="TIN-2026-GW01",
            first_name="Test",
            last_name="Gateway",
            email="gw@test.es",
            phone="+34 600 000 099",
            nif_cif="99999999R",
            shipping_address_line1="Calle Test 1",
            shipping_postal_code="28001",
            shipping_city="Madrid",
            shipping_method_name="Test Shipping",
            courier="SEUR",
            payment_method=Order.PaymentMethod.TRANSFER,
            subtotal=Decimal("100.00"),
            taxable_base=Decimal("82.64"),
            iva_amount=Decimal("17.36"),
            total=Decimal("100.00"),
        )

    def _mock_request(self):
        from django.test import RequestFactory
        from django.contrib.sessions.middleware import SessionMiddleware

        factory = RequestFactory()
        request = factory.post("/")
        middleware = SessionMiddleware(lambda r: None)
        middleware.process_request(request)
        request.session.save()
        return request

    def test_bizum_marks_paid(self):
        from apps.payments.gateways import get_payment_gateway

        gw = get_payment_gateway("bizum")
        result = gw.process_payment(self.order, self._mock_request())
        self.assertTrue(result.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    def test_transfer_keeps_pending(self):
        from apps.payments.gateways import get_payment_gateway

        gw = get_payment_gateway("transfer")
        result = gw.process_payment(self.order, self._mock_request())
        self.assertTrue(result.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PENDING)
        self.assertIn("IBAN", result.instructions)

    def test_redsys_simulation_marks_paid(self):
        from apps.payments.gateways import get_payment_gateway

        gw = get_payment_gateway("redsys")
        result = gw.process_payment(self.order, self._mock_request())
        self.assertTrue(result.success)
        self.order.refresh_from_db()
        self.assertEqual(self.order.payment_status, Order.PaymentStatus.PAID)

    @override_settings(PAYMENTS_STRIPE_ENABLED=False)
    def test_stripe_gateway_blocked_when_disabled(self):
        from apps.payments.gateways import get_payment_gateway

        with self.assertRaises(ValueError):
            get_payment_gateway("stripe")
