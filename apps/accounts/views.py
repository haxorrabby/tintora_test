import json
import logging
import posixpath
import shutil
import tempfile
import uuid
import zipfile

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core import signing
from django.core.files.base import ContentFile
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_http_methods, require_POST
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from apps.cart.models import Cart
from apps.cart.services import CartService
from apps.catalog.models import ProductOptionValue
from apps.orders.models import Invoice, Order, OrderItem

from .emails import EMAIL_VERIFICATION_MAX_AGE, EMAIL_VERIFICATION_SALT, send_email_verification
from .forms import (
    CustomerRegistrationForm,
    ProfileUpdateForm,
    SavedAddressForm,
)
from .models import CustomUser, SavedAddress, Wishlist

logger = logging.getLogger(__name__)


def _customer_orders(user):
    return Order.objects.filter(
        Q(user=user) | Q(user__isnull=True, email__iexact=user.email)
    )


def register(request):
    if request.user.is_authenticated:
        return redirect("customer:dashboard")

    form = CustomerRegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        try:
            sent = send_email_verification(user, request)
        except Exception:
            logger.exception("Failed to send account verification email for user %s", user.pk)
            sent = False
        return render(
            request,
            "registration/verification_sent.html",
            {"email": user.email, "email_sent": sent},
        )

    return render(request, "registration/register.html", {"form": form})


def verify_email(request, token):
    try:
        payload = signing.loads(
            token,
            salt=EMAIL_VERIFICATION_SALT,
            max_age=EMAIL_VERIFICATION_MAX_AGE,
        )
        if not isinstance(payload, dict):
            raise signing.BadSignature("Unexpected token payload")
    except signing.BadSignature:
        return render(request, "registration/verification_invalid.html", status=400)

    user = get_object_or_404(
        CustomUser,
        pk=payload.get("user_id"),
        email=payload.get("email"),
        is_active=True,
    )
    if not user.is_verified:
        user.is_verified = True
        user.save(update_fields=["is_verified", "updated_at"])
    messages.success(request, "Correo confirmado. Ya puedes iniciar sesión.")
    return redirect("customer:login")


@require_POST
def resend_verification(request):
    email = request.POST.get("email", "").strip()
    user = CustomUser.objects.filter(email__iexact=email, is_verified=False, is_active=True).first()
    if user:
        try:
            send_email_verification(user, request)
        except Exception:
            logger.exception("Failed to resend verification email for user %s", user.pk)
    messages.info(request, "Si la cuenta necesita verificación, enviaremos un nuevo enlace.")
    return redirect("customer:login")


def _add_export_file(file_field, archive_path, attachments):
    if not file_field or not file_field.name:
        return ""
    archive_name = f"archivos/{archive_path}/{posixpath.basename(file_field.name)}"
    attachments.append((file_field, archive_name))
    return archive_name


