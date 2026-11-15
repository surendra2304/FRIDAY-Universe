"""TASK-FRG-004: the architect discarded explicitly requested file layouts.

Production evidence (2026-11-15, FRG-004 multi-file battery against the
deployed Forge, delegate path): three goals that each stated an exact
multi-file layout in the goal text and requirements -- a package with
__init__/codes/store modules plus tests/, a stdlib REST API split across
app/models.py, app/db.py, app/handlers.py and server.py, and a CLI tool
split across parser/stats/report/cli modules -- all came back with
docs/FILE_MANIFEST.json containing only the keyword-template fallback
(["main.py", "README.md"] or ["main.py", "test_main.py", "README.md"]).
The produced projects were flat main.py + test_main.py (+ one improvised
module): zero files of each requested package layout existed. Every run
ended PARTIAL_FAILURE (9/11 verification stages; lint + pytest failed).

Root cause: roles run on the deterministic DirectProvider in production
(nothing calls set_provider), so the architect's model response is a
stub carrying no FILE_MANIFEST.json; the fallback that then engages
only keyword-matches the goal and never reads the layout the goal
itself states.

These tests pin the fix: when no model-produced manifest exists, the
architect derives the manifest from the file paths the goal and its
requirements state explicitly (explicit_layout_from_goal), and only
falls back to the historical keyword templates when fewer than three
paths are stated.
"""

from __future__ import annotations

from app.agents.roles import explicit_layout_from_goal

PACKAGE_GOAL = (
    "Create a Python package named shortlink for shortening URLs, with "
    "exactly this layout: shortlink/__init__.py exporting encode_id, "
    "decode_id and Shortener; shortlink/codes.py with functions "
    "encode_id(n: int) -> str and decode_id(s: str) -> int implementing "
    "base62; shortlink/store.py with a class Shortener; main.py at the "
    "project root demonstrating shorten and resolve; and "
    "tests/test_shortlink.py with pytest tests."
)

API_GOAL = (
    "Create a small REST API for a bookstore inventory using ONLY the "
    "Python standard library (http.server), with exactly this layout: "
    "app/__init__.py; app/models.py defining a dataclass Book; "
    "app/db.py with an in-memory repository class BookRepo; "
    "app/handlers.py implementing GET /books and POST /books; "
    "server.py at the project root; and tests/test_api.py with pytest "
    "tests that start the server on an ephemeral port."
)


def test_package_layout_extracted_verbatim():
    assert explicit_layout_from_goal(PACKAGE_GOAL) == [
        "shortlink/__init__.py",
        "shortlink/codes.py",
        "shortlink/store.py",
        "main.py",
        "tests/test_shortlink.py",
    ]


def test_api_layout_extracted_and_stdlib_mentions_ignored():
    # "http.server" in the goal is a module name, not a file path, and
    # the route templates /books/<isbn> are not paths either.
    assert explicit_layout_from_goal(API_GOAL) == [
        "app/__init__.py",
        "app/models.py",
        "app/db.py",
        "app/handlers.py",
        "server.py",
        "tests/test_api.py",
    ]


def test_layout_may_come_from_requirements_alone():
    reqs = [
        "the layout exists exactly as specified (pkg/__init__.py, "
        "pkg/core.py, pkg/util.py, main.py)",
        "the pytest tests exist and pass",
    ]
    assert explicit_layout_from_goal("Build the thing", reqs) == [
        "pkg/__init__.py",
        "pkg/core.py",
        "pkg/util.py",
        "main.py",
    ]


def test_goal_and_requirements_dedupe_in_stated_order():
    reqs = ["layout: main.py, pkg/core.py, pkg/util.py, main.py"]
    assert explicit_layout_from_goal(PACKAGE_GOAL, reqs)[:5] == [
        "shortlink/__init__.py",
        "shortlink/codes.py",
        "shortlink/store.py",
        "main.py",
        "tests/test_shortlink.py",
    ]


def test_prose_goal_without_layout_keeps_template_behaviour():
    goal = "Create a python script that sorts numbers and prints them"
    assert explicit_layout_from_goal(goal) == []


def test_two_file_mentions_are_not_a_layout():
    goal = "Create main.py and a test_main.py for a small calculator"
    assert explicit_layout_from_goal(goal) == []


def test_architects_own_artifacts_are_never_a_layout():
    goal = (
        "Write docs/ARCHITECTURE_SPEC.md and docs/FILE_MANIFEST.json "
        "describing a tool with main.py"
    )
    assert explicit_layout_from_goal(goal) == []


def test_urls_versions_and_dotted_modules_are_not_paths():
    goal = (
        "Use http.server and hashlib.pbkdf2_hmac on Python 3.10; see "
        "https://example.com/docs for the spec"
    )
    assert explicit_layout_from_goal(goal) == []
