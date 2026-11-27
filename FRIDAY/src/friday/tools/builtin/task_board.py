"""Task Board Tool — TASK-FRD-049 (checkpoint 2).

A spoken request draws a persistent task board in a screen corner
(position and items named by voice, e.g. "bottom left with YouTube,
GitHub and Gmail") and FRIDAY opens sites by voice from it.

The tool owns the board state (a JSON file under the FRIDAY data dir,
per checkpoint 1 §2 — local desktop UI state only, not agent data) and
the voice parsing; ``TaskBoardWidget`` (``friday.desktop``) renders it.
Opening a site goes through the same resolution as ``open_website``
and never guesses: an unknown label is reported, never opened.
"""

from __future__ import annotations

import json
import os
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool
from friday.tools.builtin.open_website import POPULAR_SITES

logger = get_logger("tools.task_board")

CORNERS: tuple[str, ...] = ("top-left", "top-right", "bottom-left", "bottom-right")
_DEFAULT_CORNER = "bottom-left"

# Words that look like a corner instruction but name no supported corner.
# These are rejected with a clear message, never silently remapped.
_UNKNOWN_CORNER_WORDS = ("middle", "center", "centre", "upper", "lower", "mid-")

_CORNER_PATTERNS: dict[str, re.Pattern[str]] = {
    corner: re.compile(
        r"\b" + corner.replace("-", r"[ -]") + r"\b", re.IGNORECASE
    )
    for corner in CORNERS
}


def default_store_path() -> Path:
    """Where the persisted board lives (``FRIDAY_DATA_DIR`` or ``data/``)."""
    return Path(os.getenv("FRIDAY_DATA_DIR", "data")) / "task_board.json"


def empty_board() -> dict[str, Any]:
    return {"position": _DEFAULT_CORNER, "items": [], "visible": True,
            "updated_at": None}


def parse_corner(text: str) -> str | None:
    """Return the named corner in *text*, or None when none is named."""
    for corner, pattern in _CORNER_PATTERNS.items():
        if pattern.search(text):
            return corner
    return None


def _split_items(items_text: str) -> list[str]:
    parts = re.split(r"\s*,\s*|\s+and\s+", items_text.strip(), flags=re.IGNORECASE)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def parse_board_request(request: str) -> dict[str, Any]:
    """Parse one spoken board request into position + items.

    Raises ``ValueError`` with a speakable message when the request names
    no items, or names a corner FRIDAY does not support.
    """
    text = (request or "").strip()
    if not text:
        raise ValueError(
            "Tell me where to draw the board and what to put on it, "
            "for example: 'bottom left with YouTube, GitHub and Gmail'."
        )

    # The position clause comes before "with"; only look for unknown-corner
    # words there, so an item name can never trip the check.
    head = re.split(r"\bwith\b", text, maxsplit=1, flags=re.IGNORECASE)[0]
    if parse_corner(head) is None and any(
        w in head.lower() for w in _UNKNOWN_CORNER_WORDS
    ):
        raise ValueError(
            "I can only draw the board in a screen corner — top left, "
            "top right, bottom left or bottom right. "
            f"'{head.strip()}' is not a corner I know."
        )

    position = parse_corner(text) or _DEFAULT_CORNER

    match = re.search(r"\bwith\b\s*(.+)$", text, flags=re.IGNORECASE | re.DOTALL)
    if match is None:
        raise ValueError(
            "I need at least one item for the board — "
            "for example: 'bottom left with YouTube, GitHub and Gmail'."
        )
    raw_items = _split_items(match.group(1))
    if not raw_items:
        raise ValueError(
            "I need at least one item for the board — "
            "for example: 'bottom left with YouTube, GitHub and Gmail'."
        )

    items = [{"label": raw, "site": _resolve_site(raw)} for raw in raw_items]
    return {"position": position, "items": items, "visible": True,
            "updated_at": None}


def _resolve_site(raw: str) -> str:
    """Resolve one spoken item to a site name or URL (no browser opened)."""
    name = raw.strip().lower()
    if name in POPULAR_SITES:
        return name
    if name.startswith(("http://", "https://")):
        return raw.strip()
    if "." in name and " " not in name:
        return name
    return name


def resolve_target(site: str) -> str | None:
    """Resolve a stored board item's site to a URL, or None if unusable."""
    raw = (site or "").strip()
    if not raw:
        return None
    key = raw.lower()
    if key in POPULAR_SITES:
        return POPULAR_SITES[key]
    if key.startswith(("http://", "https://")):
        return raw
    if "." in key and " " not in key:
        return f"https://{key}"
    # A bare name FRIDAY cannot resolve to a site: do not guess a URL.
    return None


