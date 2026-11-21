from django.urls import path

from .views import RedsysNotifyView, RedsysRedirectView, StripeWebhookView

app_name = "payments"

urlpatterns = [
    # Stripe kept but dormant while PAYMENTS_STRIPE_ENABLED=False
    path("webhooks/stripe/", StripeWebhookView.as_view(), name="stripe_webhook"),
    path("redsys/redirect/", RedsysRedirectView.as_view(), name="redsys_redirect"),
    path("redsys/notify/", RedsysNotifyView.as_view(), name="redsys_notify"),
]
