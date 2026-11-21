"""Template tags for admin-managed URLs (announcement bar, hero, promo CTAs)."""

import re
import unicodedata
from decimal import Decimal, InvalidOperation

from django import template
from django.core.cache import cache
from django.db.models import Min
from django.utils.translation import get_language

register = template.Library()

_LANG_PREFIX = re.compile(r"^/[a-z]{2}(/|$)")


@register.simple_tag(takes_context=True)
def localize_url(context, url: str) -> str:
    """Prefix a root-relative path with the active language (``/catalogo/`` →
    ``/es/catalogo/``), leaving absolute URLs, fragments and already-prefixed
    paths untouched. Admin fields can therefore store short routes without
    hardcoding a language.
    """
    if not url:
        return ""
    if url.startswith("/") and not url.startswith("//") and not _LANG_PREFIX.match(url):
        lang = get_language() or "es"
        return f"/{lang}{url}"
    return url


@register.simple_tag
def category_min_price(slug: str) -> str:
    """Lowest configured positive ``base_price`` of the active products in a category.

    Returns an empty string when the category has no active products with a
    configured price, so templates hide "desde …" instead of showing €0.
    Cached for 5 minutes (the mega menu renders on every page).
    """
    cache_key = f"category_min_price:{slug}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    from apps.catalog.models import Category  # noqa: PLC0415

    try:
        minimum = (
            Category.objects.get(slug=slug, is_active=True)
            .products.filter(is_active=True, base_price__gt=0)
            .aggregate(minimum=Min("base_price"))["minimum"]
        )
    except Category.DoesNotExist:
        minimum = None

    if minimum is not None:
        # Normalise the value: on SQLite, aggregates on DecimalField can
        # surface as floats (e.g. "8.90000000000000"), so quantize to a
        # clean 2-decimal price and drop trailing zeros ("29", "11.5").
        try:
            value = str(Decimal(minimum).quantize(Decimal("0.01")).normalize())
        except (InvalidOperation, TypeError, ValueError):
            value = str(minimum)
    else:
        value = ""
    cache.set(cache_key, value, 300)
    return value


@register.simple_tag(takes_context=True)
def wished(context, product) -> bool:
    """True when ``product`` is in the current user's wishlist.

    The full wishlist id set is fetched at most once per request and memoised
    on the request object, so rendering a grid of cards costs a single query.
    """
    request = context.get("request")
    if request is None or not request.user.is_authenticated:
        return False

    wished_ids = getattr(request, "_tintora_wished_ids", None)
    if wished_ids is None:
        from apps.accounts.models import Wishlist  # noqa: PLC0415

        wished_ids = set(
            Wishlist.objects.filter(user=request.user).values_list("product_id", flat=True)
        )
        request._tintora_wished_ids = wished_ids
    return product.id in wished_ids


# ---------------------------------------------------------------------- #
# Verified country-of-origin flags.                                       #
# ---------------------------------------------------------------------- #
# Maps normalised country names (admin-managed ``origin_country`` values)
# to ISO codes + flag emoji. Only verified, admin-entered origins render —
# unknown or blank values return an empty list so origins are never guessed.
_COUNTRY_FLAGS = {
    # Latin America & Caribbean
    "colombia": ("CO", "🇨🇴", "Colombia"),
    "venezuela": ("VE", "🇻🇪", "Venezuela"),
    "mexico": ("MX", "🇲🇽", "México"),
    "peru": ("PE", "🇵🇪", "Perú"),
    "ecuador": ("EC", "🇪🇨", "Ecuador"),
    "argentina": ("AR", "🇦🇷", "Argentina"),
    "chile": ("CL", "🇨🇱", "Chile"),
    "bolivia": ("BO", "🇧🇴", "Bolivia"),
    "cuba": ("CU", "🇨🇺", "Cuba"),
    "republica dominicana": ("DO", "🇩🇴", "República Dominicana"),
    "dominicana": ("DO", "🇩🇴", "República Dominicana"),
    "guatemala": ("GT", "🇬🇹", "Guatemala"),
    "honduras": ("HN", "🇭🇳", "Honduras"),
    "el salvador": ("SV", "🇸🇻", "El Salvador"),
    "nicaragua": ("NI", "🇳🇮", "Nicaragua"),
    "costa rica": ("CR", "🇨🇷", "Costa Rica"),
    "panama": ("PA", "🇵🇦", "Panamá"),
    "paraguay": ("PY", "🇵🇾", "Paraguay"),
    "uruguay": ("UY", "🇺🇾", "Uruguay"),
    "brasil": ("BR", "🇧🇷", "Brasil"),
    "haiti": ("HT", "🇭🇹", "Haití"),
    "jamaica": ("JM", "🇯🇲", "Jamaica"),
    # Europe & rest of the world
    "espana": ("ES", "🇪🇸", "España"),
    "portugal": ("PT", "🇵🇹", "Portugal"),
    "italia": ("IT", "🇮🇹", "Italia"),
    "francia": ("FR", "🇫🇷", "Francia"),
    "alemania": ("DE", "🇩🇪", "Alemania"),
    "marruecos": ("MA", "🇲🇦", "Marruecos"),
    "argelia": ("DZ", "🇩🇿", "Argelia"),
    "senegal": ("SN", "🇸🇳", "Senegal"),
    "costa de marfil": ("CI", "🇨🇮", "Costa de Marfil"),
    "camerun": ("CM", "🇨🇲", "Camerún"),
    "ghana": ("GH", "🇬🇭", "Ghana"),
    "nigeria": ("NG", "🇳🇬", "Nigeria"),
    "eeuu": ("US", "🇺🇸", "EE. UU."),
    "estados unidos": ("US", "🇺🇸", "EE. UU."),
    "china": ("CN", "🇨🇳", "China"),
    "india": ("IN", "🇮🇳", "India"),
}

_ORIGIN_SPLIT_RE = re.compile(r"[/,;&+|]+")


def _normalise_country(value: str) -> str:
    value = unicodedata.normalize("NFD", value.strip().lower())
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    return " ".join(value.split())


@register.filter
def country_flags(origin_country: str) -> list:
    """Verified origin flags for ``Product.origin_country``.

    Splits multi-origin values ("Venezuela / Colombia") and returns a list of
    ``{"code", "flag", "name"}`` dicts. Unknown or blank origins yield ``[]``.
    """
    if not origin_country:
        return []
    flags = []
    seen = set()
    for part in _ORIGIN_SPLIT_RE.split(origin_country):
        key = _normalise_country(part)
        entry = _COUNTRY_FLAGS.get(key)
        if entry and entry[0] not in seen:
            seen.add(entry[0])
            flags.append({"code": entry[0], "flag": entry[1], "name": entry[2]})
    return flags
