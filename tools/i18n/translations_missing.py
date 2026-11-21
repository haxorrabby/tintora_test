"""Extra English translations (second pass).

Bulk set recovered from the built catalog (``translations_recovered.py``) plus
the attribute/placeholder strings surfaced by ``wrap_attrs.py``. ``build.py``
merges these on top of the hand-curated ``translations_en.py``.
"""

from translations_recovered import EXTRA_PLURALS as _RECOVERED_PLURALS
from translations_recovered import EXTRA_TRANSLATIONS as _RECOVERED_TRANSLATIONS

EXTRA_TRANSLATIONS = {
    **_RECOVERED_TRANSLATIONS,
    "En stock": "In stock",
    "Pedir por WhatsApp": "Order on WhatsApp",
    "Precio por unidad": "Price per unit",
    "Unidad": "Unit",
    "Alternar tema claro y oscuro": "Toggle light and dark theme",
    "Aumentar cantidad": "Increase quantity",
    "Añadir a la lista de deseos": "Add to wishlist",
    "Carlos Martínez": "Carlos Martínez",
    "Contactar por WhatsApp con Tintora Madrid": "Contact Tintora Madrid on WhatsApp",
    "Cuéntanos tu proyecto, la funcionalidad principal, si tienes referentes visuales y el presupuesto aproximado...": "Tell us about your project, the core functionality, whether you have visual references and the approximate budget...",
    "Describe los ajustes que debemos realizar": "Describe the changes we need to make",
    "Disminuir cantidad": "Decrease quantity",
    "Duplicar esta configuración": "Duplicate this configuration",
    "Ej. 3º Izquierda": "e.g. 3rd floor, left",
    "Ej. B-88776655 o 12345678Z": "e.g. B-88776655 or 12345678Z",
    "Ej. Calle de Alcalá 120": "e.g. Calle de Alcalá 120",
    "Ej. Dejar en conserjería si no estamos en horario comercial...": "e.g. Leave with the concierge if we are not open...",
    "Ej. Estudio Creativo Alcalá S.L.": "e.g. Estudio Creativo Alcalá S.L.",
    "Ej. Gómez Méndez": "e.g. Gómez Méndez",
    "Ej. Laura": "e.g. Laura",
    "Ej. MADRID10": "e.g. MADRID10",
    "Eliminar del carrito": "Remove from cart",
    "Estudio Creativo S.L.": "Estudio Creativo S.L.",
    "Impresión profesional: tarjetas y packaging premium": "Professional printing: premium cards and packaging",
    "Menú móvil": "Mobile menu",
    "No incluido": "Not included",
    "Productos latinos: harinas, café y snacks": "Latin products: flours, coffee and snacks",
    "Quitar de la lista de deseos": "Remove from wishlist",
    "Ruta de navegación": "Breadcrumb",
    "Sublimación: tazas, camisetas y gorras personalizadas": "Sublimation: custom mugs, t-shirts and caps",
    "hola@empresa.es": "hello@company.com",
    "laura@empresa.es": "laura@company.com",
    "tu@correo.es": "you@email.com",
}

EXTRA_PLURALS = {
    **_RECOVERED_PLURALS,
    "%(counter)s artículo": ("%(counter)s item", "%(counter)s items"),
    "%(counter)s artículo en la cesta": ("%(counter)s item in the basket", "%(counter)s items in the basket"),
    "%(counter)s producto": ("%(counter)s product", "%(counter)s products"),
    "%(counter)s producto en tu cesta": ("%(counter)s product in your basket", "%(counter)s products in your basket"),
    "%(counter)s vista": ("%(counter)s view", "%(counter)s views"),
}
