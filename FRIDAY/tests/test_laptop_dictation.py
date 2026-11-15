"""TASK-IG-LAP-02 — voice dictation typing tests.

The text preparation and chunking are pure functions; the tool is
driven with a stubbed ``_dispatch`` so no laptop is needed (the owner's
laptop is not connected yet — same harness discipline as LAP-001).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.core.types import ToolResult  # noqa: E402
from friday.tools.builtin.laptop_dictation import (  # noqa: E402
    LaptopDictateTool,
    chunk_text,
    prepare_dictation_text,
)


def test_dictation_punctuation_tokens():
    assert prepare_dictation_text("hello comma world period") == "Hello, world."
    assert prepare_dictation_text("is it ready question mark") == "Is it ready?"
    assert prepare_dictation_text("wow exclamation mark") == "Wow!"
    assert prepare_dictation_text("note colon bring milk semicolon eggs") == (
        "Note: bring milk; eggs"
    )
    assert prepare_dictation_text("wait ellipsis ok") == "Wait... Ok"


def test_dictation_new_line_and_paragraph():
    assert prepare_dictation_text("first line new line second line") == (
        "First line\nSecond line"
    )
    assert prepare_dictation_text("para one new paragraph para two") == (
        "Para one\n\nPara two"
    )


def test_dictation_capitalises_sentence_starts():
    assert prepare_dictation_text("one period two period three") == "One. Two. Three"


def test_dictation_word_boundaries_protect_real_words():
    assert prepare_dictation_text("this happens periodically") == (
        "This happens periodically"
    )
    assert prepare_dictation_text("a comma shaped cloud") == "A, shaped cloud"


def test_verbatim_mode_is_untouched():
    raw = "  type this period exactly , as given  "
    assert prepare_dictation_text(raw, mode="verbatim") == raw


def test_chunking_is_lossless_and_bounded():
    text = ("word " * 400).strip()
    chunks = chunk_text(text, size=100)
    assert "".join(chunks) == text
    assert all(len(c) <= 100 for c in chunks)
    assert len(chunks) > 10


def test_chunking_prefers_newlines():
    text = "a" * 50 + "\n" + "b" * 50 + "\n" + "c" * 50
    chunks = chunk_text(text, size=60)
    assert "".join(chunks) == text
    assert chunks[0].endswith("\n")


def test_chunking_empty_and_short():
    assert chunk_text("") == []
    assert chunk_text("short") == ["short"]


class _Recorder:
    """Stands in for _LaptopTool._dispatch."""

    def __init__(self, fail_on_call: int | None = None) -> None:
        self.calls: list[str] = []
        self.fail_on_call = fail_on_call

    def __call__(self, args: dict[str, Any], laptop_id: Any = None, timeout: Any = None):
        self.calls.append(args["text"])
        if self.fail_on_call is not None and len(self.calls) == self.fail_on_call:
            return None, ToolResult(
                name="laptop_dictate", content="tunnel dropped", is_error=True
            )
        return {"ok": True, "laptop_id": "lap-1"}, None


def _tool_with(recorder: _Recorder) -> LaptopDictateTool:
    tool = LaptopDictateTool()
    tool._dispatch = recorder  # type: ignore[method-assign]
    return tool


def test_tool_types_prepared_text_in_chunks():
    recorder = _Recorder()
    tool = _tool_with(recorder)
    long_text = "hello world period " * 60  # > 600 chars once prepared
    result = tool.execute(text=long_text)
    assert not result.is_error
    joined = "".join(recorder.calls)
    assert joined == prepare_dictation_text(long_text)
    assert len(recorder.calls) > 1
    assert result.metadata["characters"] == len(joined)


def test_tool_reports_partial_progress_on_mid_failure():
    recorder = _Recorder(fail_on_call=2)
    tool = _tool_with(recorder)
    result = tool.execute(text="hello world period " * 60)
    assert result.is_error
    assert "after 1 of" in result.content
    assert len(recorder.calls) == 2  # stopped at the failure, did not plough on


def test_tool_rejects_empty_text():
    tool = _tool_with(_Recorder())
    assert tool.execute(text="   ").is_error
    assert tool.execute(text="").is_error


def test_tool_is_sensitive_class():
    tool = LaptopDictateTool()
    assert str(tool.safety_level).upper().endswith("SENSITIVE")
    assert tool.command == "type_text"
