"""TASK-FRD-057 — book-page translation reading mode.

Hermetic tests: a fake OCR runner stands in for Tesseract and a fake
LLM stands in for the Inference route, so no engine, no network and
no provider key is needed. The Telegram photo branch is tested with a
capturing _api and a stubbed download + workflow.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.proactive import telegram_gateway as tg  # noqa: E402
from friday.tools.builtin.book_translation_tools import BookPageTranslateTool  # noqa: E402
from friday.workflows import book_translation as bt  # noqa: E402

TELUGU = "ఇది ఒక పరీక్షా అనువాదం."


def _make_image(tmp_path: Path, name: str = "page.png") -> str:
    from PIL import Image

    path = tmp_path / name
    Image.new("RGB", (200, 100), color="white").save(path)
    return str(path)


def _fake_ocr_words(image):
    # Two lines: top 10 ("The quick brown fox"), top 30 ("jumps over").
    return [
        ("The", (0, 10, 30, 22)),
        ("quick", (35, 10, 70, 22)),
        ("brown", (75, 10, 115, 22)),
        ("fox", (120, 10, 145, 22)),
        ("jumps", (0, 30, 45, 42)),
        ("over", (50, 30, 85, 42)),
    ]


class _FakeLLM:
    provider_name = "fake-inference"

    def __init__(self):
        self.calls: list = []
        self.fail = False

    def generate(self, messages=None):
        self.calls.append(messages)
        if self.fail:
            raise RuntimeError("inference down")
        return SimpleNamespace(content=TELUGU)


# ----------------------------------------------------------------------
# OCR
# ----------------------------------------------------------------------

def test_ocr_reconstructs_lines(tmp_path):
    result = bt.ocr_page_image(_make_image(tmp_path), ocr_runner=_fake_ocr_words)
    assert result["ok"] is True
    assert result["text"] == "The quick brown fox\njumps over"
    assert result["word_count"] == 6


def test_ocr_empty_is_honest(tmp_path):
    result = bt.ocr_page_image(_make_image(tmp_path), ocr_runner=lambda image: [])
    assert result["ok"] is False
    assert "No readable text" in result["error"]


def test_ocr_missing_file_is_honest():
    result = bt.ocr_page_image("/no/such/page.png", ocr_runner=_fake_ocr_words)
    assert result["ok"] is False
    assert "not found" in result["error"]


# ----------------------------------------------------------------------
# Translation
# ----------------------------------------------------------------------

def test_translate_to_telugu_prompts_and_returns():
    llm = _FakeLLM()
    result = bt.translate_to_telugu("The quick brown fox.", llm=llm)
    assert result["ok"] is True
    assert result["telugu"] == TELUGU
    assert result["provider"] == "fake-inference"
    messages = llm.calls[0]
    assert "Telugu" in messages[0].content
    assert "The quick brown fox." in messages[1].content


def test_translate_to_telugu_empty_is_honest():
    assert bt.translate_to_telugu("   ", llm=_FakeLLM())["ok"] is False


def test_translate_to_telugu_failure_is_honest():
    llm = _FakeLLM()
    llm.fail = True
    result = bt.translate_to_telugu("Hello.", llm=llm)
    assert result["ok"] is False
    assert "Translation failed" in result["error"]


# ----------------------------------------------------------------------
# Page orchestration + progress
# ----------------------------------------------------------------------

def test_translate_page_saves_and_tracks(tmp_path):
    data_dir = str(tmp_path / "book_translation")
    llm = _FakeLLM()
    first = bt.translate_page(
        _make_image(tmp_path), book="My Book", llm=llm, ocr_runner=_fake_ocr_words, data_dir=data_dir
    )
    assert first["ok"] is True
    assert first["page"] == 1
    assert first["telugu"] == TELUGU
    saved = Path(first["saved_path"])
    assert saved.exists()
    assert TELUGU in saved.read_text(encoding="utf-8")
    assert "The quick brown fox" in saved.read_text(encoding="utf-8")
    state = json.loads((tmp_path / "book_translation" / "my-book" / "state.json").read_text())
    assert state["pages_done"] == [1]
    assert state["last_page"] == 1
    second = bt.translate_page(
        _make_image(tmp_path, "page2.png"), book="My Book", llm=llm,
        ocr_runner=_fake_ocr_words, data_dir=data_dir,
    )
    assert second["page"] == 2
    assert bt.book_progress("My Book", data_dir=data_dir)["count"] == 2


def test_translate_page_ocr_failure_calls_no_translation(tmp_path):
    llm = _FakeLLM()
    result = bt.translate_page(
        _make_image(tmp_path), book="My Book", llm=llm,
        ocr_runner=lambda image: [], data_dir=str(tmp_path / "bt"),
    )
    assert result["ok"] is False
    assert llm.calls == []


def test_translate_page_translation_failure_is_honest(tmp_path):
    llm = _FakeLLM()
    llm.fail = True
    result = bt.translate_page(
        _make_image(tmp_path), book="My Book", llm=llm,
        ocr_runner=_fake_ocr_words, data_dir=str(tmp_path / "bt"),
    )
    assert result["ok"] is False
    assert "Translation failed" in result["error"]
    assert not list((tmp_path / "bt").rglob("page-*.md"))


def test_book_progress_empty(tmp_path):
    progress = bt.book_progress("No Such Book", data_dir=str(tmp_path / "bt"))
    assert progress["count"] == 0
    assert progress["pages_done"] == []


# ----------------------------------------------------------------------
# Tool
# ----------------------------------------------------------------------

def test_tool_returns_telugu_and_errors_honestly(tmp_path, monkeypatch):
    monkeypatch.setattr(
        bt, "translate_page",
        lambda *a, **k: {"ok": True, "book": "My Book", "page": 1, "telugu": TELUGU, "provider": "fake", "saved_path": "/x/page-1.md"},
    )
    tool = BookPageTranslateTool()
    result = tool.execute(image_path="/x/page.png", book="My Book")
    assert result.is_error is False
    assert TELUGU in result.content
    assert tool.execute(image_path="").is_error is True


# ----------------------------------------------------------------------
# Telegram photo branch
# ----------------------------------------------------------------------

def _gateway(monkeypatch: pytest.MonkeyPatch) -> tg.TelegramGateway:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:test-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "6341781431")
    return tg.TelegramGateway()


class _CapturingApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, method: str, params: dict) -> dict:
        self.calls.append((method, params))
        if method == "getFile":
            return {"ok": True, "result": {"file_path": "photos/file_1.jpg"}}
        return {"ok": True, "result": {"message_id": 1}}


def _photo_update(caption: str = "My Book", sender: str = "6341781431") -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 7,
            "from": {"id": int(sender), "first_name": "Surendra"},
            "chat": {"id": 6341781431},
            "caption": caption,
            "photo": [
                {"file_id": "small", "width": 90, "height": 90},
                {"file_id": "big-file-id", "width": 1280, "height": 960},
            ],
        },
    }


def test_gateway_photo_translates_and_replies(tmp_path, monkeypatch):
    g = _gateway(monkeypatch)
    api = _CapturingApi()
    monkeypatch.setattr(g, "_api", api)
    monkeypatch.setattr(g, "_download_telegram_file", lambda file_path: b"fake-jpg-bytes")
    monkeypatch.setattr(bt, "inbox_path", lambda file_id, **k: tmp_path / "inbox.jpg")
    seen: dict = {}

    def fake_translate(image_path, *, book, **kwargs):
        seen["book"] = book
        seen["image_path"] = image_path
        return {"ok": True, "book": book, "page": 1, "telugu": TELUGU}

    monkeypatch.setattr(bt, "translate_page", fake_translate)
    g._handle_update(_photo_update())
    assert seen["book"] == "My Book"
    assert ("getFile", {"file_id": "big-file-id"}) in api.calls
    sent = [p["text"] for m, p in api.calls if m == "sendMessage"]
    assert sent and TELUGU in sent[0]
    assert "Page 1" in sent[0]


def test_gateway_photo_from_non_owner_is_refused(tmp_path, monkeypatch):
    g = _gateway(monkeypatch)
    api = _CapturingApi()
    monkeypatch.setattr(g, "_api", api)
    called = []
    monkeypatch.setattr(bt, "translate_page", lambda *a, **k: called.append(True))
    g._handle_update(_photo_update(sender="999"))
    assert called == []
    sent = [p["text"] for m, p in api.calls if m == "sendMessage"]
    assert sent and "only to him" in sent[0]


def test_gateway_photo_translation_failure_is_honest(tmp_path, monkeypatch):
    g = _gateway(monkeypatch)
    api = _CapturingApi()
    monkeypatch.setattr(g, "_api", api)
    monkeypatch.setattr(g, "_download_telegram_file", lambda file_path: b"fake-jpg-bytes")
    monkeypatch.setattr(bt, "inbox_path", lambda file_id, **k: tmp_path / "inbox.jpg")
    monkeypatch.setattr(
        bt, "translate_page",
        lambda *a, **k: {"ok": False, "book": "My Book", "page": 1, "error": "No readable text found in the image."},
    )
    g._handle_update(_photo_update())
    sent = [p["text"] for m, p in api.calls if m == "sendMessage"]
    assert sent and "Could not translate" in sent[0]
    assert "No readable text" in sent[0]