def _customer_export_payload(user, attachments):
    orders = list(
        _customer_orders(user)
        .select_related("invoice")
        .prefetch_related("items")
        .order_by("created_at")
    )
    serialized_orders = []

    for order in orders:
        serialized_items = []
        for item in order.items.all():
            serialized_items.append(
                {
                    "product_name": item.product_name,
                    "product_sku": item.product_sku,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                    "configuration": item.configuration,
                    "artwork_status": item.artwork_status,
                    "artwork_file": _add_export_file(
                        item.artwork_file,
                        f"pedidos/{order.pk}/originales/{item.pk}",
                        attachments,
                    ),
                    "proof_status": item.proof_status,
                    "proof_feedback": item.proof_feedback,
                    "proof_image": _add_export_file(
                        item.proof_image,
                        f"pedidos/{order.pk}/pruebas/{item.pk}",
                        attachments,
                    ),
                }
            )

        try:
            invoice = order.invoice
        except Invoice.DoesNotExist:
            invoice = None

        serialized_invoice = None
        if invoice:
            serialized_invoice = {
                "invoice_number": invoice.invoice_number,
                "issue_date": invoice.issue_date,
                "company_data": invoice.company_data,
                "customer_data": invoice.customer_data,
                "taxable_base": invoice.taxable_base,
                "iva_percentage": invoice.iva_percentage,
                "iva_amount": invoice.iva_amount,
                "total": invoice.total,
                "is_paid": invoice.is_paid,
                "pdf_file": _add_export_file(
                    invoice.pdf_file,
                    f"facturas/{invoice.pk}",
                    attachments,
                ),
            }

        serialized_orders.append(
            {
                "order_number": order.order_number,
                "created_at": order.created_at,
                "status": order.status,
                "customer": {
                    "type": order.customer_type,
                    "first_name": order.first_name,
                    "last_name": order.last_name,
                    "email": order.email,
                    "phone": order.phone,
                    "company_name": order.company_name,
                    "nif_cif": order.nif_cif,
                },
                "payment_method": order.payment_method,
                "payment_status": order.payment_status,
                "subtotal": order.subtotal,
                "discount_amount": order.discount_amount,
                "shipping_cost": order.shipping_cost,
                "taxable_base": order.taxable_base,
                "iva_percentage": order.iva_percentage,
                "iva_amount": order.iva_amount,
                "total": order.total,
                "shipping_address": {
                    "line1": order.shipping_address_line1,
                    "line2": order.shipping_address_line2,
                    "postal_code": order.shipping_postal_code,
                    "city": order.shipping_city,
                    "province": order.shipping_province,
                    "country": order.shipping_country,
                },
                "shipping_method": order.shipping_method_name,
                "courier": order.courier,
                "tracking_number": order.tracking_number,
                "tracking_url": order.tracking_url,
                "customer_notes": order.customer_notes,
                "items": serialized_items,
                "invoice": serialized_invoice,
            }
        )

    carts = user.carts.select_related("coupon", "shipping_method").prefetch_related("items__product")
    serialized_carts = []
    for cart in carts:
        serialized_items = []
        for item in cart.items.all():
            serialized_items.append(
                {
                    "product_name": item.product.name,
                    "product_sku": item.product.sku,
                    "quantity": item.quantity,
                    "selected_options": item.selected_options,
                    "unit_price": item.unit_price,
                    "line_total": item.line_total,
                    "artwork_status": item.artwork_status,
                    "artwork_file": _add_export_file(
                        item.artwork_file,
                        f"carritos/{cart.pk}/{item.pk}",
                        attachments,
                    ),
                }
            )
        serialized_carts.append(
            {
                "created_at": cart.created_at,
                "updated_at": cart.updated_at,
                "shipping_postal_code": cart.shipping_postal_code,
                "subtotal": cart.subtotal,
                "discount_amount": cart.discount_amount,
                "shipping_cost": cart.shipping_cost,
                "total": cart.total,
                "coupon": cart.coupon.code if cart.coupon else "",
                "items": serialized_items,
            }
        )

    return {
        "account": {
            "email": user.email,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "customer_type": user.customer_type,
            "company_name": user.company_name,
            "nif_cif": user.nif_cif,
            "phone": user.phone,
            "address": user.address,
            "postal_code": user.postal_code,
            "city": user.city,
            "province": user.province,
            "country": user.country,
            "email_verified": user.is_verified,
            "newsletter_subscribed": user.newsletter_subscribed,
            "date_joined": user.date_joined,
            "last_login": user.last_login,
            "updated_at": user.updated_at,
        },
        "saved_addresses": list(
            user.saved_addresses.values(
                "label",
                "address_line1",
                "address_line2",
                "postal_code",
                "city",
                "province",
                "country",
                "is_default",
                "created_at",
                "updated_at",
            )
        ),
        "wishlist": [
            {
                "product_name": item.product.name,
                "product_sku": item.product.sku,
                "notes": item.notes,
                "created_at": item.created_at,
            }
            for item in user.wishlist_items.select_related("product")
        ],
        "carts": serialized_carts,
        "orders": serialized_orders,
        "files": [archive_name for _, archive_name in attachments],
    }


