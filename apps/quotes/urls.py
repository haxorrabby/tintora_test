from django.urls import path

from .views import DevelopmentWebView

app_name = "quotes"

urlpatterns = [
    path("", DevelopmentWebView.as_view(), name="development"),
]
