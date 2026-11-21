import time
from decimal import Decimal

from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import CustomUser
from apps.catalog.models import BusinessArea, Category, Product
from .middleware import AdminSecurityMiddleware
from .context import current_actor
from .models import AuditEvent
from .totp import decrypt_totp_secret, encrypt_totp_secret, totp_code, verify_totp


class TotpUtilityTests(TestCase):
    def test_totp_accepts_current_code_and_rejects_invalid_code(self):
        timestamp = 1_700_000_000
        secret = "JBSWY3DPEHPK3PXP"

        self.assertTrue(verify_totp(secret, totp_code(secret, timestamp), timestamp))
        self.assertFalse(verify_totp(secret, "000000", timestamp, window=0))
        self.assertFalse(verify_totp(secret, "12x456", timestamp))

    def test_totp_secret_is_encrypted_at_rest_and_round_trips(self):
        secret = "JBSWY3DPEHPK3PXP"
        stored_value = encrypt_totp_secret(secret)

        self.assertTrue(stored_value.startswith("fernet:v1:"))
        self.assertNotIn(secret, stored_value)
        self.assertEqual(decrypt_totp_secret(stored_value), secret)

    @override_settings(ADMIN_2FA_REQUIRED=True)
    def test_staff_admin_requires_totp_setup_then_challenge(self):
        staff = CustomUser.objects.create_user(
            username="phase7-staff",
            email="staff-phase7@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="orders",
                codename="view_order",
            )
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))
        self.assertRedirects(response, reverse("dashboard:totp_setup"))

        response = self.client.get(reverse("dashboard:totp_setup"))
        self.assertEqual(response.status_code, 200)
        staff.refresh_from_db()
        self.assertTrue(staff.totp_secret.startswith("fernet:v1:"))

        response = self.client.post(
            reverse("dashboard:totp_setup"),
            {"code": "000000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.totp_enabled)

        secret = decrypt_totp_secret(staff.totp_secret)
        response = self.client.post(
            reverse("dashboard:totp_setup"),
            {"code": totp_code(secret)},
        )
        self.assertRedirects(response, reverse("admin:index"))
        staff.refresh_from_db()
        self.assertTrue(staff.totp_enabled)

    @override_settings(ADMIN_2FA_REQUIRED=True)
    def test_staff_with_totp_is_redirected_to_challenge_without_session_proof(self):
        staff = CustomUser.objects.create_user(
            username="phase7-verified-staff",
            email="verified-staff@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
            totp_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_enabled=True,
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("next=%2Fgestion-tintora%2F", response["Location"])

    @override_settings(ADMIN_2FA_REQUIRED=False)
    def test_two_factor_can_be_disabled_for_staff_without_totp(self):
        staff = CustomUser.objects.create_user(
            username="no-totp-staff",
            email="no-totp@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(
                content_type__app_label="dashboard",
                codename="view_adminanalytics",
            )
        )
        self.client.force_login(staff)

        response = self.client.get(reverse("admin:index"))

        # Without the requirement, staff reach the admin directly (no TOTP
        # setup/challenge redirect) while the account stays non-TOTP.
        self.assertEqual(response.status_code, 200)
        staff.refresh_from_db()
        self.assertFalse(staff.totp_enabled)
        self.assertEqual(staff.totp_secret, "")

    def test_totp_challenge_throttles_repeated_invalid_codes(self):
        staff = CustomUser.objects.create_user(
            username="throttled-staff",
            email="throttled@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
            totp_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_enabled=True,
        )
        self.client.force_login(staff)
        url = reverse("dashboard:totp_challenge")

        for _ in range(5):
            response = self.client.post(url, {"code": "000000"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {"code": "000000"})
        self.assertEqual(response.status_code, 429)

    def test_totp_challenge_rejects_external_return_urls(self):
        staff = CustomUser.objects.create_user(
            username="safe-redirect-staff",
            email="safe-redirect@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
            totp_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_enabled=True,
        )
        staff.user_permissions.add(
            Permission.objects.get(content_type__app_label="orders", codename="view_order")
        )
        self.client.force_login(staff)
        url = f"{reverse('dashboard:totp_challenge')}?next=https://attacker.invalid/"

        response = self.client.post(url, {"code": totp_code("JBSWY3DPEHPK3PXP")})

        self.assertRedirects(response, reverse("admin:index"))

    @override_settings(ADMIN_ALLOWED_IPS=["192.0.2.0/24"])
    def test_admin_ip_allowlist_blocks_unapproved_network(self):
        request = RequestFactory().get("/gestion-tintora/")
        request.META["REMOTE_ADDR"] = "198.51.100.20"
        middleware = AdminSecurityMiddleware(lambda req: None)

        response = middleware(request)

        self.assertEqual(response.status_code, 403)


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.staff = CustomUser.objects.create_user(
            username="analytics-staff",
            email="analytics@example.es",
            password="SecureStaffPassword123!",
            is_staff=True,
            is_verified=True,
            totp_secret=encrypt_totp_secret("JBSWY3DPEHPK3PXP"),
            totp_enabled=True,
        )
        self.client.force_login(self.staff)
        session = self.client.session
        session[AdminSecurityMiddleware.session_key] = int(time.time()) + 600
        session[AdminSecurityMiddleware.activity_key] = int(time.time())
        session.save()

    def test_analytics_dashboard_requires_permission(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 403)

    def test_analytics_permission_shows_dashboard_metrics(self):
        permission = Permission.objects.get(
            content_type__app_label="dashboard",
            codename="view_adminanalytics",
        )
        self.staff.user_permissions.add(permission)
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resumen del taller y la tienda")
        self.assertContains(response, "Ingresos · últimos 14 días")

    def test_model_changes_create_audit_event_with_actor_and_field_names(self):
        category = Category.objects.create(
            name="Auditoría",
            slug="audit-category-phase7",
            business_area=BusinessArea.IMPRESION,
        )
        actor_token = current_actor.set(self.staff)
        try:
            product = Product.objects.create(
                category=category,
                business_area=BusinessArea.IMPRESION,
                name="Producto auditado",
                slug="audited-product-phase7",
                sku="AUDIT-PHASE7-01",
                short_description="Producto de prueba de auditoría",
                description="Registro para comprobar que los cambios quedan auditados.",
                base_price=Decimal("5.00"),
            )

            event = AuditEvent.objects.filter(object_pk=str(product.pk)).latest("created_at")
            self.assertEqual(event.action, AuditEvent.Action.CREATED)
            self.assertEqual(event.actor, self.staff)
            self.assertIn("base_price", event.changed_fields)

            product.name = "Producto actualizado"
            product.save()
            update_event = AuditEvent.objects.filter(object_pk=str(product.pk)).latest("created_at")
            self.assertEqual(update_event.action, AuditEvent.Action.UPDATED)
            self.assertIn("name", update_event.changed_fields)
            self.assertNotIn("Producto actualizado", str(update_event.changed_fields))
        finally:
            current_actor.reset(actor_token)


class StaffRoleCommandTests(TestCase):
    def test_role_command_creates_expected_groups(self):
        from django.core.management import call_command

        call_command("setup_staff_roles", verbosity=0)

        self.assertTrue(Group.objects.filter(name="Super Admin").exists())
        self.assertTrue(Group.objects.filter(name="Manager").exists())
        self.assertTrue(Group.objects.filter(name="Production").exists())
        self.assertTrue(Group.objects.filter(name="Support").exists())
        self.assertTrue(Group.objects.filter(name="Content Editor").exists())