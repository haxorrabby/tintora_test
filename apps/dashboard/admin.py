from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(ModelAdmin):
    list_display = ("created_at", "actor", "action", "app_label", "model_name", "object_repr", "ip_address")
    list_filter = ("action", "app_label", "model_name", "created_at")
    search_fields = ("object_repr", "object_pk", "actor__email", "user_agent")
    readonly_fields = (
        "created_at",
        "updated_at",
        "actor",
        "action",
        "app_label",
        "model_name",
        "object_pk",
        "object_repr",
        "changed_fields",
        "ip_address",
        "user_agent",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
