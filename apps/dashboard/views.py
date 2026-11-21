import time
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F, Sum
from django.db.models.functions import TruncDate
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.quotes.models import QuoteRequest

from .middleware import AdminSecurityMiddleware
from .models import AuditEvent
from .totp import decrypt_totp_secret, encrypt_totp_secret, generate_totp_secret, provisioning_uri, verify_totp

_TOTP_FAILURE_LIMIT = 5
_TOTP_FAILURE_WINDOW = 5 * 60


def _totp_attempts(session, now):
    attempts = session.get("tintora_admin_totp_failures", {})
    if not attempts:
        return {"count": 0, "started_at": now}
    if now - attempts.get("started_at", now) > _TOTP_FAILURE_WINDOW:
        attempts = {"count": 0, "started_at": now}
    return attempts


def _safe_admin_destination(request, candidate):
    admin_prefix = "/" + settings.ADMIN_URL_PATH.strip("/") + "/"
    if (
        candidate.startswith(admin_prefix)
        and url_has_allowed_host_and_scheme(candidate, {request.get_host()}, require_https=request.is_secure())
    ):
        return candidate
    return admin_prefix


@staff_member_required(login_url="admin:login")
@require_http_methods(["GET", "POST"])
def totp_setup(request):
    user = request.user
    if user.totp_enabled and user.totp_secret:
        return redirect("dashboard:totp_challenge")
    if not user.totp_secret:
        user.totp_secret = encrypt_totp_secret(generate_totp_secret())
        user.save(update_fields=["totp_secret", "updated_at"])

    error = ""
    if request.method == "POST":
        now = int(time.time())
        attempts = _totp_attempts(request.session, now)
        if attempts["count"] >= _TOTP_FAILURE_LIMIT:
            error = "Se han agotado los intentos. Espera cinco minutos antes de volver a probar."
            return render(request, "admin/security/totp_setup.html", {
                "secret": decrypt_totp_secret(user.totp_secret),
                "provisioning_uri": provisioning_uri(decrypt_totp_secret(user.totp_secret), user.email),
                "error": error,
            }, status=429)
        if verify_totp(decrypt_totp_secret(user.totp_secret), request.POST.get("code", "")):
            user.totp_enabled = True
            user.save(update_fields=["totp_enabled", "updated_at"])
            request.session.pop("tintora_admin_totp_failures", None)
            request.session[AdminSecurityMiddleware.session_key] = now + 8 * 60 * 60
            request.session[AdminSecurityMiddleware.activity_key] = now
            messages.success(request, "La verificación en dos pasos ya está activa.")
            return redirect(_safe_admin_destination(request, request.GET.get("next", "")))
        attempts["count"] += 1
        request.session["tintora_admin_totp_failures"] = attempts
        error = "El código no es válido. Comprueba la hora del dispositivo y vuelve a intentarlo."

    return render(
        request,
        "admin/security/totp_setup.html",
        {
            "secret": decrypt_totp_secret(user.totp_secret),
            "provisioning_uri": provisioning_uri(decrypt_totp_secret(user.totp_secret), user.email),
            "error": error,
        },
    )


@staff_member_required(login_url="admin:login")
@require_http_methods(["GET", "POST"])
def totp_challenge(request):
    user = request.user
    if not user.totp_enabled or not user.totp_secret:
        return redirect("dashboard:totp_setup")

    error = ""
    if request.method == "POST":
        now = int(time.time())
        attempts = _totp_attempts(request.session, now)
        if attempts["count"] >= _TOTP_FAILURE_LIMIT:
            return render(
                request,
                "admin/security/totp_challenge.html",
                {"error": "Se han agotado los intentos. Espera cinco minutos antes de volver a probar."},
                status=429,
            )
        if verify_totp(decrypt_totp_secret(user.totp_secret), request.POST.get("code", "")):
            request.session.pop("tintora_admin_totp_failures", None)
            request.session[AdminSecurityMiddleware.session_key] = now + 8 * 60 * 60
            request.session[AdminSecurityMiddleware.activity_key] = now
            return redirect(_safe_admin_destination(request, request.GET.get("next", "")))
        attempts["count"] += 1
        request.session["tintora_admin_totp_failures"] = attempts
        error = "El código no es válido o ha caducado."

    return render(request, "admin/security/totp_challenge.html", {"error": error})


@staff_member_required(login_url="admin:login")
def admin_dashboard(request):
    can_view_analytics = request.user.is_superuser or request.user.has_perm("dashboard.view_adminanalytics")
    can_view_orders = request.user.is_superuser or request.user.has_perm("orders.view_order")
    can_view_inventory = request.user.is_superuser or request.user.has_perm("catalog.view_product")
    if not (can_view_analytics or can_view_orders or can_view_inventory):
        return HttpResponseForbidden("No tienes permiso para consultar el panel de administración.")

    now = timezone.localtime()
    today = now.date()
    start_week = today - timedelta(days=today.weekday())
    paid_orders = Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
    revenue_today = paid_orders.filter(created_at__date=today).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    revenue_week = paid_orders.filter(created_at__date__gte=start_week).aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    revenue_month = paid_orders.filter(created_at__year=today.year, created_at__month=today.month).aggregate(
        total=Sum("total")
    )["total"] or Decimal("0.00")

    chart_start = today - timedelta(days=13)
    grouped_revenue = {
        row["day"]: row["total"] or Decimal("0.00")
        for row in paid_orders.filter(created_at__date__gte=chart_start, created_at__date__lte=today)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total"))
    }
    chart = [
        {
            "day": chart_start + timedelta(days=index),
            "revenue": grouped_revenue.get(chart_start + timedelta(days=index), Decimal("0.00")),
        }
        for index in range(14)
    ]
    max_revenue = max((point["revenue"] for point in chart), default=Decimal("0.00")) or Decimal("1.00")
    for point in chart:
        point["height"] = max(4, int(point["revenue"] / max_revenue * 100))

    status_counts = (
        [
            {"label": label, "count": Order.objects.filter(status=value).count()}
            for value, label in Order.Status.choices
        ]
        if can_view_orders
        else []
    )
    top_products = (
        OrderItem.objects.filter(order__payment_status=Order.PaymentStatus.PAID)
        .values("product_name")
        .annotate(units=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")[:5]
        if can_view_analytics
        else []
    )
    low_stock = (
        Product.objects.filter(stock__gt=0, stock__lte=F("low_stock_threshold")).order_by("stock", "name")[:10]
        if can_view_inventory
        else []
    )
    new_quotes = (
        QuoteRequest.objects.filter(status=QuoteRequest.Status.NEW).order_by("-created_at")[:8]
        if can_view_analytics
        else []
    )

    context = admin.site.each_context(request)
    context.update(
        {
            "title": _("Analítica de Tintora"),
            "can_view_analytics": can_view_analytics,
            "can_view_orders": can_view_orders,
            "can_view_inventory": can_view_inventory,
            "revenue_today": revenue_today,
            "revenue_week": revenue_week,
            "revenue_month": revenue_month,
            "chart": chart,
            "status_counts": status_counts,
            "top_products": top_products,
            "low_stock": low_stock,
            "new_quotes": new_quotes,
            "recent_orders": Order.objects.order_by("-created_at")[:8] if can_view_orders else [],
            "recent_activity": AuditEvent.objects.select_related("actor")[:10] if can_view_analytics else [],
        }
    )
    return render(request, "admin/index.html", context)
