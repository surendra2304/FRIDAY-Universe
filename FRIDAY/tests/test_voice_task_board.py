"""TASK-FRD-049 — voice task-board tests (checkpoint 2).

Parser, persistence and open-item mapping are tested against the real
tool with a throwaway store file; no test touches the network or opens
a real browser (the opener is faked). Widget tests run only where
PyQt6 is installed; the corner-position helper is pure and tested here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.tools.builtin.task_board import (  # noqa: E402
    TaskBoardStore,
    TaskBoardTool,
    corner_position,
    parse_board_request,
    resolve_target,
)


def _tool(tmp_path, opener=None):
    return TaskBoardTool(
        store=TaskBoardStore(tmp_path / "task_board.json"), opener=opener
    )


class FakeOpener:
    def __init__(self):
        self.opened: list[str] = []

    def __call__(self, url: str) -> bool:
        self.opened.append(url)
        return True


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def test_parse_acceptance_example():
    board = parse_board_request("bottom left with YouTube, GitHub and Gmail")
    assert board["position"] == "bottom-left"
    assert [i["label"] for i in board["items"]] == ["YouTube", "GitHub", "Gmail"]
    assert [i["site"] for i in board["items"]] == ["youtube", "github", "gmail"]


def test_parse_top_right_variant():
    board = parse_board_request("top right with Netflix and Spotify")
    assert board["position"] == "top-right"
    assert [i["label"] for i in board["items"]] == ["Netflix", "Spotify"]


def test_parse_hyphenated_corner():
    board = parse_board_request("draw a board bottom-right with Wikipedia")
    assert board["position"] == "bottom-right"
    assert board["items"][0]["label"] == "Wikipedia"


def test_parse_missing_position_defaults_bottom_left():
    board = parse_board_request("with YouTube and GitHub")
    assert board["position"] == "bottom-left"
    assert len(board["items"]) == 2


def test_parse_one_item():
    board = parse_board_request("top left with Gmail")
    assert board["items"] == [{"label": "Gmail", "site": "gmail"}]


def test_parse_url_item_passes_through():
    board = parse_board_request("bottom left with https://example.com/news")
    assert board["items"][0]["site"] == "https://example.com/news"


def test_parse_empty_items_rejected():
    with pytest.raises(ValueError, match="at least one item"):
        parse_board_request("bottom left with")
    with pytest.raises(ValueError, match="at least one item"):
        parse_board_request("draw a board bottom left")


def test_parse_unknown_corner_rejected_not_remapped():
    with pytest.raises(ValueError, match="not a corner"):
        parse_board_request("middle left with YouTube")
    with pytest.raises(ValueError, match="not a corner"):
        parse_board_request("center with YouTube")


def test_parse_empty_request_rejected():
    with pytest.raises(ValueError, match="where to draw"):
        parse_board_request("")


# ---------------------------------------------------------------------------
# Persistence round-trip
# ---------------------------------------------------------------------------

def test_draw_then_reload_identical(tmp_path):
    tool = _tool(tmp_path)
    result = tool.execute(
        action="draw", request="bottom left with YouTube, GitHub and Gmail"
    )
    assert not result.is_error
    reloaded = TaskBoardStore(tmp_path / "task_board.json").load()
    assert reloaded["position"] == "bottom-left"
    assert [i["label"] for i in reloaded["items"]] == [
        "YouTube", "GitHub", "Gmail",
    ]
    assert reloaded["visible"] is True


def test_add_remove_round_trip(tmp_path):
    tool = _tool(tmp_path)
    tool.execute(action="draw", request="bottom left with YouTube")
    tool.execute(action="add", label="Reddit")
    assert [i["label"] for i in tool._store.load()["items"]] == [
        "YouTube", "Reddit",
    ]
    tool.execute(action="remove", label="youtube")
    assert [i["label"] for i in tool._store.load()["items"]] == ["Reddit"]


def test_remove_unknown_label_is_error_no_change(tmp_path):
    tool = _tool(tmp_path)
    tool.execute(action="draw", request="bottom left with YouTube")
    result = tool.execute(action="remove", label="Netflix")
    assert result.is_error
    assert [i["label"] for i in tool._store.load()["items"]] == ["YouTube"]


def test_clear_and_hide_show(tmp_path):
    tool = _tool(tmp_path)
    tool.execute(action="draw", request="bottom left with YouTube")
    assert tool.execute(action="hide").content.startswith("Task board hidden")
    assert tool._store.load()["visible"] is False
    assert tool.execute(action="show").content.startswith("Task board shown")
    tool.execute(action="clear")
    assert tool._store.load()["items"] == []


def test_corrupt_store_file_loads_empty_board(tmp_path):
    path = tmp_path / "task_board.json"
    path.write_text("{not json", encoding="utf-8")
    assert TaskBoardStore(path).load()["items"] == []


def test_on_change_callback_fires(tmp_path):
    seen: list[dict] = []
    tool = TaskBoardTool(
        store=TaskBoardStore(tmp_path / "task_board.json"),
        on_change=seen.append,
    )
    tool.execute(action="draw", request="bottom left with YouTube")
    assert len(seen) == 1
    assert seen[0]["position"] == "bottom-left"


# ---------------------------------------------------------------------------
# Open-item mapping
# ---------------------------------------------------------------------------

def test_open_known_label_opens_correct_url(tmp_path):
    opener = FakeOpener()
    tool = _tool(tmp_path, opener=opener)
    tool.execute(action="draw", request="bottom left with YouTube, GitHub")
    result = tool.execute(action="open", label="github")
    assert not result.is_error
    assert opener.opened == ["https://github.com"]


def test_open_unknown_label_opens_nothing(tmp_path):
    opener = FakeOpener()
    tool = _tool(tmp_path, opener=opener)
    tool.execute(action="draw", request="bottom left with YouTube")
    result = tool.execute(action="open", label="Netflix")
    assert result.is_error
    assert opener.opened == []


def test_open_with_no_board_is_error(tmp_path):
    opener = FakeOpener()
    tool = _tool(tmp_path, opener=opener)
    result = tool.execute(action="open", label="YouTube")
    assert result.is_error
    assert opener.opened == []


def test_resolve_target_unknown_bare_name_returns_none():
    assert resolve_target("some-made-up-thing") is None
    assert resolve_target("youtube") == "https://www.youtube.com"
    assert resolve_target("example.com") == "https://example.com"


def test_unknown_action_is_error(tmp_path):
    tool = _tool(tmp_path)
    assert tool.execute(action="explode").is_error


# ---------------------------------------------------------------------------
# Corner geometry (pure helper — no Qt needed)
# ---------------------------------------------------------------------------

def test_corner_position_all_corners():
    assert corner_position("top-left", 1920, 1080, 300, 200) == (16, 16)
    assert corner_position("top-right", 1920, 1080, 300, 200) == (1604, 16)
    assert corner_position("bottom-left", 1920, 1080, 300, 200) == (16, 864)
    assert corner_position("bottom-right", 1920, 1080, 300, 200) == (1604, 864)


# ---------------------------------------------------------------------------
# Widget (only where PyQt6 is installed)
# ---------------------------------------------------------------------------

def test_widget_shows_items_and_click_opens():
    pytest.importorskip("PyQt6")
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    from friday.desktop.task_board_widget import TaskBoardWidget

    app = QApplication.instance() or QApplication([])
    opened: list[tuple[str, str]] = []
    widget = TaskBoardWidget(
        {"position": "bottom-left",
         "items": [{"label": "YouTube", "site": "youtube"}], "visible": True},
        open_item=lambda label, site: opened.append((label, site)),
    )
    assert widget.isVisible()
    assert len(widget._item_buttons) == 1
    widget._item_buttons[0].click()
    assert opened == [("YouTube", "youtube")]
    widget.set_board({"position": "top-right", "items": [], "visible": True})
    assert not widget.isVisible()
    widget.deleteLater()
    app.quit()
