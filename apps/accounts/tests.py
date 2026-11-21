import json
import tempfile
import zipfile
from decimal import Decimal
from io import BytesIO

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core import mail
from django.test import TestCase
from django.urls import reverse

from apps.cart.models import Cart
from apps.catalog.models import BusinessArea, Category, Product, ProductOptionGroup, ProductOptionValue
from .emails import make_email_verification_token
from .models import CustomUser, SavedAddress
from apps.orders.models import Invoice, Order, OrderItem


class AccountsModelTestCase(TestCase):
    def test_create_individual_user(self):
        user = CustomUser.objects.create_user(
            username="carlos_madrid",
            email="carlos@madrid.es",
            password="Password123!",
            first_name="Carlos",
            last_name="Sanz",
            customer_type=CustomUser.CustomerType.INDIVIDUAL,
            nif_cif="50123456Z",
        )
        self.assertEqual(user.email, "carlos@madrid.es")
        self.assertEqual(user.customer_type, CustomUser.CustomerType.INDIVIDUAL)
        self.assertIn("Carlos Sanz", str(user))

    def test_create_business_user(self):
        user = CustomUser.objects.create_user(
            username="estudio_grafico",
            email="hola@estudiografico.es",
            password="Password123!",
            customer_type=CustomUser.CustomerType.BUSINESS,
            company_name="Estudio Gráfico SL",
            nif_cif="B-88990011",
        )
        self.assertEqual(user.customer_type, CustomUser.CustomerType.BUSINESS)
        self.assertEqual(user.company_name, "Estudio Gráfico SL")
        self.assertIn("Estudio Gráfico SL", str(user))


class CustomerProofActionTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="proof-customer",
            email="cliente@example.es",
            password="SecurePassword123!",
        )
        self.order = Order.objects.create(
            order_number="TIN-2026-9001",
            user=self.user,
            email=self.user.email,
            first_name="Ana",
            last_name="López",
            phone="+34910000000",
            shipping_address_line1="Calle de Atocha 45",
            shipping_postal_code="28012",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("24.20"),
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product_name="Tarjetas de visita",
            product_sku="TAR-001",
            quantity=1,
            unit_price=Decimal("24.20"),
            line_total=Decimal("24.20"),
            request_proof=True,
            proof_status=OrderItem.ProofStatus.SENT,
        )
        self.client.force_login(self.user)

    def test_proof_actions_reject_get_requests(self):
        for action in ("approve_proof", "reject_proof"):
            response = self.client.get(
                reverse(
                    f"customer:{action}",
                    kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
                )
            )
            self.assertEqual(response.status_code, 405)

        self.item.refresh_from_db()
        self.assertEqual(self.item.proof_status, OrderItem.ProofStatus.SENT)

    def test_customer_can_approve_sent_proof_with_post(self):
        response = self.client.post(
            reverse(
                "customer:approve_proof",
                kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
            )
        )

        self.assertRedirects(response, reverse("customer:order_detail", args=[self.order.order_number]))
        self.item.refresh_from_db()
        self.assertEqual(self.item.proof_status, OrderItem.ProofStatus.APPROVED)

    def test_customer_rejection_requires_and_persists_feedback(self):
        url = reverse(
            "customer:reject_proof",
            kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
        )
        response = self.client.post(url, {"proof_feedback": "  "})
        self.assertRedirects(response, reverse("customer:order_detail", args=[self.order.order_number]))
        self.item.refresh_from_db()
        self.assertEqual(self.item.proof_status, OrderItem.ProofStatus.SENT)

        self.client.post(url, {"proof_feedback": "Ajustar el margen superior."})
        self.item.refresh_from_db()
        self.assertEqual(self.item.proof_status, OrderItem.ProofStatus.REJECTED)
        self.assertEqual(self.item.proof_feedback, "Ajustar el margen superior.")

    def test_customer_cannot_change_another_customers_proof(self):
        another_user = CustomUser.objects.create_user(
            username="other-customer",
            email="otra@example.es",
            password="SecurePassword123!",
        )
        self.client.force_login(another_user)
        response = self.client.post(
            reverse(
                "customer:approve_proof",
                kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
            )
        )

        self.assertEqual(response.status_code, 404)
        self.item.refresh_from_db()
        self.assertEqual(self.item.proof_status, OrderItem.ProofStatus.SENT)


class CustomerPrivacyFlowTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="privacy-customer",
            email="privacidad@example.es",
            password="SecurePassword123!",
            first_name="María",
            last_name="García",
        )
        self.order = Order.objects.create(
            order_number="TIN-2026-9101",
            user=self.user,
            email=self.user.email,
            first_name=self.user.first_name,
            last_name=self.user.last_name,
            phone="+34910000000",
            nif_cif="12345678Z",
            shipping_address_line1="Calle de Atocha 45",
            shipping_postal_code="28012",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("24.20"),
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product_name="Tarjetas de visita",
            product_sku="TAR-001",
            quantity=1,
            unit_price=Decimal("24.20"),
            line_total=Decimal("24.20"),
        )
        self.client.force_login(self.user)

    def test_privacy_page_links_to_real_export_and_deletion_actions(self):
        response = self.client.get(reverse("customer:privacy"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("customer:data_export"))
        self.assertContains(response, reverse("customer:delete_account"))
        self.assertContains(response, "Descargar mis datos")
        self.assertContains(response, "Escribe ELIMINAR para confirmar")

    def test_export_download_contains_order_data_and_uploaded_artwork(self):
        Cart.objects.create(user=self.user)
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.item.artwork_file.save("original.pdf", ContentFile(b"print-ready artwork"), save=True)
                response = self.client.post(reverse("customer:data_export"))

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response["Content-Type"], "application/zip")
                archive_bytes = b"".join(response.streaming_content)

        with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
            payload = json.loads(archive.read("datos.json"))
            self.assertEqual(payload["account"]["email"], self.user.email)
            self.assertEqual(payload["orders"][0]["order_number"], self.order.order_number)
            self.assertEqual(payload["orders"][0]["customer"]["nif_cif"], "12345678Z")
            self.assertEqual(payload["carts"][0]["total"], "0.00")
            artwork_path = payload["orders"][0]["items"][0]["artwork_file"]
            self.assertEqual(archive.read(artwork_path), b"print-ready artwork")

    def test_customer_can_download_own_artwork(self):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.item.artwork_file.save("original.pdf", ContentFile(b"customer artwork"), save=True)
                response = self.client.get(
                    reverse(
                        "customer:download_customer_file",
                        kwargs={"item_id": self.item.pk, "file_kind": "artwork"},
                    )
                )

                self.assertEqual(response.status_code, 200)
                self.assertIn("original.pdf", response["Content-Disposition"])
                self.assertEqual(b"".join(response.streaming_content), b"customer artwork")

    def test_export_is_post_only(self):
        response = self.client.get(reverse("customer:data_export"))
        self.assertEqual(response.status_code, 405)

    def test_account_deletion_requires_password_and_exact_confirmation(self):
        url = reverse("customer:delete_account")
        response = self.client.post(url, {"password": "wrong", "confirmation": "ELIMINAR"})
        self.assertRedirects(response, reverse("customer:privacy"))
        self.assertTrue(CustomUser.objects.filter(pk=self.user.pk).exists())

        response = self.client.post(
            url,
            {"password": "SecurePassword123!", "confirmation": "eliminar"},
        )
        self.assertRedirects(response, reverse("customer:privacy"))
        self.assertTrue(CustomUser.objects.filter(pk=self.user.pk).exists())

    def test_account_deletion_is_blocked_while_order_is_active(self):
        response = self.client.post(
            reverse("customer:delete_account"),
            {"password": "SecurePassword123!", "confirmation": "ELIMINAR"},
        )

        self.assertRedirects(response, reverse("customer:privacy"))
        self.assertTrue(CustomUser.objects.filter(pk=self.user.pk).exists())
        self.order.refresh_from_db()
        self.assertEqual(self.order.user_id, self.user.pk)

    def test_confirmed_deletion_anonymizes_orders_and_retains_invoice(self):
        self.order.status = Order.Status.ENTREGADO
        self.order.save(update_fields=["status", "updated_at"])
        old_access_token = self.order.access_token
        address = SavedAddress.objects.create(
            user=self.user,
            label="Casa",
            address_line1="Calle de Atocha 45",
            postal_code="28012",
            city="Madrid",
            province="Madrid",
        )
        invoice = Invoice.objects.create(
            invoice_number="TIN-F-2026-9101",
            order=self.order,
            company_data={"name": "Tintora"},
            customer_data={"name": "María García", "nif_cif": "12345678Z"},
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )

        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.item.artwork_file.save("original.pdf", ContentFile(b"private artwork"), save=True)
                artwork_name = self.item.artwork_file.name
                response = self.client.post(
                    reverse("customer:delete_account"),
                    {"password": "SecurePassword123!", "confirmation": "ELIMINAR"},
                )
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "Tu cuenta ha sido eliminada")
                self.assertFalse(self.item.artwork_file.storage.exists(artwork_name))

        self.assertFalse(CustomUser.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(SavedAddress.objects.filter(pk=address.pk).exists())
        self.order.refresh_from_db()
        self.item.refresh_from_db()
        invoice.refresh_from_db()
        self.assertIsNone(self.order.user_id)
        self.assertEqual(self.order.email, f"deleted-{self.order.pk}@privacy.invalid")
        self.assertEqual(self.order.first_name, "Cuenta eliminada")
        self.assertNotEqual(self.order.access_token, old_access_token)
        self.assertFalse(self.item.artwork_file)
        self.assertEqual(invoice.customer_data["name"], "María García")


class CustomerAuthenticationFlowTests(TestCase):
    def test_registration_sends_verification_and_signed_link_activates_account(self):
        response = self.client.post(
            reverse("customer:register"),
            {
                "email": "nuevo@example.es",
                "first_name": "Lucía",
                "last_name": "Vega",
                "customer_type": CustomUser.CustomerType.INDIVIDUAL,
                "password1": "TintoraSecure!2026",
                "password2": "TintoraSecure!2026",
            },
        )

        self.assertEqual(response.status_code, 200)
        user = CustomUser.objects.get(email="nuevo@example.es")
        self.assertFalse(user.is_verified)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("/verificar-email/", mail.outbox[0].body)

        response = self.client.get(
            reverse(
                "customer:verify_email",
                kwargs={"token": make_email_verification_token(user)},
            )
        )
        self.assertRedirects(response, reverse("customer:login"))
        user.refresh_from_db()
        self.assertTrue(user.is_verified)

    def test_unverified_user_cannot_sign_in(self):
        user = CustomUser.objects.create_user(
            username="unverified-user",
            email="pendiente@example.es",
            password="TintoraSecure!2026",
        )

        response = self.client.post(
            reverse("customer:login"),
            {"username": user.email, "password": "TintoraSecure!2026"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirma tu correo electrónico")
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_invalid_verification_token_is_rejected(self):
        response = self.client.get(
            reverse("customer:verify_email", kwargs={"token": "not-a-signed-token"})
        )
        self.assertEqual(response.status_code, 400)

    def test_password_reset_sends_email_for_verified_account(self):
        user = CustomUser.objects.create_user(
            username="reset-user",
            email="reset@example.es",
            password="TintoraSecure!2026",
            is_verified=True,
        )

        response = self.client.post(
            reverse("customer:password_reset"),
            {"email": user.email},
        )

        self.assertRedirects(response, reverse("customer:password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("restablecer-contrasena/", mail.outbox[0].body)


class CustomerArtworkLibraryTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="art-customer",
            email="arte@example.es",
            password="SecurePassword123!",
        )
        self.order = Order.objects.create(
            order_number="TIN-2026-9201",
            user=self.user,
            email=self.user.email,
            first_name="Ana",
            last_name="López",
            phone="+34910000000",
            shipping_address_line1="Calle de Atocha 45",
            shipping_postal_code="28012",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("24.20"),
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )
        self.item = OrderItem.objects.create(
            order=self.order,
            product_name="Tarjetas de visita",
            product_sku="TAR-001",
            unit_price=Decimal("24.20"),
            line_total=Decimal("24.20"),
        )
        self.client.force_login(self.user)

    def test_artwork_upload_page_uses_order_number_route_parameter(self):
        response = self.client.get(
            reverse(
                "customer:upload_artwork",
                kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

    def test_artwork_upload_rejects_unsupported_file_extension(self):
        self.item.artwork_status = OrderItem.ArtworkStatus.DESIGN_LATER
        self.item.save(update_fields=["artwork_status", "updated_at"])
        response = self.client.post(
            reverse(
                "customer:upload_artwork",
                kwargs={"order_number": self.order.order_number, "item_id": self.item.pk},
            ),
            {"artwork_file": SimpleUploadedFile("brief.exe", b"not artwork")},
        )

        self.assertEqual(response.status_code, 200)
        self.item.refresh_from_db()
        self.assertEqual(self.item.artwork_status, OrderItem.ArtworkStatus.DESIGN_LATER)
        self.assertFalse(self.item.artwork_file)

    def test_artwork_library_lists_only_customer_files(self):
        self.item.artwork_file = "artwork/2026/10/ana-original.pdf"
        self.item.save(update_fields=["artwork_file", "updated_at"])
        other_user = CustomUser.objects.create_user(
            username="private-customer",
            email="private@example.es",
            password="SecurePassword123!",
        )
        other_order = Order.objects.create(
            order_number="TIN-2026-9002",
            user=other_user,
            email=other_user.email,
            first_name="Luis",
            last_name="Soto",
            phone="+34910000001",
            shipping_address_line1="Calle Mayor 1",
            shipping_postal_code="28013",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("24.20"),
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )
        OrderItem.objects.create(
            order=other_order,
            product_name="Archivo privado",
            product_sku="PRIV-001",
            unit_price=Decimal("24.20"),
            line_total=Decimal("24.20"),
            artwork_file="artwork/2026/10/private.pdf",
        )

        response = self.client.get(reverse("customer:artwork_library"))

        self.assertContains(response, "Tarjetas de visita")
        self.assertNotContains(response, "Archivo privado")

    def test_artwork_download_does_not_expose_another_customers_file(self):
        other_user = CustomUser.objects.create_user(
            username="private-customer",
            email="private@example.es",
            password="SecurePassword123!",
        )
        other_order = Order.objects.create(
            order_number="TIN-2026-9002",
            user=other_user,
            email=other_user.email,
            first_name="Luis",
            last_name="Soto",
            phone="+34910000001",
            shipping_address_line1="Calle Mayor 1",
            shipping_postal_code="28013",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("24.20"),
            taxable_base=Decimal("20.00"),
            iva_amount=Decimal("4.20"),
            total=Decimal("24.20"),
        )
        other_item = OrderItem.objects.create(
            order=other_order,
            product_name="Archivo privado",
            product_sku="PRIV-001",
            unit_price=Decimal("24.20"),
            line_total=Decimal("24.20"),
            artwork_file="artwork/2026/10/private.pdf",
        )

        response = self.client.get(
            reverse(
                "customer:download_customer_file",
                kwargs={"item_id": other_item.pk, "file_kind": "artwork"},
            )
        )

        self.assertEqual(response.status_code, 404)


class CustomerOrderReorderTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username="reorder-customer",
            email="repetir@example.es",
            password="SecurePassword123!",
        )
        category = Category.objects.create(
            name="Tarjetas",
            slug="tarjetas-reorder-test",
            business_area=BusinessArea.IMPRESION,
        )
        self.product = Product.objects.create(
            category=category,
            business_area=BusinessArea.IMPRESION,
            name="Tarjetas de visita",
            slug="tarjetas-reorder-test-product",
            sku="TAR-REORDER-01",
            short_description="Tarjeta impresa a medida",
            description="Tarjetas de visita para pruebas de repetición.",
            base_price=Decimal("4.50"),
            stock=3,
            is_active=True,
        )
        group = ProductOptionGroup.objects.create(
            product=self.product,
            name="Tamaño",
            code="tamano",
        )
        ProductOptionValue.objects.create(group=group, name="A5", price_modifier=Decimal("2.00"))
        self.order = Order.objects.create(
            order_number="TIN-2026-9301",
            user=self.user,
            email=self.user.email,
            first_name="Ana",
            last_name="López",
            phone="+34910000000",
            shipping_address_line1="Calle de Atocha 45",
            shipping_postal_code="28012",
            shipping_city="Madrid",
            shipping_method_name="Recogida local",
            subtotal=Decimal("32.50"),
            taxable_base=Decimal("26.86"),
            iva_amount=Decimal("5.64"),
            total=Decimal("32.50"),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            product_sku=self.product.sku,
            quantity=5,
            unit_price=Decimal("6.50"),
            line_total=Decimal("32.50"),
            configuration={"Tamaño": "A5"},
        )
        self.client.force_login(self.user)

    def test_reorder_rebuilds_cart_with_current_options_stock_and_price(self):
        response = self.client.post(
            reverse("customer:reorder_order", args=[self.order.order_number])
        )

        self.assertRedirects(response, reverse("cart:detail"))
        cart = Cart.objects.get(user=self.user)
        cart_item = cart.items.get()
        self.assertEqual(cart_item.quantity, 3)
        self.assertEqual(cart_item.selected_options, {"Tamaño": "A5"})
        self.assertEqual(cart_item.line_total, Decimal("15.50"))

    def test_reorder_copies_artwork_into_a_new_cart_file(self):
        with tempfile.TemporaryDirectory() as media_root:
            with self.settings(MEDIA_ROOT=media_root):
                self.order_item.artwork_file.save("original.pdf", ContentFile(b"print artwork"), save=True)
                response = self.client.post(
                    reverse("customer:reorder_order", args=[self.order.order_number])
                )

                self.assertEqual(response.status_code, 302)
                cart_item = Cart.objects.get(user=self.user).items.get()
                self.assertNotEqual(cart_item.artwork_file.name, self.order_item.artwork_file.name)
                with cart_item.artwork_file.open("rb") as stored_artwork:
                    self.assertEqual(stored_artwork.read(), b"print artwork")

    def test_reorder_cannot_access_another_customers_order(self):
        other_user = CustomUser.objects.create_user(
            username="other-reorder-customer",
            email="otra-repetir@example.es",
            password="SecurePassword123!",
        )
        self.client.force_login(other_user)

        response = self.client.post(
            reverse("customer:reorder_order", args=[self.order.order_number])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Cart.objects.filter(user=other_user).exists())

    def test_reorder_rejects_get(self):
        response = self.client.get(
            reverse("customer:reorder_order", args=[self.order.order_number])
        )
        self.assertEqual(response.status_code, 405)
