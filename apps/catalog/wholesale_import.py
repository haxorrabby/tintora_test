"""Pure helpers for importing the two supplied wholesale PDF catalogs.

Parses distributor catalogs (case-based listings, no retail prices) into
individual retail-unit entries without inventing prices, origins or images:

* every entry keeps its distributor ``code`` (→ ``Product.sku``), its
  individual ``size`` (→ display name + ``weight_grams``) and its wholesale
  case info (kept in the admin-facing description only);
* deduplication is by ``code`` first, then by normalised (name, size).

Span extraction (PyMuPDF) lives in the management command; everything here
operates on plain ``{"text", "font", "size", "bbox", "page"}`` dicts so the
parsers are unit-testable without the PDFs.
"""

from __future__ import annotations

import re
import unicodedata

BULLET = "\u2022"

AMERICA_DETAIL_RE = re.compile(
    r"^([A-Z]{2,4}\d{2,4})\s*\u2022\s*(.+?)\s*\u2022\s*[Cc]aja\s+(\d+)\s*[Uu]ds?\.?\s*$"
)
AMERICA_DETAIL_FALLBACK_RE = re.compile(
    r"^([A-Z]{2,4}\d{2,4})\s*[^\w\s]\s*(.+?)\s*[^\w\s]\s*[Cc]aja\s+(\d+)\s*[Uu]ds?\.?\s*$"
)
# Some references are sold per unit in the wholesale catalog
# (``HA006 • 1 Kg • UNIDAD``) — ideal individual retail units.
AMERICA_UNIT_RE = re.compile(
    r"^([A-Z]{2,4}\d{2,4})\s*[^\w\s]\s*(.+?)\s*[^\w\s]\s*UNIDAD\s*\.?\s*$",
    re.IGNORECASE,
)
# Codes may carry a suffix variant (``Cod: PLG077-1``).
LATINO_COD_RE = re.compile(r"^Cod:\s*([A-Z]+\d+(?:-\d+)?)\s*$")
# ``SIZE x CASE`` with an optional trailing display pack (``50g x 12 Displ. x 12``).
LATINO_PACK_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb|uds?|u))\s*[x×]\s*(\d+)"
    r"(?:\s+displ\.?\s*[x×]\s*\d+)?\s*$",
    re.IGNORECASE,
)
# Count-first pack format: ``12 Unid. 100g x 40`` / ``24 Unid x 17g x 15``.
LATINO_PACK_COUNT_FIRST_RE = re.compile(
    r"^(\d+)\s*(?:unid\.?|uds?|u)\.?\s*[x×]?\s*"
    r"(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Multi-pack: ``2 x 160g x 12`` — the retail unit is one 160 g pack.
LATINO_MULTI_PACK_RE = re.compile(
    r"^(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Size with inner unit count: ``5g x 50 Unid. x 24`` / ``450g x 5 Unid. x 24``.
LATINO_SIZE_UNITS_PACK_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*[x×]\s*(\d+)\s*"
    r"(?:unid\.?|uds?|u)\.?\s*[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Count-first without a size: ``2 Unid. x 12`` — the retail unit is N units.
LATINO_UNITS_ONLY_RE = re.compile(
    r"^(\d+)\s*(?:unid\.?|uds?|u)\.?\s*[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Count-first with a parenthesised size: ``2 unid. (260g) x 5``.
LATINO_UNITS_PAREN_RE = re.compile(
    r"^(\d+)\s*(?:unid\.?|uds?|u)\.?\s*\(\s*"
    r"(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*\)\s*[x×]\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Bulk sack: ``5kg x 300-500g 1`` — the sack itself is the retail unit.
LATINO_BULK_SACK_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*[x×]\s*[\d.,\-–]+\s*"
    r"(?:g|kg|oz|lb|ml|l)?\s*(\d+)\s*$",
    re.IGNORECASE,
)
# Bulk sacks printed as a bare size (``25kg``) — single retail unit.
LATINO_BARE_SIZE_RE = re.compile(
    r"^(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|ml|l|cl|oz|lb))\s*$",
    re.IGNORECASE,
)

_SIZE_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(kg|g|gr|ml|l|cl|oz|lb)\b",
    re.IGNORECASE,
)
_UNIT_NORMALIZE = {"gr": "g", "lt": "l"}


def span_text(chars: str) -> str:
    """Collapse whitespace in an extracted span string."""
    return " ".join(chars.split())


def title_name(name: str) -> str:
    """Title-case a catalogue name while keeping acronyms readable.

    Short uppercase tokens (``PAN``, ``P.A.N.``) keep their styling; longer
    all-caps words (``AMÉRICA``) become ``América`` for consistent display.
    """
    words = []
    for word in span_text(name).split(" "):
        if not word:
            continue
        bare = word.replace(".", "")
        if "." in word or (bare.isupper() and len(bare) <= 3):
            words.append(word.upper())
        elif "-" in word:
            words.append("-".join(w[:1].upper() + w[1:].lower() for w in word.split("-")))
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def normalize_size_display(size: str) -> str:
    """'425ml' → '425 ml', '3Kg' → '3 kg', '500 gr' → '500 g'."""
    size = span_text(size)
    match = _SIZE_RE.search(size)
    if not match:
        return size
    number = match.group(1).replace(",", ".")
    unit = _UNIT_NORMALIZE.get(match.group(2).lower(), match.group(2).lower())
    return f"{number} {unit}"


def weight_grams_from_size(size: str) -> int:
    """Net weight in grams for weight-based sizes, else 0 (volumes/units).

    Pound/ounce sizes are converted with the exact factors (1 lb = 453.592 g,
    1 oz = 28.3495 g) so shipping estimates stay accurate; the displayed
    size string always keeps the catalog's own unit.
    """
    match = _SIZE_RE.search(size or "")
    if not match:
        return 0
    try:
        number = float(match.group(1).replace(",", "."))
    except ValueError:
        return 0
    unit = _UNIT_NORMALIZE.get(match.group(2).lower(), match.group(2).lower())
    if unit == "kg":
        return int(round(number * 1000))
    if unit == "g":
        return int(round(number))
    if unit == "lb":
        return int(round(number * 453.592))
    if unit == "oz":
        return int(round(number * 28.3495))
    return 0


def norm_key(name: str, size: str) -> str:
    """Accent/case-insensitive dedupe key for (name, size)."""
    raw = f"{name} {size}".lower()
    raw = unicodedata.normalize("NFD", raw)
    raw = "".join(c for c in raw if unicodedata.category(c) != "Mn")
    return " ".join(raw.split())


# Brands the América Foods catalog explicitly highlights as ``MARCAS
# DESTACADAS`` — a brand is only set when it literally appears in the product
# name, never inferred from the packaging.
AMERICA_BRANDS = (
    ("ORIENTAL", "Oriental"),
    ("TESORO NATURAL", "Tesoro Natural"),
    ("BALDOM", "Baldom"),
    ("PONY MALTA", "Pony Malta"),
)

# Explicit origin statements printed in the catalogs (``Fabricada en Colombia
# desde 1953``). Matched case/accent-insensitively against free text lines.
ORIGIN_STATEMENT_RE = re.compile(
    r"(?:fabricad[oa]|hech[oa]|elaborad[oa]|producto\s+de)\s+(?:en|de)\s+([a-záéíóúñ]+)",
    re.IGNORECASE,
)
ORIGIN_COUNTRIES = {
    "colombia": "Colombia",
    "venezuela": "Venezuela",
    "mexico": "México",
    "peru": "Perú",
    "ecuador": "Ecuador",
    "brasil": "Brasil",
    "argentina": "Argentina",
    "chile": "Chile",
    "bolivia": "Bolivia",
    "españa": "España",
    "espana": "España",
}


def brand_for_name(name: str) -> str:
    """Explicit catalog brand contained in a product name, else ``""``."""
    upper = span_text(name).upper()
    for token, brand in AMERICA_BRANDS:
        if token in upper:
            return brand
    return ""


def origin_from_statement(text: str) -> str:
    """Country of origin from an explicit catalog statement, else ``""``."""
    match = ORIGIN_STATEMENT_RE.search(span_text(text))
    if not match:
        return ""
    return ORIGIN_COUNTRIES.get(match.group(1).lower(), "")


def _is_america_name(span: dict) -> bool:
    return "Bold" in span["font"] and round(span["size"], 1) == 8.0


def _is_america_detail(span: dict) -> bool:
    return "Regular" in span["font"] and round(span["size"], 1) == 7.0


def _is_america_section(span: dict) -> bool:
    return (
        "Bold" in span["font"]
        and round(span["size"], 1) == 12.0
        and "Condensed" in span["font"]
    )


def parse_america_spans(spans: list) -> list:
    """Parse América Foods spans into retail-unit entries.

    A product name (Bold 8.0, possibly multi-line) is followed by one or more
    detail lines ``CODE • size • Caja N Uds.`` — one entry per detail line.
    """
    entries = []
    section = ""
    pending_names: list = []
    pending_box = None
    pending_origin = ""
    needs_reset = False
    for span in spans:
        text = span_text(span["text"])
        if not text:
            continue
        if _is_america_section(span):
            section = text.rstrip(f" {BULLET}·").strip()
            pending_names = []
            pending_box = None
            pending_origin = ""
            needs_reset = False
            continue
        if _is_america_name(span):
            if needs_reset:
                pending_names = []
                pending_box = None
                needs_reset = False
            pending_names.append(text)
            if pending_box is None:
                pending_box = tuple(span.get("bbox", (0, 0, 0, 0)))
            continue
        if _is_america_detail(span):
            match = AMERICA_DETAIL_RE.match(text) or AMERICA_DETAIL_FALLBACK_RE.match(text)
            unit_match = None if match else AMERICA_UNIT_RE.match(text)
            picked = match or unit_match
            if picked and pending_names:
                code, size = picked.group(1), picked.group(2)
                case_qty = picked.group(3) if match else "1"
                name = " ".join(pending_names)
                entries.append(
                    {
                        "source": "america",
                        "code": code,
                        "name": name,
                        "size": span_text(size),
                        "case_qty": case_qty,
                        "section": section,
                        "origin": pending_origin,
                        "brand": brand_for_name(name),
                        "page": span.get("page", 0),
                        "_box": pending_box,
                    }
                )
                needs_reset = True
                continue
        # Explicit origin statement (``Fabricada en Colombia desde 1953``),
        # printed either as a free-text detail line or in a display font,
        # applies to the products that follow it within the same section.
        origin = origin_from_statement(text)
        if origin:
            pending_origin = origin
            continue
        # Any other span (promo lines, page numbers) breaks name grouping.
        if pending_names and ("Bold" in span["font"] or "Charcoal" in span["font"]):
            pending_names = []
            pending_box = None
            needs_reset = False
    return entries


def parse_latinoandina_spans(spans: list) -> list:
    """Parse Distribuidora Latinoandina spans into retail-unit entries.

    Pattern per product: 1–2 Bold name lines, ``Cod: XXX`` line, then
    ``SIZE x CASE`` line (optionally ``N Unid. SIZE x CASE`` or with a
    trailing ``Displ. x N``). A trailing Bold line without a following
    ``Cod:`` line is treated as a brand qualifier for the previous name.
    """
    entries = []
    section = ""
    name_lines: list = []
    name_box = None
    for span in spans:
        text = span_text(span["text"])
        if not text:
            continue
        font, size = span["font"], round(span["size"], 1)
        if "Atlanta" in font and size >= 20.0 and "www" not in text and "@" not in text:
            section = text
            name_lines = []
            name_box = None
            continue
        if "Bold" in font:
            if not name_lines:
                name_box = tuple(span.get("bbox", (0, 0, 0, 0)))
            name_lines.append(text)
            continue
        cod = LATINO_COD_RE.match(text)
        if cod and name_lines:
            entries.append(
                {
                    "source": "latinoandina",
                    "code": cod.group(1),
                    "name": " ".join(name_lines),
                    "brand": "",
                    "size": "",
                    "case_qty": "",
                    "section": section,
                    "origin": "",
                    "page": span.get("page", 0),
                    "_box": name_box,
                }
            )
            name_lines = []
            name_box = None
            continue
        # Pack formats — most specific first. All only fill the size of the
        # most recent entry that does not have one yet.
        pack = LATINO_PACK_RE.match(text)
        if pack and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(pack.group(1))
            entries[-1]["case_qty"] = pack.group(2)
            continue
        multi = LATINO_MULTI_PACK_RE.match(text)
        if multi and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(multi.group(2))
            entries[-1]["case_qty"] = multi.group(3)
            continue
        size_units = LATINO_SIZE_UNITS_PACK_RE.match(text)
        if size_units and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(size_units.group(1))
            entries[-1]["case_qty"] = size_units.group(3)
            continue
        count_first = LATINO_PACK_COUNT_FIRST_RE.match(text)
        if count_first and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(count_first.group(2))
            entries[-1]["case_qty"] = count_first.group(3)
            continue
        units_paren = LATINO_UNITS_PAREN_RE.match(text)
        if units_paren and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(units_paren.group(2))
            entries[-1]["case_qty"] = units_paren.group(3)
            continue
        units_only = LATINO_UNITS_ONLY_RE.match(text)
        if units_only and entries and not entries[-1]["size"]:
            entries[-1]["size"] = f"{units_only.group(1)} uds."
            entries[-1]["case_qty"] = units_only.group(2)
            continue
        bulk = LATINO_BULK_SACK_RE.match(text)
        if bulk and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(bulk.group(1))
            entries[-1]["case_qty"] = bulk.group(2)
            continue
        bare = LATINO_BARE_SIZE_RE.match(text)
        if bare and entries and not entries[-1]["size"]:
            entries[-1]["size"] = span_text(bare.group(1))
            entries[-1]["case_qty"] = "1"
            continue
        name_lines = []
        name_box = None
    return [e for e in entries if e["code"]]


def dedupe_entries(entries: list) -> tuple:
    """Split ``entries`` into (unique, skipped) for one parse run.

    A distributor code (or a normalised ``(name, size)`` pair) printed in two
    catalog sections is one product — the second occurrence is skipped.
    DB matching is the caller's job (see the import command).
    """
    unique, skipped = [], []
    seen_codes, seen_keys = set(), set()
    for entry in entries:
        code = (entry.get("code") or "").upper()
        key = norm_key(
            f"{entry.get('name', '')} {entry.get('brand', '')}",
            normalize_size_display(entry.get("size", "")),
        )
        if not code or code in seen_codes or key in seen_keys:
            skipped.append(entry)
            continue
        seen_codes.add(code)
        seen_keys.add(key)
        unique.append(entry)
    return unique, skipped


def match_images_to_names(
    name_boxes: list, image_boxes: list
) -> dict:
    """Match product-name bboxes to product image bboxes on one catalog page.

    The product name is printed over the *lower* part of its photo, so the
    correct photo is the one that horizontally centre-aligns with the name
    while vertically overlapping it. Relying on the exact pixel boundary is
    brittle (a 1 px difference flips the match), so candidates are scored by
    the size of the vertical overlap with the name box and, failing that, by
    the smallest vertical gap (``<= 45`` pt). Returns
    ``{name_index: image_index}``.
    """
    matches = {}
    used = set()
    for ni, (nx0, ny0, nx1, ny1) in enumerate(name_boxes):
        cx = (nx0 + nx1) / 2
        best, best_score = None, None
        for ii, (ix0, iy0, ix1, iy1) in enumerate(image_boxes):
            if ii in used:
                continue
            if not (ix0 <= cx <= ix1):
                continue
            if (iy1 - iy0) < 60:
                continue
            overlap = min(ny1, iy1) - max(ny0, iy0)
            if overlap > 0:
                score = (0, -overlap)  # prefer the largest vertical overlap
            else:
                gap = max(iy0, ny0) - min(iy1, ny1)
                if gap > 45:
                    continue
                score = (1, gap)  # else the smallest gap below the photo
            if best is None or score < best_score:
                best, best_score = ii, score
        if best is not None:
            matches[ni] = best
            used.add(best)
    return matches


# --------------------------------------------------------------------------
# Embedded-image orientation
# --------------------------------------------------------------------------
# PDF producers draw an embedded photo through a matrix. ``Pixmap(doc, xref)``
# hands back the samples *exactly as stored*, which for a large share of the
# América Foods catalog is vertically mirrored relative to how the page draws
# them (the plain ``[w 0 0 -h x y]`` placement), so saving the raw samples
# stores an upside-down photo. These helpers work out which of the eight
# dihedral transforms has to be applied to the raw samples to reproduce what
# the catalog page actually shows.

#: op -> how it re-maps an image's local direction pair ``(right, down)``,
#: where ``right`` = "(a, b)" and ``down`` = "(c, d)" of the draw matrix.
_ORIENTATION_MAP = {
    "identity": lambda r, d: (r, d),
    "flip_v": lambda r, d: (r, (-d[0], -d[1])),
    "flip_h": lambda r, d: ((-r[0], -r[1]), d),
    "r180": lambda r, d: ((-r[0], -r[1]), (-d[0], -d[1])),
    "r90": lambda r, d: (d, (-r[0], -r[1])),  # 90° counter-clockwise
    "r270": lambda r, d: ((-d[0], -d[1]), r),  # 90° clockwise
    "transpose": lambda r, d: (d, r),  # mirror over the main diagonal
    "transverse": lambda r, d: ((-d[0], -d[1]), (-r[0], -r[1])),
}

#: Inverse of each op (only the quarter-turns are not self-inverse).
_INVERSE_ORIENTATION = {
    "identity": "identity",
    "flip_v": "flip_v",
    "flip_h": "flip_h",
    "r180": "r180",
    "r90": "r270",
    "r270": "r90",
    "transpose": "transpose",
    "transverse": "transverse",
}


def orientation_from_matrix(matrix) -> str:
    """Dihedral op that turns a raw extracted pixmap into the drawn image.

    ``matrix`` is ``(a, b, c, d, e, f)`` as reported by
    ``page.get_image_info()``: it maps the unit square of image space onto the
    page, the image's columns travelling along ``(a, b)`` and its sample rows
    along ``(c, d)``. A photo reads "upright" once its columns point right
    and its rows point down on the page, so the returned op is whichever of
    the eight orientations re-aims the pair at ``((1, 0), (0, 1))``.
    """
    a, b, c, d = matrix[:4]

    def quantise(x, y):
        """Nearest axis direction; the dominant component decides the sign."""
        if abs(x) >= abs(y):
            return (1.0, 0.0) if x >= 0 else (-1.0, 0.0)
        return (0.0, 1.0) if y >= 0 else (0.0, -1.0)

    right, down = quantise(a, b), quantise(c, d)
    for name, map_op in _ORIENTATION_MAP.items():
        if map_op(right, down) == ((1.0, 0.0), (0.0, 1.0)):
            return name
    return "identity"  # unreachable: the group always contains a solution


def _grayscale_grid(image, size: int = 48):
    from PIL import Image  # noqa: PLC0415

    return image.convert("L").resize((size, size), Image.Resampling.BOX)


def orientation_from_pixels(raw_image, drawn_image) -> tuple:
    """Best-matching op by comparing raw samples to the rendered page region.

    Returns ``(op, confident)``. The rendered region is the catalog's own
    drawing, so a confident answer is definitive; rotated/skewed placements
    leave the answer ambiguous and the caller should fall back to the matrix
    rule (:func:`orientation_from_matrix`).
    """
    from PIL import ImageChops  # noqa: PLC0415

    target = _grayscale_grid(drawn_image)
    scored = []
    for name, candidate in _iter_orientations(raw_image):
        diff = ImageChops.difference(_grayscale_grid(candidate), target).histogram()
        total = sum(diff) or 1
        scored.append((sum(i * n for i, n in enumerate(diff)) / total, name))
    scored.sort()
    (best_mad, best), (second_mad, _) = scored[0], scored[1]
    return best, best_mad <= 22 and (second_mad - best_mad) >= 1.5


def _iter_orientations(image):
    """The eight dihedral orientations of ``image``, keyed by op name."""
    from PIL import Image  # noqa: PLC0415

    t = Image.Transpose
    transposes = {
        "identity": None,
        "r90": t.ROTATE_90,
        "r180": t.ROTATE_180,
        "r270": t.ROTATE_270,
        "flip_v": t.FLIP_TOP_BOTTOM,
        "flip_h": t.FLIP_LEFT_RIGHT,
        "transpose": t.TRANSPOSE,
        "transverse": t.TRANSVERSE,
    }
    for name, op in transposes.items():
        yield name, image if op is None else image.transpose(op)


def _placement_matrix(page, xref: int):
    """Draw matrix ``(a, b, c, d, e, f)`` of ``xref`` on ``page``, if any."""
    try:
        for info in page.get_image_info(xrefs=True):
            if info.get("xref") == xref:
                return info.get("transform")
    except Exception:  # pragma: no cover - defensive
        return None
    return None


def _raw_rgb_image(page, xref: int):
    """Stored samples of ``xref`` as a PIL RGB image, in their raw order."""
    import io  # noqa: PLC0415

    import pymupdf  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    pix = pymupdf.Pixmap(page.parent, xref)
    if pix.n - pix.alpha > 3:  # CMYK → RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")


def apply_orientation(image, op: str):
    """Return ``image`` with the named dihedral op applied."""
    for name, candidate in _iter_orientations(image):
        if name == op:
            return candidate
    return image


def image_display_orientation(page, xref: int, bbox) -> str:
    """Op needed to make the raw samples of ``xref`` match the page drawing.

    Compares the extracted samples with the rendered placement region; when
    that comparison is inconclusive (decoratively rotated placements) it
    falls back to the placement matrix rule.
    """
    import io  # noqa: PLC0415

    import pymupdf  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    try:
        raw = _raw_rgb_image(page, xref)
    except Exception:  # pragma: no cover - defensive
        matrix = _placement_matrix(page, xref)
        return orientation_from_matrix(matrix) if matrix else "identity"

    if bbox is not None:
        try:
            clip = pymupdf.Rect(bbox)
            if clip.width > 1 and clip.height > 1:
                pix = page.get_pixmap(clip=clip, dpi=72, colorspace=pymupdf.csRGB)
                drawn = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                op, confident = orientation_from_pixels(raw, drawn)
                if confident:
                    return op
        except Exception:  # pragma: no cover - defensive
            pass

    matrix = _placement_matrix(page, xref)
    return orientation_from_matrix(matrix) if matrix else "identity"


def orientation_status(path, page, xref: int, bbox) -> str:
    """How a saved JPEG relates to the catalog's drawing of one photo.

    Returns one of:

    ``correct``
        the file already reads the way the page draws the photo;
    ``stale``
        the file still holds the raw, mirrored samples → re-encode it;
    ``unrelated``
        the file does not resemble this placement's samples at all (the
        positional match picked another photo) → never touch it;
    ``drawn-as-stored``
        the page draws the stored samples as-is → nothing to correct.

    Every branch is a pixel comparison against the catalog itself, so the
    check is repeatable and never rewrites an already-correct file.
    """
    from PIL import Image  # noqa: PLC0415

    if image_display_orientation(page, xref, bbox) == "identity":
        return "drawn-as-stored"
    raw = _raw_rgb_image(page, xref)
    current = Image.open(path).convert("RGB")
    to_raw, confident = orientation_from_pixels(current, raw)
    if not confident:
        return "unrelated"
    if to_raw == "identity":
        return "stale"
    drawn_op = image_display_orientation(page, xref, bbox)
    return (
        "correct"
        if to_raw == _INVERSE_ORIENTATION[drawn_op]
        else "unrelated"
    )


def needs_orientation_fix(path, page, xref: int, bbox) -> bool:
    """True only when the file still holds the raw, mirrored samples."""
    return orientation_status(path, page, xref, bbox) == "stale"


def oriented_image_jpeg(page, xref: int, bbox, quality: int = 92) -> bytes | None:
    """JPEG bytes of the embedded photo, oriented like the catalog draws it.

    The EXIF orientation tag is never written, so no client can apply a
    second, phantom rotation on top of the corrected pixels.
    """
    import io  # noqa: PLC0415

    try:
        image = apply_orientation(
            _raw_rgb_image(page, xref), image_display_orientation(page, xref, bbox)
        )
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue()
    except Exception:  # pragma: no cover - defensive
        return None


def column_bounds_for_names(name_boxes: list, page_width: float) -> list:
    """Horizontal cell bounds ``(x0, x1)`` for each name box on one page.

    Catalog pages lay products out in fixed columns. Name-box centres are
    clustered (tolerance 45 pt); each cluster becomes one column whose outer
    edges are the midpoints to its neighbours. Lets the Latinoandina importer
    crop the flat page raster without spilling into the neighbouring cells.
    """
    if not name_boxes:
        return []
    centres = sorted((b[0] + b[2]) / 2 for b in name_boxes)
    clusters = [[centres[0]]]
    for centre in centres[1:]:
        if centre - clusters[-1][-1] <= 45:
            clusters[-1].append(centre)
        else:
            clusters.append([centre])
    col_centres = [sum(c) / len(c) for c in clusters]
    count = len(col_centres)
    bounds = []
    for i, centre in enumerate(col_centres):
        if count == 1:
            bounds.append((max(0.0, centre - 75), min(page_width, centre + 75)))
            continue
        left = (
            (col_centres[i - 1] + centre) / 2
            if i > 0
            else centre - (col_centres[1] - centre) / 2
        )
        right = (
            (centre + col_centres[i + 1]) / 2
            if i < count - 1
            else centre + (centre - col_centres[i - 1]) / 2
        )
        bounds.append((max(0.0, left), min(page_width, right)))
    result = []
    for box in name_boxes:
        centre = (box[0] + box[2]) / 2
        idx = min(range(count), key=lambda i: abs(col_centres[i] - centre))
        result.append(bounds[idx])
    return result
