"""
apps/core/views.py — Tintora core views.

Provides:
- HomeView: e-commerce homepage with live DB context
- FAQPageView / ContactView / LegalView: static content pages
- NewsletterSubscribeView: GDPR newsletter opt-in endpoint
- StyleguideView: design system reference page
- health_check: k8s/load-balancer health endpoint
"""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView
from django.views.static import serve

from apps.latin_products.data import preview_products, product_total

from .legal_content import render_legal_content
from .models import FAQ, HomepageSettings, NewsletterSubscriber, PortfolioItem, Testimonial


def _faq_schema(faqs) -> dict:
    """Build a schema.org FAQPage payload from a FAQ queryset/list."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {
                "@type": "Question",
                "name": f.question,
                "acceptedAnswer": {"@type": "Answer", "text": f.answer},
            }
            for f in faqs
        ],
    }


class HomeView(TemplateView):
    """E-commerce homepage — featured/best-seller products and packages from DB."""

    template_name = "pages/home.html"

    # ------------------------------------------------------------------ #
    # Services data — displayed as the four numbered pillars on the home  #
    # ------------------------------------------------------------------ #
    SERVICES = [
        {
            "number": "01",
            "name": "Impresión Profesional",
            "tagline": "Calibración Fogra39, papeles de alta gama y acabados premium: soft-touch, stamping en oro, barniz selectivo UV.",
            "category_slug": "tarjetas-de-visita",
            "items": [
                "Tarjetas de Visita Premium",
                "Flyers & Folletos DL/A5/A4",
                "Carpetas & Dípticos",
                "Catálogos & Revistas",
                "Roll-ups & Banners",
                "Pegatinas & Troquelados",
            ],
        },
        {
            "number": "02",
            "name": "Sublimación & Merch",
            "tagline": "Termotransferencia con colores vibrantes y alta resistencia al lavado para textil, cerámica y más.",
            "category_slug": "tazas-personalizadas",
            "items": [
                "Tazas Mágicas & Cerámica",
                "Camisetas Técnicas & Algodón",
                "Gorras Trucker & Clásicas",
                "Cojines Decorativos",
                "Fundas Móvil Antigolpes",
                "Puzzles Personalizados",
            ],
        },
        {
            "number": "03",
            "name": "Productos Latinos",
            "tagline": "Sabores auténticos traídos de Colombia, Venezuela, México, Perú y Ecuador directamente a Madrid.",
            "category_slug": "harinas-y-granos",
            "items": [
                "Harinas PAN & Arepas",
                "Café Juan Valdez & Andino",
                "Refrescos & Maltas",
                "Snacks, Platanitos & Chucherías",
                "Salsas Picantes & Condimentos",
                "Confitería Tradicional",
            ],
        },
        {
            "number": "04",
            "name": "Desarrollo Web & IT",
            "tagline": "Ingeniería Python/Django, Tailwind, Alpine.js. Diseño editorial de alta gama con Stripe, Bizum y SEO.",
            "category_slug": None,  # links to #desarrollo-web anchor
            "items": [
                "Landing Pages Alta Conversión",
                "Webs Corporativas B2B/B2C",
                "E-Commerce con Stripe & Bizum",
                "Desarrollo a Medida & API REST",
                "Optimización SEO Técnico",
                "Mantenimiento y Soporte",
            ],
        },
    ]

    def get_context_data(self, **kwargs: object) -> dict:
        """Build home page context from DB + static editorial data."""
        context = super().get_context_data(**kwargs)

        # Imported late to avoid circular imports at module level
        from django.db.models import Count, Prefetch, Q  # noqa: PLC0415

        from apps.catalog.models import Category, Product  # noqa: PLC0415
        from apps.orders.models import Order  # noqa: PLC0415
        from apps.quotes.models import WebPackage  # noqa: PLC0415

        # Featured products
        featured_products = list(
            Product.objects.filter(is_active=True, is_featured=True, parent_product__isnull=True)
            .select_related("category")
            .prefetch_related("images", "size_variants__images")
            .order_by("-created_at")[:8]
        )

        new_arrivals = list(
            Product.objects.filter(is_active=True, base_price__gt=0, parent_product__isnull=True)
            .select_related("category")
            .prefetch_related("images", "size_variants__images")
            .order_by("-created_at")[:4]
        )

        # Best sellers — real sales ordering, graceful fallback to featured
        best_sellers = self._best_sellers(Product, Order, featured_products)

        # Whether the best-seller row is backed by real (non-cancelled) sales
        from apps.orders.models import OrderItem  # noqa: PLC0415

        has_sales_data = OrderItem.objects.filter(product__isnull=False).exclude(
            order__status=Order.Status.CANCELADO
        ).exists()

        # "Compra por categoría" tiles — active categories with product counts.
        # Only categories with at least one active (purchasable) product are
        # shown; newly imported rows stay hidden until priced + activated.
        products_with_images = (
            Product.objects.filter(is_active=True, parent_product__isnull=True)
            .filter(Q(images__image__gt="") | Q(images__image_url__gt=""))
            .distinct()
            .order_by("-is_featured", "-created_at")
            .prefetch_related("images")
        )
        categories = list(
            Category.objects.filter(is_active=True, parent__isnull=True)
            .annotate(
                product_count=Count(
                    "products",
                    filter=Q(products__is_active=True, products__parent_product__isnull=True),
                )
            )
            .filter(product_count__gt=0)
            .order_by("business_area", "order", "name")
            .prefetch_related(Prefetch("products", queryset=products_with_images, to_attr="products_with_images"))
        )
        for category in categories:
            if category.image:
                category.cover_image_url = category.image.url
            elif category.products_with_images:
                category.cover_image_url = next(
                    (
                        product.primary_image_url
                        for product in category.products_with_images
                        if "tintora-logo-mono.svg" not in product.primary_image_url
                    ),
                    "",
                )
            else:
                category.cover_image_url = ""

        # Web dev packages
        web_packages = list(WebPackage.objects.filter(is_active=True).order_by("order"))

        # Admin-managed content
        home_content = HomepageSettings.get_cached()
        testimonials = list(Testimonial.objects.filter(is_published=True)[:6])
        faqs = list(FAQ.objects.filter(is_published=True)[:10])
        portfolio = list(PortfolioItem.objects.filter(is_published=True)[:6])

        context.update(
            {
                "page_title": "Tintora · Tinta que deja huella",
                "services": self.SERVICES,
                "categories": categories,
                "featured_products": featured_products,
                "new_arrivals": new_arrivals,
                "best_sellers": best_sellers,
                "has_sales_data": has_sales_data,
                "portfolio": portfolio,
                "web_packages": web_packages,
                "testimonials": testimonials,
                "faqs": faqs,
                "home_content": home_content,
                "faq_schema": _faq_schema(faqs) if faqs else None,
                # Database-backed Latin catalog preview.
                "latin_preview": preview_products(8),
                "latin_total": product_total(),
            }
        )
        return context

    @staticmethod
    def _best_sellers(Product, Order, fallback: list) -> list:
        """Top products by units sold (excluding cancelled orders).

        Falls back to featured products when there is not enough sales history.
        """
        from django.db.models import Sum  # noqa: PLC0415
        from django.db.models.functions import Coalesce  # noqa: PLC0415

        from apps.orders.models import OrderItem  # noqa: PLC0415

        rows = (
            OrderItem.objects.filter(product__isnull=False)
            .exclude(order__status=Order.Status.CANCELADO)
            .annotate(parent_id=Coalesce("product__parent_product_id", "product_id"))
            .values("parent_id")
            .annotate(units=Sum("quantity"))
            .order_by("-units", "parent_id")[:8]
        )
        ordered_ids = [row["parent_id"] for row in rows]

        products = {
            p.id: p
            for p in Product.objects.filter(is_active=True, id__in=ordered_ids, parent_product__isnull=True)
            .select_related("category")
            .prefetch_related("images", "size_variants__images")
        }
        result = [products[pid] for pid in ordered_ids if pid in products]

        if len(result) < 8:
            seen = {p.id for p in result}
            for p in fallback:
                if len(result) >= 8:
                    break
                if p.id not in seen:
                    result.append(p)
                    seen.add(p.id)
        return result


class StyleguideView(TemplateView):
    """Design system reference — brand tokens, typography, component states."""

    template_name = "styleguide.html"


class FAQPageView(TemplateView):
    """Public FAQ page with client-side search and FAQPage schema."""

    template_name = "pages/faq.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        faqs = list(FAQ.objects.filter(is_published=True))
        groups = []
        for value, label in FAQ.Group.choices:
            items = [f for f in faqs if f.group == value]
            if items:
                groups.append({"key": value, "label": label, "items": items})
        context.update(
            {
                "page_title": "Preguntas Frecuentes · Tintora Madrid",
                "meta_description": "Dudas sobre pedidos, impresión, envíos, diseños, pagos y devoluciones en Tintora, Madrid.",
                "groups": groups,
                "faqs": faqs,
                "faq_schema": _faq_schema(faqs) if faqs else None,
            }
        )
        return context


class ContactView(TemplateView):
    """Contact page — real company data, WhatsApp/email shortcuts, quote CTA."""

    template_name = "pages/contact.html"

    def get_context_data(self, **kwargs: object) -> dict:
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": "Contacto · Tintora Madrid",
                "meta_description": (
                    f"Habla con Tintora: taller en {settings.TINTORA_COMPANY['ADDRESS']}. "
                    "Teléfono, WhatsApp, horarios y solicitud de presupuesto."
                ),
            }
        )
        return context


class LegalView(View):
    """Renders the legal pages (aviso legal, privacidad, cookies, venta, envíos)."""

    def get(self, request: HttpRequest, slug: str) -> HttpResponse:
        page = render_legal_content(slug, settings.TINTORA_COMPANY)
        if page is None:
            raise Http404("Página legal no encontrada")
        return render(
            request,
            "pages/legal_detail.html",
            {
                "page_title": f"{page['title']} · Tintora Madrid",
                "meta_description": f"{page['title']} de Tintora Impresión y Soluciones Creativas S.L., Madrid.",
                "legal": page,
                "slug": slug,
            },
        )


class NewsletterSubscribeView(View):
    """GDPR newsletter opt-in. Returns an HTMX fragment or redirects back."""

    def post(self, request: HttpRequest) -> HttpResponse:
        email = request.POST.get("email", "").strip().lower()
        consent = request.POST.get("consent")
        honeypot = request.POST.get("website", "")

        ok = False
        if not honeypot and consent in ("on", "true", "1") and email:
            try:
                validate_email(email)
            except ValidationError:
                ok = False
            else:
                subscriber, created = NewsletterSubscriber.objects.get_or_create(
                    email=email,
                    defaults={
                        "consent_at": timezone.now(),
                        "source": (request.POST.get("source", "footer")[:50] or "footer"),
                    },
                )
                if not created and not subscriber.is_active:
                    subscriber.is_active = True
                    subscriber.consent_at = timezone.now()
                    subscriber.save(update_fields=["is_active", "consent_at", "updated_at"])
                ok = True

        if request.headers.get("HX-Request"):
            return render(
                request,
                "components/newsletter_form.html",
                {
                    "newsletter_ok": ok,
                    "newsletter_error": not ok,
                    "newsletter_badge": request.POST.get("source", "footer"),
                    "newsletter_dark": request.POST.get("dark") == "1",
                },
            )

        if ok:
            messages.success(request, "¡Gracias por suscribirte a la newsletter de Tintora!")
        else:
            messages.error(request, "Revisa el email y acepta la política de privacidad para suscribirte.")
        referer = request.META.get("HTTP_REFERER", "")
        if referer.startswith("/") and not referer.startswith("//"):
            return redirect(referer)
        return redirect("core:home")


def health_check(request):  # type: ignore[no-untyped-def]
    """
    Simple health check endpoint for load balancers and uptime monitors.

    Returns HTTP 200 with JSON payload ``{"status": "ok"}`` when the
    application is running correctly.
    """
    return JsonResponse({"status": "ok", "service": "tintora"})


def public_catalog_media(request: HttpRequest, path: str) -> HttpResponse:
    """Serve public catalog photos without exposing invoices or customer artwork."""
    return serve(request, path, document_root=Path(settings.MEDIA_ROOT) / "catalog")


def page_not_found_view(request: HttpRequest, exception=None) -> HttpResponse:
    """Custom premium 404 handler returning genuine HTTP 404 status."""
    return render(request, "404.html", status=404)


def permission_denied_view(request: HttpRequest, exception=None) -> HttpResponse:
    """Render the branded 403 page for forbidden requests."""
    return render(request, "403.html", status=403)


def server_error_view(request: HttpRequest) -> HttpResponse:
    """Custom premium 500 handler returning genuine HTTP 500 status."""
    return render(request, "500.html", status=500)
