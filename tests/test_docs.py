from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
LANGS = ("en", "pt-BR")
LINK = re.compile(r"\]\((?!https?://|mailto:|#)([^)#\s]+)(?:#[^)]*)?\)")


def pages(lang: str) -> set[str]:
    base = DOCS / lang
    return {str(p.relative_to(base)).replace("\\", "/") for p in base.rglob("*.md")}


def test_both_languages_have_the_same_pages() -> None:
    assert pages("en") == pages("pt-BR")


@pytest.mark.parametrize("path", [*DOCS.rglob("*.md"), *ROOT.glob("*.md")], ids=lambda p: p.name)
def test_relative_links_resolve(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    broken = [
        target for target in LINK.findall(text) if not (path.parent / target).resolve().exists()
    ]
    assert not broken, f"{path.relative_to(ROOT)}: {broken}"


def test_removed_platforms_are_not_documented_as_current() -> None:
    allowed = {"index.md", "migration/from-celery.md", "adr/index.md"}
    offenders = []
    for lang in LANGS:
        for page in pages(lang) - allowed:
            text = (DOCS / lang / page).read_text(encoding="utf-8").lower()
            if "celery" in text or "fly.io" in text.replace("fly.io, cloud run", ""):
                offenders.append(f"{lang}/{page}")
    assert not offenders, offenders
