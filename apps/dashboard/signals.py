from django.db import connection
from django.db.models import DateTimeField, Model, signals

from .context import current_actor, current_request
from .models import AuditEvent

_EXCLUDED_APPS = {"admin", "auth", "contenttypes", "dashboard", "migrations", "sessions"}

# Once the audit table has been observed to exist we cache that positive
# (never a negative) so production saves don't re-introspect every time.
_audit_table_ready_flag = False


def _audit_table_ready() -> bool:
    """Return True once the audit table exists, re-checking until it does.

    Data migrations (e.g. core.0002 seeds) fire post_save while the
    ``dashboard_auditevent`` table may not exist yet in a fresh database, so
    audit writes must be skipped there instead of crashing the migration.
    """
    global _audit_table_ready_flag
    if _audit_table_ready_flag:
        return True
    try:
        _audit_table_ready_flag = (
            AuditEvent._meta.db_table in connection.introspection.table_names()
        )
    except Exception:  # noqa: BLE001 - never let the audit trail break a save
        _audit_table_ready_flag = False
    return _audit_table_ready_flag


def _is_audited(sender: type[Model]) -> bool:
    return sender._meta.app_label not in _EXCLUDED_APPS and sender is not AuditEvent


def _field_values(instance: Model) -> dict[str, object]:
    values = {}
    for field in instance._meta.concrete_fields:
        if field.primary_key or field.name == "password" or isinstance(field, DateTimeField) and field.auto_now:
            continue
        value = field.value_from_object(instance)
        if hasattr(value, "name"):
            value = value.name
        values[field.name] = value
    return values


def _audit_metadata(instance: Model) -> dict[str, object]:
    request = current_request.get()
    ip_address = request.META.get("REMOTE_ADDR") if request else None
    user_agent = request.META.get("HTTP_USER_AGENT", "")[:300] if request else ""
    return {
        "actor": current_actor.get(),
        "app_label": instance._meta.app_label,
        "model_name": instance._meta.model_name,
        "object_pk": str(instance.pk),
        "object_repr": str(instance)[:255],
        "ip_address": ip_address,
        "user_agent": user_agent,
    }


def before_model_save(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk or not _is_audited(sender):
        instance._audit_before = None
        return
    try:
        previous = sender._base_manager.get(pk=instance.pk)
    except sender.DoesNotExist:
        instance._audit_before = None
        return
    instance._audit_before = _field_values(previous)


def after_model_save(sender, instance, created=False, raw=False, **kwargs):
    if raw or not _is_audited(sender):
        return
    before = getattr(instance, "_audit_before", None)
    after = _field_values(instance)
    if created:
        action = AuditEvent.Action.CREATED
        changed_fields = list(after)
    elif before is not None:
        action = AuditEvent.Action.UPDATED
        changed_fields = [key for key, value in after.items() if before.get(key) != value]
        if not changed_fields:
            return
    else:
        return
    if not _audit_table_ready():
        return
    AuditEvent.objects.create(
        action=action,
        changed_fields=changed_fields,
        **_audit_metadata(instance),
    )


def after_model_delete(sender, instance, **kwargs):
    if not _is_audited(sender):
        return
    if not _audit_table_ready():
        return
    AuditEvent.objects.create(
        action=AuditEvent.Action.DELETED,
        changed_fields=list(_field_values(instance)),
        **_audit_metadata(instance),
    )


signals.pre_save.connect(before_model_save, dispatch_uid="tintora_audit_before", weak=False)
signals.post_save.connect(after_model_save, dispatch_uid="tintora_audit_after", weak=False)
signals.pre_delete.connect(after_model_delete, dispatch_uid="tintora_audit_delete", weak=False)
