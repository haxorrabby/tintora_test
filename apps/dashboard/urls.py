from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("setup/", views.totp_setup, name="totp_setup"),
    path("verify/", views.totp_challenge, name="totp_challenge"),
]
