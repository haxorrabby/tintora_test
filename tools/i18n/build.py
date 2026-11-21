"""Build the English gettext catalog for Tintora Madrid without GNU gettext.

Django's ``makemessages`` needs the ``xgettext`` binary, which is not always
available (e.g. stock Windows). This tool extracts every translatable string
directly from the compiled Django templates (so ``{% blocktrans %}`` msgids
match *exactly* what ``gettext`` receives at render time) plus Python source,
pairs them with the English strings in ``translations_en.py`` and writes:

    locale/en/LC_MESSAGES/django.po
    locale/en/LC_MESSAGES/django.mo

Usage:
    python tools/i18n/build.py            # build .po + .mo and report gaps
    python tools/i18n/build.py --dump     # print exact msgids (for authoring)
"""

from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")

import django  # noqa: E402

django.setup()

import polib  # noqa: E402
from django.template import Context, engines  # noqa: E402
from django.template.base import NodeList  # noqa: E402
from django.templatetags.i18n import BlockTranslateNode, TranslateNode  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from translations_en import BLOCKTRANSLATIONS, PLURALS, TRANSLATIONS  # noqa: E402

# Optional companion module with strings added after the first pass (kept apart
# so the hand-curated translations_en.py stays readable).
try:  # pragma: no cover - optional
    from translations_missing import EXTRA_PLURALS, EXTRA_TRANSLATIONS  # noqa: E402

    TRANSLATIONS = {**TRANSLATIONS, **EXTRA_TRANSLATIONS}
    PLURALS = {**PLURALS, **EXTRA_PLURALS}
except Exception:  # pragma: no cover
    pass

TEMPLATE_DIRS = [BASE_DIR / "templates", BASE_DIR / "apps"]
PY_DIRS = [BASE_DIR / "apps", BASE_DIR / "config"]


def iter_templates():
    for root in TEMPLATE_DIRS:
        for path in root.rglob("*.html"):
            if "staticfiles" in path.parts or ".venv" in path.parts:
                continue
            yield path


def _iter_nodes(nodelist):
    """Yield every node in a compiled nodelist, recursing into child nodelists."""
    for node in nodelist:
        yield node
        for value in vars(node).values():
            if isinstance(value, NodeList):
                yield from _iter_nodes(value)
            elif isinstance(value, (list, tuple)):
                for item in value:
                    if isinstance(item, NodeList):
                        yield from _iter_nodes(item)
                    elif isinstance(item, (list, tuple)):
                        for sub in item:
                            if isinstance(sub, NodeList):
                                yield from _iter_nodes(sub)


def _walk_nodelist(nodelist):
    for node in _iter_nodes(nodelist):
        if isinstance(node, BlockTranslateNode):
            yield node


def _iter_compiled_templates():
    engine = engines["django"]
    for path in iter_templates():
        try:
            source = path.read_text(encoding="utf-8")
        except Exception:
            continue
        try:
            template = engine.from_string(source)
        except Exception as exc:  # pragma: no cover - safety net
            print(f"  ! could not compile {path}: {exc}")
            continue
        underlying = getattr(template, "template", template)
        nodelist = getattr(underlying, "nodelist", None)
        if nodelist is not None:
            yield path, nodelist


def collect_blocktranslates():
    """Return a dict of msgid -> (msgid_plural_or_None, origin) for blocktrans."""
    found = {}
    for path, nodelist in _iter_compiled_templates():
        for node in _walk_nodelist(nodelist):
            singular, _ = node.render_token_list(node.singular)
            if node.plural:
                plural, _ = node.render_token_list(node.plural)
            else:
                plural = None
            found[singular] = (plural, str(path.relative_to(BASE_DIR)))
    return found


def collect_translate_strings():
    """Return the set of msgids used by ``{% trans %}`` / ``{% translate %}``."""
    strings = set()
    for _path, nodelist in _iter_compiled_templates():
        for node in _iter_nodes(nodelist):
            if not isinstance(node, TranslateNode):
                continue
            try:
                value = node.filter_expression.resolve(Context())
            except Exception:
                continue
            if isinstance(value, str) and value:
                strings.add(value)
    return strings


