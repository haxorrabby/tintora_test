import json

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def json_ld(data):
    serialized = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    serialized = serialized.replace("&", "\\u0026").replace("<", "\\u003C").replace(">", "\\u003E")
    return mark_safe(f'<script type="application/ld+json">{serialized}</script>')
