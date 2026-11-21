"""Wrap hardcoded Spanish text nodes in templates with {% trans %}.

Only *simple* text nodes are wrapped automatically. Template tags
(``{{ }}`` / ``{% %}``) and the bodies of ``<script>/<style>/<pre>/<code>``
are blanked out (length-preserving) before locating text, so a ``>`` inside
a template expression or a JS/CSS block can never be mistaken for a tag
close. Nodes that still contain a quote are skipped and reported, because
they usually mean the ``>`` belonged to an HTML attribute or the prose itself
needs manual handling.

Whitespace inside a node is collapsed to a single space (HTML collapses it
anyway); leading/trailing whitespace stays outside the ``{% trans %}`` tag.

Usage:
    python tools/i18n/wrap_templates.py --dry-run
    python tools/i18n/wrap_templates.py
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
TEMPLATES = BASE / "templates"
APPS = BASE / "apps"

# Blank script/style/pre/code bodies AND template tags, keeping newlines.
MASK_RE = re.compile(
    r"\{%\s*blocktrans(?:late)?\b.*?%\}.*?\{%\s*endblocktrans\s*%\}"  # blocktrans blocks
    r"|<(script|style|pre|code)\b[^>]*>.*?</\1>|"  # code-ish blocks
    r"\{\{.*?\}\}"  # {{ variable }}
    r"|\{%.*?%\}"  # {% tag %}
    r"|\{#.*?#\}",  # {# comment #}
    re.S | re.I,
)
TEXT_RE = re.compile(r"(?<=>)([^<>]+)(?=<)")


def mask_tag_gt(src: str) -> str:
    """Blank any ``>`` that sits inside a quoted HTML attribute.

    Without this, an attribute like ``x-data="{ (a) => a < b }"`` would make the
    ``=>`` and ``<`` look like a text node, and the wrapper would corrupt it.
    The real closing ``>`` of each tag is preserved.
    """
    out = list(src)
    i, n = 0, len(src)
    while i < n:
        if src[i] == "<":
            j, quote = i + 1, None
            while j < n:
                c = src[j]
                if quote:
                    if c == quote:
                        quote = None
                elif c in ('"', "'"):
                    quote = c
                elif c == ">":
                    break
                j += 1
            if j < n:
                k, quote = i, None
                while k < j:
                    c = src[k]
                    if quote:
                        if c == quote:
                            quote = None
                        elif c == ">":
                            out[k] = " "
                    elif c in ('"', "'"):
                        quote = c
                    k += 1
                i = j + 1
                continue
        i += 1
    return "".join(out)
HAS_LETTERS = re.compile(r"[A-Za-zÀ-ÿ]")
I18N_LOAD_RE = re.compile(r"\{%\s*load\b[^%]*\bi18n\b[^%]*%\}")

EXCLUDE_NAMES = {"styleguide.html"}
EXCLUDE_PARENT = TEMPLATES / "admin"


def iter_templates():
    for root in (TEMPLATES, APPS):
        for path in root.rglob("*.html"):
            if any(part in {".venv", "staticfiles", "node_modules"} for part in path.parts):
                continue
            if path.name in EXCLUDE_NAMES:
                continue
            if EXCLUDE_PARENT in path.parents:
                continue
            yield path


def blank(match: re.Match) -> str:
    return "".join("\n" if c == "\n" else " " for c in match.group(0))


def is_translatable(text: str) -> bool:
    unescaped = html.unescape(text)
    letters = [c for c in unescaped if c.isalpha()]
    return len(letters) >= 3 and bool(HAS_LETTERS.search(unescaped))


def wrap_file(path: Path, dry_run: bool):
    src = path.read_text(encoding="utf-8")
    masked = mask_tag_gt(MASK_RE.sub(blank, src))
    edits = []
    manual = []
    skipped = []

    for m in TEXT_RE.finditer(masked):
        start, end = m.span(1)
        raw = src[start:end]
        masked_text = masked[start:end]
        stripped = raw.strip()
        if not stripped:
            continue
        if "`" in raw:
            continue
        # If the span overlaps anything we masked (script/style/pre/code or
        # template tags), only keep it when it genuinely contains template
        # tags; otherwise it is an artefact spanning a masked code block.
        if masked_text != raw and "{{" not in raw and "{%" not in raw:
            continue
        if "{{" in raw or "{%" in raw:
            if is_translatable(re.sub(r"\{[{%].*?[}%]\}", " ", raw, flags=re.S)):
                manual.append((masked.count("\n", 0, start) + 1, " ".join(stripped.split())[:90]))
            continue
        if '"' in raw or "'" in raw:
            if is_translatable(raw):
                skipped.append((masked.count("\n", 0, start) + 1, " ".join(stripped.split())[:90]))
            continue
        if not is_translatable(raw):
            continue
        normalized = " ".join(stripped.split())
        lead = raw[: len(raw) - len(raw.lstrip())]
        trail = raw[len(raw.rstrip()):]
        escaped = normalized.replace("\\", "\\\\").replace('"', '\\"')
        edits.append((start, end, f'{lead}{{% trans "{escaped}" %}}{trail}'))

    if not edits:
        return 0, manual, skipped

    if not dry_run:
        text = src
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        if "{% trans" in text and not I18N_LOAD_RE.search(text):
            extends = re.search(r"^\s*\{%\s*extends[^%]*%\}\s*$", text, re.M)
            if extends:
                text = text[: extends.end()] + "\n{% load i18n %}" + text[extends.end():]
            else:
                text = "{% load i18n %}\n" + text
        path.write_text(text, encoding="utf-8")

    return len(edits), manual, skipped


def main():
    dry_run = "--dry-run" in sys.argv
    show = "--show" in sys.argv
    total = manual_total = skipped_total = 0
    all_manual = []
    all_skipped = []
    for path in sorted(iter_templates()):
        n, manual, skipped = wrap_file(path, dry_run)
        rel = path.relative_to(BASE)
        if n or manual or skipped:
            print(f"{n:4d} wrapped  {len(manual):3d} manual  {len(skipped):3d} quoted   {rel}")
        total += n
        manual_total += len(manual)
        skipped_total += len(skipped)
        all_manual += [(str(rel), ln, txt) for ln, txt in manual]
        all_skipped += [(str(rel), ln, txt) for ln, txt in skipped]

    print(f"\nTotal wrapped: {total}   manual (vars): {manual_total}   skipped (quotes): {skipped_total}")
    if dry_run:
        print("(dry run — no files changed)")
    if show:
        print("\n--- MANUAL (template vars) ---")
        for rel, line, txt in all_manual:
            print(f"  {line:5d}  {rel}  |  {txt}")
        print("\n--- SKIPPED (contain quotes) ---")
        for rel, line, txt in all_skipped:
            print(f"  {line:5d}  {rel}  |  {txt}")


if __name__ == "__main__":
    main()
