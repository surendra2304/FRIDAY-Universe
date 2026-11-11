"""
test_accent_corpus.py — E10 corpus + scoring-sheet integrity (hermetic, fast).

Guards: every phrase has the fields the scorer needs, the sheet renders every
phrase, and the corpus stays a realistic size (an owner session is ~5 minutes,
so an overgrown corpus would silently never get run).
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "FRIDAY" / "scripts"))

from accent_scoring_sheet import CORPUS, render_sheet  # noqa: E402

REQUIRED_FIELDS = {"id", "category", "phrase", "pass_criteria"}
ALLOWED_CATEGORIES = {"retroflex", "indian_vocab", "telugu_mix", "numbers",
                      "domain", "speed"}


def _corpus() -> dict:
    return json.loads(CORPUS.read_text(encoding="utf-8"))


def test_every_phrase_has_required_fields():
    corpus = _corpus()
    assert corpus["phrases"], "corpus must not be empty"
    for p in corpus["phrases"]:
        missing = REQUIRED_FIELDS - set(p)
        assert not missing, f"{p.get('id', '?')} missing {missing}"


def test_categories_are_known():
    for p in _corpus()["phrases"]:
        assert p["category"] in ALLOWED_CATEGORIES, f"{p['id']}: {p['category']}"


def test_ids_unique_and_stable():
    ids = [p["id"] for p in _corpus()["phrases"]]
    assert len(ids) == len(set(ids)), "duplicate phrase ids"


def test_corpus_covers_the_target_mixes():
    cats = {p["category"] for p in _corpus()["phrases"]}
    assert {"telugu_mix", "numbers", "indian_vocab", "retroflex"} <= cats, (
        f"missing key accent categories: {cats}"
    )


def test_corpus_size_is_a_five_minute_session():
    n = len(_corpus()["phrases"])
    assert 10 <= n <= 25, f"{n} phrases — an owner session is ~5 minutes"


def test_numbers_category_mentions_trading_quantities():
    """Indian numbering (lakh/crore) is the highest-stakes accent case for a
    trading assistant — mishearing 'two lakh' as 'two' is a real risk."""
    number_phrases = [p for p in _corpus()["phrases"] if p["category"] == "numbers"]
    assert number_phrases, "numbers category must exist"
    joined = " ".join(p["phrase"] for p in number_phrases)
    assert any(w in joined.lower() for w in ("lakh", "crore", "fifty")), (
        "numbers category should exercise Indian numbering"
    )


def test_sheet_renders_every_phrase_with_pass_threshold():
    corpus = _corpus()
    sheet = render_sheet(corpus)
    for p in corpus["phrases"]:
        assert p["id"] in sheet, f"{p['id']} missing from sheet"
        assert p["phrase"] in sheet
    n = len(corpus["phrases"])
    assert f">= {int(0.9 * n + 0.999)}/{n}" in sheet, "PASS threshold must be printed"
    assert "KIT PASS" in sheet