@login_required
@require_POST
def export_customer_data(request):
    attachments = []
    payload = _customer_export_payload(request.user, attachments)
    archive_buffer = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024, mode="w+b")

    try:
        with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "datos.json",
                json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2),
            )
            for file_field, archive_name in attachments:
                with file_field.open("rb") as source, archive.open(archive_name, "w") as destination:
                    shutil.copyfileobj(source, destination)
        archive_buffer.seek(0)
    except Exception:
        archive_buffer.close()
        raise

    return FileResponse(
        archive_buffer,
        as_attachment=True,
        filename=f"tintora-exportacion-{request.user.pk}.zip",
        content_type="application/zip",
    )


@login_required
@require_POST
def delete_customer_account(request):
    user = request.user
    if user.is_staff:
        messages.error(request, "Las cuentas de equipo deben gestionarse desde administración.")
        return redirect("customer:privacy")
    if not user.check_password(request.POST.get("password", "")):
        messages.error(request, "La contraseña actual no es correcta.")
        return redirect("customer:privacy")
    if request.POST.get("confirmation", "").strip() != "ELIMINAR":
        messages.error(request, "Escribe ELIMINAR para confirmar la solicitud.")
        return redirect("customer:privacy")

    active_statuses = [
        Order.Status.RECIBIDO,
        Order.Status.REVISION_ARTE,
        Order.Status.PRUEBA_ENVIADA,
        Order.Status.EN_PRODUCCION,
        Order.Status.ENVIADO,
    ]
    with transaction.atomic():
        orders = list(_customer_orders(user).select_for_update().prefetch_related("items"))
        if any(order.status in active_statuses for order in orders):
            messages.error(
                request,
                "No podemos eliminar la cuenta mientras haya pedidos en curso. Cuando se entreguen o cancelen, vuelve a intentarlo.",
            )
            return redirect("customer:privacy")

        for order in orders:
            for item in order.items.all():
                for file_field in (item.artwork_file, item.proof_image):
                    if file_field and file_field.name:
                        file_field.storage.delete(file_field.name)
                item.artwork_file = None
                item.proof_image = None
                item.proof_feedback = ""
                item.save(
                    update_fields=[
                        "artwork_file",
                        "proof_image",
                        "proof_feedback",
                        "updated_at",
                    ]
                )

            order.user = None
            order.email = f"deleted-{order.pk}@privacy.invalid"
            order.first_name = "Cuenta eliminada"
            order.last_name = ""
            order.phone = ""
            order.company_name = ""
            order.nif_cif = ""
            order.shipping_address_line1 = ""
            order.shipping_address_line2 = ""
            order.shipping_postal_code = ""
            order.shipping_city = ""
            order.shipping_province = ""
            order.shipping_country = ""
            order.customer_notes = ""
            order.access_token = uuid.uuid4()
            order.save(
                update_fields=[
                    "user",
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                    "company_name",
                    "nif_cif",
                    "shipping_address_line1",
                    "shipping_address_line2",
                    "shipping_postal_code",
                    "shipping_city",
                    "shipping_province",
                    "shipping_country",
                    "customer_notes",
                    "access_token",
                    "updated_at",
                ]
            )

        carts = Cart.objects.filter(user=user).prefetch_related("items")
        for cart in carts:
            for item in cart.items.all():
                if item.artwork_file and item.artwork_file.name:
                    item.artwork_file.storage.delete(item.artwork_file.name)
        carts.delete()
        user.delete()

    logout(request)
    return render(request, "customer/account_deleted.html")


@login_required
def dashboard(request):
    """Customer dashboard with order summary and quick actions"""
    user = request.user

    # Get recent orders
    recent_orders = _customer_orders(user).order_by('-created_at')[:5]

    # Get wishlist count
    wishlist_count = Wishlist.objects.filter(user=user).count()

    # Get saved addresses count
    addresses_count = SavedAddress.objects.filter(user=user).count()

    # Get pending proofs (orders with proof sent but not approved)
    pending_proofs = OrderItem.objects.filter(
        order__in=recent_orders,
        proof_status=OrderItem.ProofStatus.SENT
    ).count()

    context = {
        'recent_orders': recent_orders,
        'wishlist_count': wishlist_count,
        'addresses_count': addresses_count,
        'pending_proofs': pending_proofs,
    }
    return render(request, 'customer/dashboard.html', context)


