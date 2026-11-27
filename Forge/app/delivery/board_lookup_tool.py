"""
Board task lookup — the TASK-FRG-030 proof tool.

Answers the question every worker asks all day: "what is the state of task X
/ what is free in lane Y?" Reads ``docs/collaboration/WORK_BOARD.yaml`` live
and returns matching board records (id, title, status, owner, branch, pr)
plus summary counts. Read-only: no secrets, no writes, no network beyond an
optional raw-GitHub fallback when no local board file exists.

The tool is delivered through the Gradio layer
(:mod:`app.delivery.gradio_layer`); the lookup logic itself is plain Python
so it can be tested without Gradio installed.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("delivery.board_lookup_tool")

BOARD_REL_PATH = Path("docs/collaboration/WORK_BOARD.yaml")
BOARD_RAW_URL = (
    "https://raw.githubusercontent.com/surendra2304/FRIDAY-Universe/main/"
    "docs/collaboration/WORK_BOARD.yaml"
)

STATUSES = (
    "ANY",
    "PROPOSED",
    "AVAILABLE",
    "CLAIMED",
    "IN_PROGRESS",
    "BLOCKED",
    "IN_REVIEW",
    "MERGED",
    "DEPLOYED",
    "VERIFIED",
    "CLOSED",
)


def _load_board(board_path: str | Path | None) -> list[dict[str, Any]]:
    """Load the board's task list from a local file (or the raw main URL)."""
    import yaml

    path = Path(board_path) if board_path else BOARD_REL_PATH
    if path.exists():
        text = path.read_text(encoding="utf-8")
    else:  # no local checkout: read the live main copy (read-only GET)
        import urllib.request

        logger.info("no local board at %s; fetching %s", path, BOARD_RAW_URL)
        with urllib.request.urlopen(BOARD_RAW_URL, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    data = yaml.safe_load(text)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    if not isinstance(tasks, list):
        raise ValueError("board file has no top-level 'tasks' list")
    return tasks


def list_owners(board_path: str | Path | None = None) -> list[str]:
    """Distinct non-empty owners on the board, sorted (for the UI dropdown)."""
    owners = sorted({str(t.get("owner")) for t in _load_board(board_path) if t.get("owner")})
    return ["ANY"] + owners


def lookup_board_tasks(
    task_id: str = "",
    status: str = "ANY",
    owner: str = "ANY",
    max_rows: int = 10,
    board_path: str | Path | None = None,
) -> str:
    """Filter board tasks and render them as markdown.

    ``task_id`` matches by substring (case-insensitive) so ``FRG-030`` finds
    ``TASK-FRG-030``; ``status``/``owner`` must match exactly unless ``ANY``.
    """
    tasks = _load_board(board_path)
    needle = (task_id or "").strip().upper()
    status = (status or "ANY").upper()
    owner = (owner or "ANY").strip()
    max_rows = max(1, min(int(max_rows), 50))

    matched: list[dict[str, Any]] = []
    for task in tasks:
        tid = str(task.get("id", ""))
        if needle and needle not in tid.upper():
            continue
        if status != "ANY" and str(task.get("status", "")).upper() != status:
            continue
        if owner != "ANY" and str(task.get("owner", "")) != owner:
            continue
        matched.append(task)

    counts: dict[str, int] = {}
    for task in tasks:
        counts[str(task.get("status", "?"))] = counts.get(str(task.get("status", "?")), 0) + 1

    lines = [
        f"Board: {len(tasks)} tasks, {len(matched)} matched "
        f"(showing up to {max_rows}).",
        "By status: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) + ".",
        "",
    ]
    if not matched:
        lines.append("No matching tasks.")
        return "\n".join(lines)
    lines.append("| id | title | status | owner | branch | pr |")
    lines.append("|---|---|---|---|---|---|")
    for task in matched[:max_rows]:
        title = str(task.get("title", "")).replace("|", "/")[:80]
        lines.append(
            f"| {task.get('id', '')} | {title} | {task.get('status', '')} | "
            f"{task.get('owner', '') or ''} | {task.get('branch', '') or ''} | "
            f"{task.get('pr', '') or ''} |"
        )
    if len(matched) > max_rows:
        lines.append(f"\n… and {len(matched) - max_rows} more (raise max rows).")
    return "\n".join(lines)


def board_lookup_spec(board_path: str | Path | None = None) -> Any:
    """ToolSpec for the board lookup, wired for the Gradio layer.

    Owner choices are read from the live board at spec-build time so the
    dropdown always reflects current owners.
    """
    from app.delivery.gradio_layer import ToolSpec

    owners = list_owners(board_path)

    def _run(task_id: str, status: str, owner: str, max_rows: int) -> str:
        return lookup_board_tasks(task_id, status, owner, int(max_rows), board_path)

    return ToolSpec(
        name="FRIDAY board task lookup",
        description=(
            "Look up work-board tasks by id, status or owner. "
            "Read-only: reads docs/collaboration/WORK_BOARD.yaml live."
        ),
        fn=_run,
        inputs=[
            {"kind": "textbox", "label": "Task id (substring, e.g. FRG-030)",
             "placeholder": "FRG-030"},
            {"kind": "dropdown", "label": "Status", "choices": list(STATUSES),
             "default": "ANY"},
            {"kind": "dropdown", "label": "Owner", "choices": owners, "default": "ANY"},
            {"kind": "slider", "label": "Max rows", "minimum": 1, "maximum": 50,
             "step": 1, "default": 10},
        ],
        outputs=[{"kind": "markdown"}],
        examples=[
            ["FRG-030", "ANY", "ANY", 10],
            ["", "AVAILABLE", "muse_11", 10],
            ["", "CLAIMED", "ANY", 10],
        ],
    )
