"""TASK-FRD-057 — book-page translation reading mode.

Source: friday package F-15 (item DaFKBDwJlLZ) — a study method for
Telugu readers: screenshot 10-20 book pages daily and have the AI
translate them into Telugu. FRIDAY's baseline has no book-translation
capability; this builds it as a real reading workflow, with Inference
as the translation route.

The flow, page by page:
1. The owner photographs a book page on his phone and sends it to
   FRIDAY on Telegram (@fridayuniverse_bot). The Telegram gateway
   downloads the photo and hands it here (see
   ``friday.proactive.telegram_gateway`` — photo updates).
2. ``ocr_page_image`` reads the page with local Tesseract OCR (the
   same pytesseract pattern as ``tools/builtin/screen_ocr.py``) — free,
   no cloud call. A photo that yields no readable text is reported
   honestly; nothing is invented.
3. ``translate_to_telugu`` sends the OCR text to the LLM provider
   stack (``create_llm_provider`` — the REL-044 escalating stack, so a
   full-page translation is served by Inference) with a
   translate-only prompt. The model returns Telugu only.
4. ``translate_page`` saves the page (Telugu + OCR source + metadata)
   under ``FRIDAY/.data/book_translation/<book>/`` and tracks progress
   in ``state.json`` (pages done, last page). Page numbers
   auto-increment per book, so the owner just keeps sending photos.

Hard rules, by design:
- NOTHING is ever sent or submitted anywhere. The translation is
  returned to the owner and saved locally; there is no apply/post path.
- An OCR or translation failure is returned as an error with the
  reason — never a fabricated translation.
- Spoken read-out is optional in the acceptance and is NOT wired here.
  A Telugu TTS path DOES exist on the server: POST /api/voice/speak
  synthesises English or Telugu via edge-tts; wiring a read-aloud for
  a saved page is a follow-up. The saved page file is what the voice
  lane reads when the owner asks FRIDAY to read it aloud.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Translation target for the reading mode (Telugu).
TARGET_LANG = "te"
TARGET_LANG_NAME = "Telugu"

#: OCR confidence floor for kept words (same as screen_ocr).
OCR_MIN_CONF = 40
#: Words on the same line when their tops differ by at most this (px).
OCR_LINE_TOLERANCE_PX = 6
#: Bound the translation prompt so a dense page cannot blow up the call.
MAX_TRANSLATE_CHARS = 12000


def _data_dir() -> str:
    """File-backed state root: FRIDAY/.data/book_translation/."""
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        base = os.path.abspath(os.path.join(cwd, ".data", "book_translation"))
    else:
        here = os.path.dirname(__file__)  # .../friday/workflows
        base = os.path.abspath(os.path.join(here, "..", "..", ".data", "book_translation"))
    os.makedirs(base, exist_ok=True)
    return base


def _slugify(book: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (book or "unspecified").strip().lower()).strip("-")
    return slug or "unspecified"


def inbox_path(file_id: str, *, data_dir: str | None = None) -> Path:
    """Where a downloaded Telegram photo is stored before translation."""
    return Path(data_dir or _data_dir()) / "inbox" / f"{file_id}.jpg"


def _book_dir(book: str, *, data_dir: str | None = None) -> Path:
    return Path(data_dir or _data_dir()) / _slugify(book)


def _state_path(book: str, *, data_dir: str | None = None) -> Path:
    return _book_dir(book, data_dir=data_dir) / "state.json"


def _load_state(book: str, *, data_dir: str | None = None) -> dict[str, Any]:
    try:
        with open(_state_path(book, data_dir=data_dir), "r", encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict):
            state.setdefault("pages_done", [])
            state.setdefault("last_page", 0)
            return state
    except Exception:
        pass
    return {"book": book, "pages_done": [], "last_page": 0}


def _save_state(book: str, state: dict[str, Any], *, data_dir: str | None = None) -> None:
    path = _state_path(book, data_dir=data_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def book_progress(book: str, *, data_dir: str | None = None) -> dict[str, Any]:
    """Pages translated so far for a book (honest empty when none)."""
    state = _load_state(book, data_dir=data_dir)
    pages = sorted({int(p) for p in state.get("pages_done", []) if str(p).isdigit()})
    return {"book": book, "pages_done": pages, "count": len(pages), "last_page": int(state.get("last_page") or 0)}


# ----------------------------------------------------------------------
# OCR — local Tesseract over a page photo
# ----------------------------------------------------------------------

def _default_ocr_runner(image) -> list[tuple[str, tuple[int, int, int, int]]]:
    """Run Tesseract; return [(text, bounding_box)] for confident words."""
    import pytesseract

    from friday.core.config import get_settings

    settings = get_settings()
    cmd = getattr(settings, "tesseract_cmd", None)
    if not cmd and os.name == "nt":
        cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
    results: list[tuple[str, tuple[int, int, int, int]]] = []
    n = len(data.get("text", []))
    for i in range(n):
        word = (data["text"][i] or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if word and conf > OCR_MIN_CONF:
            box = (
                data["left"][i],
                data["top"][i],
                data["left"][i] + data["width"][i],
                data["top"][i] + data["height"][i],
            )
            results.append((word, box))
    return results


def ocr_page_image(
    image_path: str,
    *,
    ocr_runner: Callable | None = None,
) -> dict[str, Any]:
    """OCR one book-page image file. Returns ok/text/word_count, or ok False."""
    try:
        from PIL import Image

        image = Image.open(image_path).convert("L")
    except FileNotFoundError:
        return {"ok": False, "error": f"Image file not found: {image_path}"}
    except Exception as exc:
        return {"ok": False, "error": f"Could not open image {image_path}: {exc}"}
    runner = ocr_runner or _default_ocr_runner
    try:
        words = runner(image)
    except ImportError as exc:
        return {
            "ok": False,
            "error": (
                f"Local OCR unavailable: {type(exc).__name__}. Install the Tesseract engine "
                "(https://github.com/UB-Mannheim/tesseract/wiki) and ensure it is on PATH."
            ),
        }
    except Exception as exc:
        return {"ok": False, "error": f"OCR failed on {image_path}: {exc}"}
    if not words:
        return {"ok": False, "error": "No readable text found in the image."}
    # Reconstruct lines by grouping words on the same top coordinate.
    lines: list[tuple[int, list[str]]] = []
    for word, (l, t, r, b) in words:
        if lines and abs(lines[-1][0] - t) <= OCR_LINE_TOLERANCE_PX:
            lines[-1][1].append(word)
        else:
            lines.append((t, [word]))
    text = "\n".join(" ".join(ws) for _, ws in lines).strip()
    if not text:
        return {"ok": False, "error": "No readable text found in the image."}
    return {
        "ok": True,
        "text": text,
        "word_count": len(text.split()),
    }


# ----------------------------------------------------------------------
# Translation — through the Inference route (REL-044 escalating stack)
# ----------------------------------------------------------------------

def translate_to_telugu(text: str, *, llm: Any = None) -> dict[str, Any]:
    """Translate English text to Telugu via the LLM provider stack.

    ``llm`` is injectable for tests; otherwise the provider is built
    from settings (the escalating stack serves a full-page translation
    through Inference).
    """
    source = (text or "").strip()
    if not source:
        return {"ok": False, "error": "Nothing to translate: the OCR text was empty."}
    if len(source) > MAX_TRANSLATE_CHARS:
        source = source[:MAX_TRANSLATE_CHARS]
    try:
        if llm is None:
            from friday.core.config import get_settings
            from friday.core.types import Message, Role
            from friday.llm.factory import create_llm_provider

            provider = create_llm_provider(get_settings())
            messages = [
                Message(
                    role=Role.SYSTEM,
                    content=(
                        "You are a precise English-to-Telugu translator. Translate the text "
                        "faithfully into Telugu, preserving paragraph breaks and line "
                        "structure. Do not add commentary, explanations, or English — "
                        "output only the Telugu translation."
                    ),
                ),
                Message(role=Role.USER, content=source),
            ]
            resp = provider.generate(messages=messages)
            telugu = (resp.content or "").strip()
            provider_name = getattr(provider, "provider_name", "llm")
        else:
            from friday.core.types import Message, Role

            messages = [
                Message(
                    role=Role.SYSTEM,
                    content=(
                        "You are a precise English-to-Telugu translator. Translate the text "
                        "faithfully into Telugu, preserving paragraph breaks and line "
                        "structure. Do not add commentary, explanations, or English — "
                        "output only the Telugu translation."
                    ),
                ),
                Message(role=Role.USER, content=source),
            ]
            resp = llm.generate(messages=messages)
            telugu = (resp.content or "").strip()
            provider_name = getattr(llm, "provider_name", "llm")
    except Exception as exc:
        logger.warning("[BOOK-TRANSLATION] translation failed: %s", exc)
        return {"ok": False, "error": f"Translation failed: {exc}"}
    if not telugu:
        return {"ok": False, "error": "Translation returned no Telugu text."}
    return {"ok": True, "telugu": telugu, "provider": provider_name}


# ----------------------------------------------------------------------
# Page orchestration — OCR, translate, save, track
# ----------------------------------------------------------------------

def translate_page(
    image_path: str,
    *,
    book: str = "unspecified",
    page_no: int | None = None,
    llm: Any = None,
    ocr_runner: Callable | None = None,
    data_dir: str | None = None,
) -> dict[str, Any]:
    """Translate one photographed book page end to end.

    OCR first, then translate through Inference, then save the page
    (Telugu + OCR source + metadata) and advance the book's progress.
    A failure at either step is returned honestly with the reason —
    no translation is ever fabricated.
    """
    state = _load_state(book, data_dir=data_dir)
    page = int(page_no) if page_no else int(state.get("last_page") or 0) + 1
    ocr = ocr_page_image(image_path, ocr_runner=ocr_runner)
    if not ocr.get("ok"):
        return {"ok": False, "book": book, "page": page, "error": ocr.get("error", "OCR failed")}
    translation = translate_to_telugu(ocr["text"], llm=llm)
    if not translation.get("ok"):
        return {
            "ok": False,
            "book": book,
            "page": page,
            "error": translation.get("error", "Translation failed"),
            "ocr_text": ocr["text"],
            "ocr_word_count": ocr.get("word_count", 0),
        }
    telugu = translation["telugu"]
    book_dir = _book_dir(book, data_dir=data_dir)
    book_dir.mkdir(parents=True, exist_ok=True)
    saved = book_dir / f"page-{page}.md"
    saved.write_text(
        (
            f"# {book} — page {page}\n\n"
            f"Translated {datetime.now(timezone.utc).isoformat()} via "
            f"{translation.get('provider', 'llm')} — OCR {ocr.get('word_count', 0)} words.\n\n"
            f"## Telugu\n\n{telugu}\n\n"
            f"## Source (OCR)\n\n{ocr['text']}\n"
        ),
        encoding="utf-8",
    )
    pages = sorted({int(p) for p in state.get("pages_done", []) if str(p).isdigit()} | {page})
    state["pages_done"] = pages
    state["last_page"] = max(pages)
    _save_state(book, state, data_dir=data_dir)
    return {
        "ok": True,
        "book": book,
        "page": page,
        "telugu": telugu,
        "ocr_text": ocr["text"],
        "ocr_word_count": ocr.get("word_count", 0),
        "provider": translation.get("provider", "llm"),
        "saved_path": str(saved),
    }