@login_required
def order_history(request):
    """Customer order history with status timeline"""
    user = request.user
    orders = _customer_orders(user).order_by('-created_at')

    context = {
        'orders': orders,
    }
    return render(request, 'customer/order_history.html', context)


@login_required
def order_detail(request, order_number):
    """Detailed order view with timeline and proof approval"""
    user = request.user
    order = get_object_or_404(_customer_orders(user), order_number=order_number)

    context = {
        'order': order,
    }
    return render(request, 'customer/order_detail.html', context)


@login_required
@require_POST
def reorder_order(request, order_number):
    order = get_object_or_404(_customer_orders(request.user), order_number=order_number)
    cart = CartService.get_or_create_cart(request)
    added_count = 0
    skipped_count = 0

    for order_item in order.items.select_related("product"):
        product = order_item.product
        if not product or not product.is_active or product.stock <= 0:
            skipped_count += 1
            continue

        quantity = min(order_item.quantity, product.stock)
        configuration = order_item.configuration if isinstance(order_item.configuration, dict) else {}
        option_value_ids = []
        for value in ProductOptionValue.objects.filter(group__product=product).select_related("group"):
            if configuration.get(value.group.name) == value.name:
                option_value_ids.append(value.pk)

        artwork_upload = None
        if order_item.artwork_file and order_item.artwork_file.name:
            try:
                with order_item.artwork_file.open("rb"):
                    artwork_upload = ContentFile(
                        order_item.artwork_file.read(),
                        name=posixpath.basename(order_item.artwork_file.name),
                    )
            except (FileNotFoundError, OSError):
                artwork_upload = None

        CartService.add_item(
            cart,
            product,
            quantity=quantity,
            option_value_ids=option_value_ids,
            artwork_file=artwork_upload,
            design_later=not bool(artwork_upload),
            request_proof=order_item.request_proof and product.allows_proof,
        )
        added_count += 1

    if added_count:
        messages.success(request, f"Se añadieron {added_count} artículo(s) a tu cesta con los precios actuales.")
    if skipped_count:
        messages.warning(request, f"Se omitieron {skipped_count} artículo(s) que ya no están disponibles.")
    if not added_count:
        messages.error(request, "No hay artículos disponibles para repetir este pedido.")
    return redirect("cart:detail")


@login_required
def artwork_library(request):
    artwork_items = (
        OrderItem.objects.filter(order__in=_customer_orders(request.user))
        .filter(Q(artwork_file__gt="") | Q(proof_image__gt=""))
        .select_related("order")
        .order_by("-updated_at")
    )
    return render(request, "customer/artwork_library.html", {"artwork_items": artwork_items})


@login_required
def download_customer_file(request, item_id, file_kind):
    item = get_object_or_404(
        OrderItem.objects.filter(order__in=_customer_orders(request.user)),
        pk=item_id,
    )
    file_field = {
        "artwork": item.artwork_file,
        "proof": item.proof_image,
    }.get(file_kind)
    if not file_field or not file_field.name:
        raise Http404

    try:
        file_field.open("rb")
    except (FileNotFoundError, OSError):
        raise Http404 from None

    return FileResponse(
        file_field,
        as_attachment=True,
        filename=posixpath.basename(file_field.name),
    )


def _get_customer_order_item(request, order_number, item_id):
    return get_object_or_404(
        OrderItem.objects.select_related("order").filter(
            order__in=_customer_orders(request.user),
            order__order_number=order_number,
            pk=item_id,
        )
    )


