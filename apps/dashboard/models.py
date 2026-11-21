from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class AuditEvent(TimeStampedModel):
    class Action(models.TextChoices):
        CREATED = "created", _("Creado")
        UPDATED = "updated", _("Modificado")
        DELETED = "deleted", _("Eliminado")

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
        verbose_name=_("Usuario responsable"),
    )
    action = models.CharField(_("Acción"), max_length=12, choices=Action.choices)
    app_label = models.CharField(_("Aplicación"), max_length=100)
    model_name = models.CharField(_("Modelo"), max_length=100)
    object_pk = models.CharField(_("Identificador"), max_length=100)
    object_repr = models.CharField(_("Objeto"), max_length=255)
    changed_fields = models.JSONField(_("Campos modificados"), default=list, blank=True)
    ip_address = models.GenericIPAddressField(_("Dirección IP"), null=True, blank=True)
    user_agent = models.CharField(_("Navegador"), max_length=300, blank=True)

    class Meta:
        verbose_name = _("Evento de auditoría")
        verbose_name_plural = _("Registro de auditoría")
        ordering = ["-created_at"]
        permissions = [("view_adminanalytics", "Can view the admin analytics dashboard")]

    def __str__(self):
        return f"{self.get_action_display()} · {self.app_label}.{self.model_name} #{self.object_pk}"
