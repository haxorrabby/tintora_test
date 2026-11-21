from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import QuoteRequest, WebPackage, WebPortfolioProject
from .tasks import send_quote_request_notifications


class QuotesModelTestCase(TestCase):
    def test_web_package_and_quote_request(self):
        pkg = WebPackage.objects.create(
            name="Landing Express",
            slug="landing-express-test",
            starting_price=Decimal("490.00"),
            price_display="desde 490€",
            delivery_timeline="5 días",
            short_summary="Landing de alta conversión",
            features=["Diseño editorial", "Hosting"],
        )
        self.assertEqual(str(pkg), "Landing Express (desde 490€)")

        quote = QuoteRequest.objects.create(
            service_type=QuoteRequest.ServiceType.WEB,
            package=pkg,
            full_name="Sofía Navarro",
            company_name="Navarro Studio",
            email="sofia@navarrostudio.es",
            phone="+34 600 00 11 22",
            project_description="Necesito una landing corporativa para estudio en Madrid.",
        )
        self.assertEqual(quote.status, QuoteRequest.Status.NEW)
        self.assertIn("Sofía Navarro", str(quote))


class QuoteRequestFlowTests(TestCase):
    def setUp(self):
        self.package = WebPackage.objects.create(
            name="Web Corporativa",
            slug="web-corporativa-test",
            starting_price=Decimal("1150.00"),
            price_display="desde 1.150€",
            delivery_timeline="2 semanas",
            short_summary="Sitio corporativo para una marca en crecimiento.",
            features=["Diseño a medida", "Panel de contenidos"],
            order=1,
            is_active=True,
        )

    def test_development_page_renders_packages_comparison_portfolio_and_form(self):
        WebPortfolioProject.objects.create(
            title="Identidad y web editorial",
            slug="identidad-web-editorial-test",
            client_name="Estudio Demo",
            sector="Cultura",
            summary="Una plataforma editorial para publicar proyectos y artículos.",
            technologies=["Django", "Tailwind"],
            is_active=True,
        )

        response = self.client.get(reverse("quotes:development"), {"paquete": self.package.slug})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.package.name)
        self.assertContains(response, "Qué incluye cada paquete")
        self.assertContains(response, "Identidad y web editorial")
        self.assertContains(response, "Enviar solicitud")
        self.assertEqual(response.context["form"]["package"].value(), self.package.pk)

    def test_homepage_package_cta_and_quote_form_are_live(self):
        response = self.client.get(reverse("core:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("quotes:development"))
        self.assertContains(response, 'name="privacy_accepted"')
        self.assertNotContains(response, "@submit.prevent")

    @patch("apps.quotes.views.queue_quote_request_notifications", return_value=True)
    def test_valid_submission_creates_web_lead_and_queues_notifications(self, queue_notifications):
        response = self.client.post(
            reverse("quotes:development"),
            {
                "package": str(self.package.pk),
                "full_name": "Lucía Martín",
                "company_name": "Martín Estudio",
                "email": "lucia@example.es",
                "phone": "+34 600 00 11 22",
                "nif_cif": "",
                "budget_range": "1.000€ - 3.000€",
                "project_description": "Necesito una web corporativa bilingüe con portfolio y formulario de contacto.",
                "privacy_accepted": "on",
                "website_url": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/quote_received.html")
        lead = QuoteRequest.objects.get(email="lucia@example.es")
        self.assertEqual(lead.service_type, QuoteRequest.ServiceType.WEB)
        self.assertEqual(lead.package, self.package)
        self.assertEqual(lead.status, QuoteRequest.Status.NEW)
        queue_notifications.assert_called_once_with(lead.pk)

    def test_submission_requires_privacy_consent_and_rejects_honeypot(self):
        payload = {
            "full_name": "Lucía Martín",
            "email": "lucia@example.es",
            "phone": "+34 600 00 11 22",
            "project_description": "Necesito una web corporativa con portfolio y formulario de contacto.",
        }
        response = self.client.post(reverse("quotes:development"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(QuoteRequest.objects.exists())

        payload.update({"privacy_accepted": "on", "website_url": "https://spam.invalid"})
        response = self.client.post(reverse("quotes:development"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(QuoteRequest.objects.exists())

    def test_quote_notifications_email_company_and_customer(self):
        lead = QuoteRequest.objects.create(
            service_type=QuoteRequest.ServiceType.WEB,
            package=self.package,
            full_name="Lucía Martín",
            email="lucia@example.es",
            phone="+34 600 00 11 22",
            project_description="Web corporativa bilingüe para estudio creativo.",
        )

        self.assertTrue(send_quote_request_notifications(lead.pk))

        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("lucia@example.es", mail.outbox[1].to)
        self.assertIn("Martín", mail.outbox[0].body)

    @override_settings(DEBUG=True)
    @patch("apps.quotes.tasks.send_quote_request_notifications")
    def test_debug_notification_queue_runs_without_redis(self, send_notifications):
        send_notifications.return_value = True

        result = self.client.post(
            reverse("quotes:development"),
            {
                "full_name": "Lucía Martín",
                "email": "debug@example.es",
                "phone": "+34 600 00 11 22",
                "project_description": "Necesito una web corporativa para mi empresa.",
                "privacy_accepted": "on",
                "website_url": "",
            },
        )

        self.assertEqual(result.status_code, 200)
        send_notifications.assert_called_once_with(QuoteRequest.objects.get(email="debug@example.es").pk)