@login_required
@require_POST
def approve_proof(request, order_number, item_id):
    """Customer approves a proof"""
    item = _get_customer_order_item(request, order_number, item_id)

    if item.proof_status != OrderItem.ProofStatus.SENT:
        messages.error(request, "Esta prueba no puede ser aprobada en este estado.")
        return redirect('customer:order_detail', order_number=item.order.order_number)

    item.proof_status = OrderItem.ProofStatus.APPROVED
    item.save(update_fields=["proof_status", "updated_at"])
    messages.success(request, "Prueba aprobada correctamente.")
    return redirect('customer:order_detail', order_number=item.order.order_number)


@login_required
@require_POST
def reject_proof(request, order_number, item_id):
    """Customer rejects a proof with feedback"""
    item = _get_customer_order_item(request, order_number, item_id)

    if item.proof_status != OrderItem.ProofStatus.SENT:
        messages.error(request, "Esta prueba no puede ser rechazada en este estado.")
        return redirect('customer:order_detail', order_number=item.order.order_number)

    feedback = request.POST.get("proof_feedback", "").strip()
    if not feedback:
        messages.error(request, "Indica qué cambios necesitas antes de enviar la solicitud.")
        return redirect('customer:order_detail', order_number=item.order.order_number)

    item.proof_status = OrderItem.ProofStatus.REJECTED
    item.proof_feedback = feedback
    item.save(update_fields=["proof_status", "proof_feedback", "updated_at"])
    messages.success(request, "Prueba rechazada. Nos pondremos en contacto contigo para revisar los cambios.")
    return redirect('customer:order_detail', order_number=item.order.order_number)


@login_required
@require_http_methods(["GET", "POST"])
def upload_artwork(request, order_number, item_id):
    """Customer uploads artwork for an order item"""
    item = _get_customer_order_item(request, order_number, item_id)

    if item.artwork_status not in [OrderItem.ArtworkStatus.DESIGN_LATER, OrderItem.ArtworkStatus.NEEDS_REVISION]:
        messages.error(request, "No puedes subir arte en este estado.")
        return redirect('customer:order_detail', order_number=item.order.order_number)

    if request.method == 'POST':
        artwork_file = request.FILES.get('artwork_file')
        if artwork_file:
            allowed_extensions = {".pdf", ".ai", ".eps", ".psd", ".tiff", ".jpg", ".png"}
            extension = "." + artwork_file.name.rsplit(".", 1)[-1].lower() if "." in artwork_file.name else ""
            if extension not in allowed_extensions:
                messages.error(request, "El formato del archivo no está permitido.")
            elif artwork_file.size > 50 * 1024 * 1024:
                messages.error(request, "El archivo no puede superar los 50 MB.")
            else:
                item.artwork_file = artwork_file
                item.artwork_status = OrderItem.ArtworkStatus.UPLOADED
                item.save(update_fields=["artwork_file", "artwork_status", "updated_at"])
                messages.success(request, "Arte subido correctamente. Nuestro equipo lo revisará.")
                return redirect('customer:order_detail', order_number=item.order.order_number)
        else:
            messages.error(request, "Por favor selecciona un archivo.")

    context = {
        'item': item,
    }
    return render(request, 'customer/upload_artwork.html', context)


class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    """Customer profile editing"""
    model = CustomUser
    form_class = ProfileUpdateForm
    template_name = 'customer/profile_edit.html'
    success_url = reverse_lazy('customer:dashboard')

    def get_object(self):
        return self.request.user

    def form_valid(self, form):
        messages.success(self.request, "Perfil actualizado correctamente.")
        return super().form_valid(form)


class SavedAddressListView(LoginRequiredMixin, ListView):
    """List of saved addresses"""
    model = SavedAddress
    template_name = 'customer/addresses.html'
    context_object_name = 'addresses'

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user).order_by('-is_default', 'label')


class SavedAddressCreateView(LoginRequiredMixin, CreateView):
    """Create new saved address"""
    model = SavedAddress
    form_class = SavedAddressForm
    template_name = 'customer/address_form.html'
    success_url = reverse_lazy('customer:addresses')

    def form_valid(self, form):
        form.instance.user = self.request.user
        messages.success(self.request, "Dirección guardada correctamente.")
        return super().form_valid(form)


