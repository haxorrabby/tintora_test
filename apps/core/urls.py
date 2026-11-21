from django.urls import path

from .views import ContactView, FAQPageView, HomeView, LegalView, NewsletterSubscribeView, StyleguideView

app_name = "core"

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("styleguide/", StyleguideView.as_view(), name="styleguide"),
    path("faq/", FAQPageView.as_view(), name="faq"),
    path("contacto/", ContactView.as_view(), name="contact"),
    path("legal/<slug:slug>/", LegalView.as_view(), name="legal"),
    path("newsletter/suscribir/", NewsletterSubscribeView.as_view(), name="newsletter"),
]
