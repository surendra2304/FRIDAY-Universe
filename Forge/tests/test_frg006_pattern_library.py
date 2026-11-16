"""
TASK-FRG-006: Forge pattern library tests.

The library mines Forge's verified successful builds (TASK-REL-028 run 6;
the deterministic synthesis generators) into starting templates. These
tests pin: the matcher (conservative -- web and vague goals get nothing),
the mined manifest shapes, the provenance discipline, and the three
integration points (Architect prompt seeding + manifest fallback,
Developer manifest fallback, Tester multi-file test context).

On clean main every test here fails: app.agents.pattern_library does not
exist and the roles carry no pattern behaviour.
"""

import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.agents.pattern_library import (
    PATTERNS,
    PATTERNS_BY_ID,
    extract_module_name,
    match_pattern,
)
from app.agents.roles import ArchitectRole, DeveloperRole
from app.core.config import Settings
from app.core.workspace import WorkspaceManager
from app.execution.engine import ExecutionEngine
from app.providers.base import ProviderResponse, UsageEstimate

ROMAN_GOAL = (
    "Create a small Python project: a module roman.py with functions "
    "to_roman(n: int) -> str and from_roman(s: str) -> int implementing "
    "standard Roman numerals, and a main.py that demonstrates both "
    "functions on a few examples."
)

PALINDROME_GOAL = (
    "Write a Python program with a function is_palindrome(s: str) -> bool "
    "that checks whether a string reads the same forwards and backwards, "
    "plus a main.py demonstrating it on examples."
)


# ---------------------------------------------------------------------------
# Matcher
# ---------------------------------------------------------------------------


def test_palindrome_goal_matches_rel028_single_module_pattern():
    m = match_pattern(PALINDROME_GOAL, [])
    assert m is not None
    assert m.pattern.id == "python-single-module"
    assert m.manifest == ["main.py", "test_main.py", "README.md"]


def test_named_module_goal_matches_two_module_pattern_with_module_in_manifest():
    # The REL-028 failure shape: the old generic fallback produced
    # [main.py, README.md] and silently dropped the named module.
    m = match_pattern(ROMAN_GOAL, [])
    assert m is not None
    assert m.pattern.id == "python-two-module"
    assert m.module_name == "roman"
    assert m.manifest == ["roman.py", "main.py", "test_main.py", "README.md"]


def test_library_only_module_goal_uses_library_manifest():
    m = match_pattern(
        "Create a Python module textstats.py with functions word_count(text) "
        "and top_words(text, n) and unit tests for them.",
        [],
    )
    assert m is not None
    assert m.pattern.id == "python-two-module"
    assert m.manifest == ["textstats.py", "test_textstats.py", "README.md"]


def test_cli_crud_goal_matches_cli_pattern():
    m = match_pattern(
        "Build a command-line tool in Python to manage notes: add, list, "
        "delete and search notes stored in a local JSON file.",
        [],
    )
    assert m is not None
    assert m.pattern.id == "python-cli-crud"
    assert m.manifest == ["main.py", "test_main.py", "requirements.txt", "README.md"]


def test_fastapi_goal_matches_api_pattern():
    m = match_pattern(
        "Create a FastAPI REST API for managing books with create, list, "
        "get, update and delete endpoints and tests.",
        [],
    )
    assert m is not None
    assert m.pattern.id == "fastapi-crud"


def test_web_goal_gets_no_pattern():
    assert (
        match_pattern(
            "Build a modern responsive portfolio website with my projects "
            "and a contact form.",
            [],
        )
        is None
    )


def test_vague_and_empty_goals_get_no_pattern():
    assert match_pattern("", []) is None
    assert match_pattern("Make something cool with data.", []) is None


def test_extract_module_name_ignores_entry_points():
    assert extract_module_name("a module main.py with functions") is None
    assert extract_module_name(ROMAN_GOAL) == "roman"


# ---------------------------------------------------------------------------
# Library discipline
# ---------------------------------------------------------------------------


