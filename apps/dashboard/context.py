from contextvars import ContextVar

current_actor = ContextVar("tintora_audit_actor", default=None)
current_request = ContextVar("tintora_audit_request", default=None)