class SavedAddressUpdateView(LoginRequiredMixin, UpdateView):
    """Update saved address"""
    model = SavedAddress
    form_class = SavedAddressForm
    template_name = 'customer/address_form.html'
    success_url = reverse_lazy('customer:addresses')

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user)

    def form_valid(self, form):
        messages.success(self.request, "Dirección actualizada correctamente.")
        return super().form_valid(form)


class SavedAddressDeleteView(LoginRequiredMixin, DeleteView):
    """Delete saved address"""
    model = SavedAddress
    template_name = 'customer/address_confirm_delete.html'
    success_url = reverse_lazy('customer:addresses')

    def get_queryset(self):
        return SavedAddress.objects.filter(user=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "Dirección eliminada.")
        return super().delete(request, *args, **kwargs)


@login_required
def set_default_address(request, address_id):
    """Set an address as default"""
    address = get_object_or_404(SavedAddress, id=address_id, user=request.user)

    # Remove default from all other addresses
    SavedAddress.objects.filter(user=request.user).update(is_default=False)

    # Set this as default
    address.is_default = True
    address.save()

    messages.success(request, f"{address.label} establecida como dirección por defecto.")
    return redirect('customer:addresses')


class WishlistListView(LoginRequiredMixin, ListView):
    """Customer wishlist"""
    model = Wishlist
    template_name = 'customer/wishlist.html'
    context_object_name = 'wishlist_items'

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product').order_by('-created_at')


@login_required
def add_to_wishlist(request, product_id):
    """Add product to wishlist"""
    from apps.catalog.models import Product

    product = get_object_or_404(Product, id=product_id)

    # Check if already in wishlist
    if Wishlist.objects.filter(user=request.user, product=product).exists():
        messages.info(request, "Este producto ya está en tu lista de deseos.")
    else:
        Wishlist.objects.create(user=request.user, product=product)
        messages.success(request, "Producto añadido a tu lista de deseos.")

    # Only follow same-origin relative referers (open-redirect guard).
    referer = request.META.get("HTTP_REFERER", "")
    if referer.startswith("/") and not referer.startswith("//"):
        return redirect(referer)
    return redirect(reverse("customer:wishlist"))


def toggle_wishlist(request, product_id):
    """HTMX-aware wishlist toggle used by the product-card heart button.

    Anonymous users get an ``HX-Redirect`` to the login page when the request
    comes from HTMX (so the login page replaces the whole window instead of
    being swapped into the button).
    """
    from apps.catalog.models import Product

    product = get_object_or_404(Product, id=product_id)

    if not request.user.is_authenticated:
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = reverse("customer:login")
            return response
        return redirect("customer:login")

    item = Wishlist.objects.filter(user=request.user, product=product).first()
    if item:
        item.delete()
        wished = False
    else:
        Wishlist.objects.create(user=request.user, product=product)
        wished = True

    if request.headers.get("HX-Request"):
        return render(
            request,
            "components/wishlist_heart.html",
            {"product": product, "wished": wished},
        )

    referer = request.META.get("HTTP_REFERER", "")
    if referer.startswith("/") and not referer.startswith("//"):
        return redirect(referer)
    return redirect(reverse("customer:wishlist"))


@login_required
def remove_from_wishlist(request, wishlist_id):
    """Remove item from wishlist"""
    item = get_object_or_404(Wishlist, id=wishlist_id, user=request.user)
    item.delete()
    messages.success(request, "Producto eliminado de tu lista de deseos.")
    return redirect('customer:wishlist')


@login_required
def privacy_settings(request):
    """Manage newsletter consent and display privacy actions."""
    user = request.user

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'toggle_newsletter':
            user.newsletter_subscribed = not user.newsletter_subscribed
            user.save()
            status = "activada" if user.newsletter_subscribed else "desactivada"
            messages.success(request, f"Suscripción a la Gaceta Tintora {status}.")
        else:
            messages.error(request, "La acción solicitada no está disponible.")

    context = {
        'user': user,
    }
    return render(request, 'customer/privacy.html', context)
