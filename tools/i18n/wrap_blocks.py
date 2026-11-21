"""Wrap hardcoded text inside ``{% block title %}`` / meta blocks with trans.

These contents are not HTML text nodes (they sit between two template tags), so
``wrap_templates.py`` cannot see them. Only simple contents (no ``{{ }}`` /
``{% %}`` inside) are wrapped automatically; the rest are reported.
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
TEMPLATES = BASE / "templates"
APPS = BASE / "apps"

BLOCK_RE = re.compile(
    r"(\{%\s*block\s+(?:title|meta_[a-z_]+|og_[a-z_]+|twitter_[a-z_]+)\s*%\})"
    r"(.*?)"
    r"(\{%\s*endblock\b[^%]*%\})",
    re.S,
)
TAG_RE = re.compile(r"\{[{%].*?[}%]\}", re.S)


def iter_templates():
    for root in (TEMPLATES, APPS):
        for path in root.rglob("*.html"):
            if any(p in {".venv", "staticfiles", "node_modules"} for p in path.parts):
                continue
            if path.name == "styleguide.html":
                continue
            yield path


def is_translatable(text: str) -> bool:
    unescaped = html.unescape(text)
    return len([c for c in unescaped if c.isalpha()]) >= 3


def process(path: Path, dry_run: bool):
    src = path.read_text(encoding="utf-8")
    edits = []
    manual = []
    for m in BLOCK_RE.finditer(src):
        content = m.group(2)
        stripped = content.strip()
        if not stripped:
            continue
        if "{{" in content or "{%" in content:
            plain = TAG_RE.sub(" ", content)
            if is_translatable(plain):
                manual.append(" ".join(stripped.split())[:80])
            continue
        if not is_translatable(content):
            continue
        normalized = " ".join(stripped.split())
        quote = '"'
        if '"' in normalized and "'" not in normalized:
            quote = "'"
        elif '"' in normalized and "'" in normalized:
            continue
        lead = content[: len(content) - len(content.lstrip())]
        trail = content[len(content.rstrip()):]
        replacement = f"{m.group(1)}{lead}{{% trans {quote}{normalized}{quote} %}}{trail}{m.group(3)}"
        edits.append((m.start(), m.end(), replacement))

    if edits and not dry_run:
        text = src
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        path.write_text(text, encoding="utf-8")
    return len(edits), manual


def main():
    dry_run = "--dry-run" in sys.argv
    total = manual_total = 0
    for path in sorted(iter_templates()):
        n, manual = process(path, dry_run)
        if n or manual:
            print(f"{n:3d} wrapped  {len(manual):2d} manual  {path.relative_to(BASE)}")
            for text in manual:
                print(f"        manual: {text}")
        total += n
        manual_total += len(manual)
    print(f"\nTotal block contents wrapped: {total}   manual: {manual_total}")
    if dry_run:
        print("(dry run)")


if __name__ == "__main__":
    main()
