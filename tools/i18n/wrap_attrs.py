"""Wrap simple (template-tag-free) attributes with {% trans %}.

Covers the user-facing attributes ``aria-label``, ``placeholder``, ``title``
and ``alt`` in customer-facing templates. Attributes that already contain
template tags (``{% trans %}`` etc.) or variables are left untouched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

ATTR_RE = re.compile(
    r'(\b(?:aria-label|placeholder|title|alt)\s*=\s*")'  # attribute + opening quote
    r'([^"{}\n<>]*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][^"{}\n<>]*)'  # value with a letter
    r'(")'
)

EXCLUDE = {"styleguide.html"}


def iter_templates():
    for path in sorted((BASE / "templates").rglob("*.html")):
        rel = path.relative_to(BASE / "templates")
        if path.name in EXCLUDE:
            continue
        if rel.parts and rel.parts[0] == "admin":
            continue
        yield path


def process(path: Path, dry_run: bool):
    src = path.read_text(encoding="utf-8")
    count = 0

    def repl(match: re.Match) -> str:
        nonlocal count
        value = match.group(2)
        normalized = " ".join(value.split())
        if not normalized:
            return match.group(0)
        count += 1
        return f'{match.group(1)}{{% trans "{normalized}" %}}{match.group(3)}'

    new = ATTR_RE.sub(repl, src)
    if count and not dry_run:
        path.write_text(new, encoding="utf-8")
    return count


def main():
    dry_run = "--dry-run" in sys.argv
    total = 0
    for path in iter_templates():
        n = process(path, dry_run)
        if n:
            print(f"{n:3d}  {path.relative_to(BASE)}")
        total += n
    print(f"\nAttributes wrapped: {total}" + (" (dry run)" if dry_run else ""))


if __name__ == "__main__":
    main()