class TaskBoardStore:
    """JSON persistence for the board (one file, rewritten on mutation)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(path) if path is not None else default_store_path()

    def load(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError) as exc:
            logger.warning(f"Task board state unreadable ({self.path}): {exc}")
            return empty_board()
        if not isinstance(data, dict) or not isinstance(data.get("items"), list):
            return empty_board()
        board = empty_board()
        board.update({k: v for k, v in data.items() if k in board})
        if board["position"] not in CORNERS:
            board["position"] = _DEFAULT_CORNER
        return board

    def save(self, board: dict[str, Any]) -> dict[str, Any]:
        board = dict(board)
        board["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(board, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        return board


def corner_position(
    corner: str,
    screen_width: int,
    screen_height: int,
    panel_width: int,
    panel_height: int,
    margin: int = 16,
) -> tuple[int, int]:
    """Top-left (x, y) for *corner* — pure helper, unit-tested without Qt."""
    top = corner.startswith("top")
    left = corner.endswith("left")
    x = margin if left else max(margin, screen_width - panel_width - margin)
    y = margin if top else max(margin, screen_height - panel_height - margin)
    return (x, y)


def _describe(board: dict[str, Any]) -> str:
    labels = ", ".join(item["label"] for item in board["items"])
    return (
        f"Task board at the {board['position'].replace('-', ' ')}"
        + (f" with {len(board['items'])} item(s): {labels}" if labels else " (empty)")
        + ("" if board.get("visible", True) else " (hidden)")
    )


class TaskBoardTool(BaseTool):
    """Draw, change and open from a persistent on-screen task board."""

    name = "task_board"
    description = (
        "Draw a persistent task board in a screen corner from a spoken request "
        "(e.g. 'bottom left with YouTube, GitHub and Gmail'), add or remove "
        "items, hide or show it, and open a site from it by voice "
        "(e.g. 'open YouTube from my board'). Opening a site goes through "
        "the already-safe open_website path; an unknown board label is "
        "reported, never guessed."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["draw", "add", "remove", "clear", "hide", "show", "open"],
                "description": "Operation: 'draw' (replace the board from a spoken request), 'add'/'remove' (one item by label), 'clear', 'hide'/'show', 'open' (open one board item by label).",
            },
            "request": {
                "type": "string",
                "description": "Spoken board request for 'draw' (e.g. 'bottom left with YouTube, GitHub and Gmail').",
            },
            "label": {
                "type": "string",
                "description": "Board item label for 'add', 'remove' and 'open'.",
            },
            "site": {
                "type": "string",
                "description": "Site name or URL for 'add' (defaults to the label).",
            },
        },
        "required": ["action"],
    }

    def __init__(
        self,
        store: TaskBoardStore | None = None,
        opener: Callable[[str], bool] | None = None,
        on_change: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self._store = store or TaskBoardStore()
        self._opener = opener or webbrowser.open
        self._on_change = on_change

    def _result(self, content: str, *, is_error: bool = False,
                board: dict[str, Any] | None = None) -> ToolResult:
        return ToolResult(
            name=self.name,
            content=content,
            is_error=is_error,
            safety_level=self.safety_level,
            metadata={"board": board} if board is not None else {},
        )

    def _save(self, board: dict[str, Any]) -> dict[str, Any]:
        saved = self._store.save(board)
        if self._on_change is not None:
            try:
                self._on_change(saved)
            except Exception as exc:  # overlay refresh must never break the tool
                logger.warning(f"Task board on_change failed: {exc}")
        return saved

    def _find(self, board: dict[str, Any], label: str) -> dict[str, Any] | None:
        wanted = (label or "").strip().lower()
        for item in board["items"]:
            if item["label"].strip().lower() == wanted:
                return item
        return None

    def execute(
        self,
        action: str = "draw",
        request: str = "",
        label: str = "",
        site: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        act = (action or "draw").lower().strip()

        if act == "draw":
            try:
                board = parse_board_request(request)
            except ValueError as exc:
                return self._result(str(exc), is_error=True)
            saved = self._save(board)
            return self._result(
                f"Drew the task board. {_describe(saved)}.", board=saved
            )

        board = self._store.load()

        if act == "add":
            item_label = (label or "").strip()
            if not item_label:
                return self._result(
                    "Error: 'label' is required to add a board item.", is_error=True
                )
            existing = self._find(board, item_label)
            item = {"label": item_label,
                    "site": _resolve_site(site or item_label)}
            if existing is not None:
                existing.update(item)
            else:
                board["items"].append(item)
            saved = self._save(board)
            return self._result(
                f"Added '{item_label}' to the board. {_describe(saved)}.",
                board=saved,
            )

        if act == "remove":
            item = self._find(board, label)
            if item is None:
                return self._result(
                    f"Error: '{label}' is not on the task board — nothing removed.",
                    is_error=True,
                )
            board["items"].remove(item)
            saved = self._save(board)
            return self._result(
                f"Removed '{item['label']}' from the board. {_describe(saved)}.",
                board=saved,
            )

        if act == "clear":
            board["items"] = []
            saved = self._save(board)
            return self._result("Cleared the task board.", board=saved)

        if act in ("hide", "show"):
            board["visible"] = act == "show"
            saved = self._save(board)
            return self._result(
                f"Task board {'shown' if saved['visible'] else 'hidden'}. "
                f"{_describe(saved)}.",
                board=saved,
            )

        if act == "open":
            item = self._find(board, label)
            if item is None:
                return self._result(
                    f"Error: '{label}' is not on the task board, so I did not "
                    "open anything. Ask me which item you mean.",
                    is_error=True,
                )
            url = resolve_target(item["site"])
            if url is None:
                return self._result(
                    f"Error: '{item['label']}' has no site I can open "
                    f"('{item['site']}').",
                    is_error=True,
                )
            try:
                opened = self._opener(url)
            except Exception as exc:
                return self._result(
                    f"Failed to open {url}: {exc}", is_error=True
                )
            if not opened:
                return self._result(
                    f"Could not open {url}: the system browser did not confirm launch.",
                    is_error=True,
                )
            logger.info(f"Opened board item '{item['label']}' -> {url}.")
            return self._result(
                f"Opened {item['label']} ({url}) from your task board.",
                board=board,
            )

        return self._result(
            f"Unknown action '{action}'. Supported actions: draw, add, remove, "
            "clear, hide, show, open.",
            is_error=True,
        )
