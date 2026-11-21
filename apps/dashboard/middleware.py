import ipaddress
import time
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from .context import current_actor, current_request


class AuditActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        actor = request.user if request.user.is_authenticated else None
        actor_token = current_actor.set(actor)
        request_token = current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            current_request.reset(request_token)
            current_actor.reset(actor_token)


class AdminSecurityMiddleware:
    session_key = "tintora_admin_totp_verified_until"
    activity_key = "tintora_admin_last_activity"

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL_PATH.strip("/") + "/"
        self.allowed_networks = tuple(
            ipaddress.ip_network(value, strict=False)
            for value in getattr(settings, "ADMIN_ALLOWED_IPS", ())
        )

    def __call__(self, request):
        path = request.path_info
        if not path.startswith(self.admin_prefix):
            return self.get_response(request)

        if self.allowed_networks:
            try:
                client_ip = ipaddress.ip_address(request.META.get("REMOTE_ADDR", ""))
            except ValueError:
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Acceso no permitido desde esta red.")
            if not any(client_ip in network for network in self.allowed_networks):
                from django.http import HttpResponseForbidden

                return HttpResponseForbidden("Acceso no permitido desde esta red.")

        if path.startswith(self.admin_prefix + "2fa/"):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated or not user.is_staff or not user.is_active:
            return self.get_response(request)

        now = int(time.time())
        if getattr(settings, "ADMIN_2FA_REQUIRED", True):
            if not user.totp_enabled or not user.totp_secret:
                return redirect("dashboard:totp_setup")

            verified_until = request.session.get(self.session_key, 0)
            if verified_until < now:
                request.session.pop(self.session_key, None)
                challenge_url = reverse("dashboard:totp_challenge")
                query = urlencode({"next": request.get_full_path()})
                return redirect(f"{challenge_url}?{query}")

        last_activity = request.session.get(self.activity_key, now)
        idle_timeout = getattr(settings, "ADMIN_SESSION_IDLE_TIMEOUT", 1800)
        if now - last_activity > idle_timeout:
            logout(request)
            return redirect("admin:login")

        request.session[self.activity_key] = now
        return self.get_response(request)