def test_every_pattern_carries_provenance_and_unique_id():
    ids = [p.id for p in PATTERNS]
    assert len(ids) == len(set(ids))
    for p in PATTERNS:
        assert p.provenance.strip(), f"{p.id} has no provenance"
        assert p.manifest, f"{p.id} has no manifest"
        assert PATTERNS_BY_ID[p.id] is p


def test_guidance_names_manifest_and_test_layout():
    m = match_pattern(ROMAN_GOAL, [])
    assert m is not None
    guidance = m.guidance
    assert "roman.py" in guidance
    assert "parent.parent" in guidance  # the PR #213 lesson is encoded


# ---------------------------------------------------------------------------
# Role integration
# ---------------------------------------------------------------------------


class _RecordingProvider:
    """Provider stub: records prompts, returns a fixed manifest-less reply."""

    mock_response = "stub"

    def __init__(self, reply: str):
        self.reply = reply
        self.prompts: list[str] = []

    async def generate(self, prompt, system_prompt=None, temperature=0.2):
        self.prompts.append(prompt)
        return ProviderResponse(
            content=self.reply,
            model="stub",
            usage=UsageEstimate(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )


@pytest.fixture
def temp_engine(tmp_path: Path):
    settings = Settings()
    settings.workspaces_dir = tmp_path / "workspaces"
    wm = WorkspaceManager(settings=settings)
    engine = ExecutionEngine(wm=wm)
    return engine, wm


@pytest.mark.asyncio
async def test_architect_fallback_uses_pattern_manifest_for_two_module_goal(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = _RecordingProvider("Architecture: a roman numeral module and a demo.")
    architect = ArchitectRole(provider=provider)
    result = await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture & Module Design",
        context={"goal": ROMAN_GOAL, "requirements": []},
        engine=engine,
    )

    assert result["status"] == "success"
    assert result["pattern_id"] == "python-two-module"
    assert result["file_manifest"] == ["roman.py", "main.py", "test_main.py", "README.md"]
    on_disk = json.loads(
        engine.fs.read_file(task_id, "docs/FILE_MANIFEST.json", role="architect")
    )
    assert on_disk == result["file_manifest"]


@pytest.mark.asyncio
async def test_architect_prompt_is_seeded_with_the_pattern(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = _RecordingProvider("Architecture: one file.")
    architect = ArchitectRole(provider=provider)
    await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture & Module Design",
        context={"goal": PALINDROME_GOAL, "requirements": []},
        engine=engine,
    )
    assert provider.prompts, "architect never prompted its model"
    assert "python-single-module" in provider.prompts[0]
    assert "Proven build pattern" in provider.prompts[0]


@pytest.mark.asyncio
async def test_architect_web_goal_is_untouched_by_the_library(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = _RecordingProvider("Architecture: a website.")
    architect = ArchitectRole(provider=provider)
    result = await architect.execute_step(
        task_id=task_id,
        node_title="System Architecture & Module Design",
        context={
            "goal": "Build a modern responsive portfolio website",
            "requirements": [],
        },
        engine=engine,
    )
    assert result["pattern_id"] is None
    assert "index.html" in result["file_manifest"]
    assert "Proven build pattern" not in provider.prompts[0]


@pytest.mark.asyncio
async def test_developer_without_any_manifest_starts_from_pattern(temp_engine):
    engine, wm = temp_engine
    task_id = str(uuid4())
    wm.create_workspace(task_id)

    provider = _RecordingProvider("print('hello')\n")
    developer = DeveloperRole(provider=provider)
    result = await developer.execute_step(
        task_id=task_id,
        node_title="Implement Core Logic",
        context={"goal": ROMAN_GOAL, "requirements": []},
        engine=engine,
    )
    # The pattern manifest names roman.py first; the old fallback wrote
    # main.py only and the module vanished.
    assert "roman.py" in result["files_written"]
    assert "main.py" in result["files_written"]