def collect_python_strings():
    """Return set of msgids passed to gettext/_()/gettext_lazy()."""
    funcs = {"_", "gettext", "gettext_lazy", "gettext_noop", "ngettext", "pgettext"}
    strings = set()
    for root in PY_DIRS:
        for path in root.rglob("*.py"):
            if ".venv" in path.parts or "migrations" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not node.args:
                    continue
                func = node.func
                name = getattr(func, "id", None) or getattr(func, "attr", None)
                if name not in funcs:
                    continue
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    strings.add(first.value)
    return strings


def build(dump_only: bool = False):
    blocktrans = collect_blocktranslates()
    py_strings = collect_python_strings()
    translate_strings = collect_translate_strings()

    if dump_only:
        print(f"{len(blocktrans)} blocktrans msgids:\n")
        for msgid, (plural, origin) in sorted(blocktrans.items()):
            print(f"  msgid    = {msgid!r}   # {origin}")
            if plural:
                print(f"  plural   = {plural!r}")
        return

    catalog = polib.POFile()
    catalog.metadata = {
        "Project-Id-Version": "Tintora Madrid",
        "Report-Msgid-Bugs-To": "hola@tintora.es",
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=UTF-8",
        "Content-Transfer-Encoding": "8bit",
        "Language": "en",
        "Plural-Forms": "nplurals=2; plural=(n != 1);",
    }

    missing = []

    # 1) Simple / Python / {% trans %} msgids.
    simple_ids = set(py_strings) | set(translate_strings)
    for msgid in TRANSLATIONS:
        simple_ids.add(msgid)
    for msgid in sorted(simple_ids):
        plural = None
        for b_msgid, (b_plural, _origin) in blocktrans.items():
            if b_msgid == msgid:
                plural = b_plural
                break
        if plural:
            en_sing, en_plural = PLURALS.get(msgid, (TRANSLATIONS.get(msgid, ""), ""))
            entry = polib.POEntry(
                msgid=msgid,
                msgid_plural=plural,
                msgstr_plural={0: en_sing, 1: en_plural},
            )
            if not en_sing or not en_plural:
                missing.append(msgid)
            catalog.append(entry)
        else:
            msgstr = TRANSLATIONS.get(msgid)
            if not msgstr:
                missing.append(msgid)
                msgstr = ""
            catalog.append(polib.POEntry(msgid=msgid, msgstr=msgstr))

    # 2) blocktrans msgids (exact runtime form).
    for msgid, (plural, _origin) in sorted(blocktrans.items()):
        if plural:
            en = PLURALS.get(msgid)
            if en is None:
                missing.append(msgid)
                en = (BLOCKTRANSLATIONS.get(msgid, ("", ""))[0], BLOCKTRANSLATIONS.get(msgid, ("", ""))[1])
            catalog.append(
                polib.POEntry(msgid=msgid, msgid_plural=plural, msgstr_plural={0: en[0], 1: en[1]})
            )
        else:
            en = TRANSLATIONS.get(msgid) or BLOCKTRANSLATIONS.get(msgid, "")
            if not en:
                missing.append(msgid)
                en = ""
            catalog.append(polib.POEntry(msgid=msgid, msgstr=en))

    # Persist.
    out_dir = BASE_DIR / "locale" / "en" / "LC_MESSAGES"
    out_dir.mkdir(parents=True, exist_ok=True)
    po_path = out_dir / "django.po"
    catalog.save(str(po_path))
    catalog.save_as_mofile(str(out_dir / "django.mo"))

    translated = len([e for e in catalog if e.msgstr or e.msgstr_plural])
    print(f"Entries: {len(catalog)} | translated: {translated} | missing: {len(missing)}")
    print(f"Wrote {po_path.relative_to(BASE_DIR)} and django.mo")
    if missing:
        print("\nMISSING TRANSLATIONS:")
        for item in missing:
            print(f"  - {item!r}")


if __name__ == "__main__":
    build(dump_only="--dump" in sys.argv)
