import re

from django.conf import settings
from django.templatetags.static import static
from django.urls import translate_url
from django.utils import timezone

from apps.latin_products.data import get_catalog, product_total


def tintora_globals(request):
    """
    Global context processor injecting brand constants, Madrid company contact details,
    VAT rate, helper flags and the latin catalog categories (header mega menu/footer)
    into every template render. The latin catalog is served from the database.
    """
    from .models import HomepageSettings  # noqa: PLC0415

    latin_catalog = get_catalog()
    return {
        "COMPANY": settings.TINTORA_COMPANY,
        "BANK_IBAN": getattr(settings, "TINTORA_BANK_IBAN", ""),
        "BANK_BIC": getattr(settings, "TINTORA_BANK_BIC", ""),
        "IVA_PERCENTAGE": settings.TINTORA_IVA_PERCENTAGE,
        "CURRENT_YEAR": timezone.now().year,
        "ADMIN_URL_PATH": settings.ADMIN_URL_PATH,
        "AVAILABLE_LANGUAGES": settings.LANGUAGES,
        "LATIN_CATEGORIES": latin_catalog["categories"],
        "LATIN_PRODUCT_COUNT": product_total(),
        # Admin-managed announcement bar + newsletter copy (cached singleton)
        "home_content": HomepageSettings.get_cached(),
    }


def seo_globals(request):
    site_url = request.build_absolute_uri("/").rstrip("/")
    alternates = []
    for language_code, _language_name in settings.LANGUAGES:
        translated_path = translate_url(request.path_info, language_code)
        if translated_path:
            alternates.append(
                {
                    "language": language_code,
                    "url": request.build_absolute_uri(translated_path),
                }
            )

    company = settings.TINTORA_COMPANY
    logo_url = request.build_absolute_uri(static("images/brand/tintora-logo-dark.svg"))
    address_parts = [part.strip() for part in company["ADDRESS"].split(",")]
    postal_index = next(
        (index for index, part in enumerate(address_parts) if re.match(r"^\d{5}\b", part)),
        None,
    )
    if postal_index is None:
        street_address = company["ADDRESS"]
        postal_code = ""
        locality = ""
        region = ""
        country = ""
    else:
        street_address = ", ".join(address_parts[:postal_index])
        postal_locality = address_parts[postal_index].split(maxsplit=1)
        postal_code = postal_locality[0]
        locality = postal_locality[1] if len(postal_locality) > 1 else ""
        region = address_parts[postal_index + 1] if len(address_parts) > postal_index + 1 else ""
        country = address_parts[postal_index + 2] if len(address_parts) > postal_index + 2 else ""
    organization_schema = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Organization",
                "@id": f"{site_url}/#organization",
                "name": "Tintora",
                "legalName": company["NAME"],
                "url": site_url,
                "logo": logo_url,
                "email": company["EMAIL"],
                "telephone": company["PHONE"],
            },
            {
                "@type": "Store",
                "@id": f"{site_url}/#localbusiness",
                "name": "Tintora Madrid",
                "url": site_url,
                "image": logo_url,
                "telephone": company["PHONE"],
                "priceRange": "€€",
                "currenciesAccepted": "EUR",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": street_address,
                    "postalCode": postal_code,
                    "addressLocality": locality,
                    "addressRegion": region,
                    "addressCountry": country,
                },
                "openingHours": "Mo-Fr 09:30-19:30, Sa 10:00-14:00",
                "areaServed": ["Madrid", "España", "Unión Europea"],
            },
        ],
    }
    return {
        "canonical_url": request.build_absolute_uri(request.path),
        "hreflang_alternates": alternates,
        "organization_schema": organization_schema,
    }
