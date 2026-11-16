"""TASK-IG2-FRG-01: Karpathy-derived coding principles adopted into Forge.

Pins: all four principles present in the machine-readable module AND in
Forge/AGENT_GUIDELINES.md (with attribution + licence caveat), guidance
rendering, preflight (principles 1+4) and scope check (principle 3).
"""
from __future__ import annotations

from pathlib import Path

from forge_upgrade.coding_principles import (
    PRINCIPLES,
    guidance_block,
    preflight,
    scope_check,
)

GUIDELINES = Path(__file__).resolve().parents[1] / "AGENT_GUIDELINES.md"
EXPECTED_TITLES = [
    "Think Before Coding",
    "Simplicity First",
    "Surgical Changes",
    "Goal-Driven Execution",
]


def test_four_principles_in_order() -> None:
    assert [p.title for p in PRINCIPLES] == EXPECTED_TITLES
    assert all(p.guidance.strip() for p in PRINCIPLES)
    assert len({p.id for p in PRINCIPLES}) == 4


def test_guidance_block_renders_all_principles() -> None:
    block = guidance_block()
    for title in EXPECTED_TITLES:
        assert title in block


def test_guidelines_file_carries_principles_attribution_and_caveat() -> None:
    text = GUIDELINES.read_text(encoding="utf-8")
    for title in EXPECTED_TITLES:
        assert title in text
    # Attribution: Chang distilled, Karpathy observed, source repo named.
    assert "Forrest Chang" in text
    assert "Andrej Karpathy" in text
    assert "andrej-karpathy-skills" in text
    # Licence caveat: MIT declared but no LICENSE file in the source repo.
    assert "no LICENSE file" in text
    assert "MIT" in text


def test_preflight_passes_with_assumptions_and_criteria() -> None:
    report = preflight(
        "Add a widget counter",
        assumptions=["counts are per-workspace"],
        success_criteria=["pytest Forge/tests/test_widget.py passes"],
    )
    assert report.ok
    assert report.missing == []


def test_preflight_blocks_silent_interpretation() -> None:
    report = preflight("Add a widget counter")
    assert not report.ok
    assert any("assumptions" in m for m in report.missing)
    assert any("success criteria" in m for m in report.missing)


def test_preflight_blocks_empty_task() -> None:
    report = preflight("  ", assumptions=["a"], success_criteria=["b"])
    assert not report.ok
    assert any("empty" in m for m in report.missing)


def test_scope_check_accepts_declared_scope() -> None:
    report = scope_check(
        ["Forge/forge_upgrade/widget.py", "Forge/tests/test_widget.py"],
        ["Forge/forge_upgrade", "Forge/tests"],
    )
    assert report.ok
    assert report.out_of_scope == []


def test_scope_check_flags_drive_by_changes() -> None:
    report = scope_check(
        ["Forge/forge_upgrade/widget.py", "Stratex/app/engine.py"],
        ["Forge/forge_upgrade"],
    )
    assert not report.ok
    assert report.out_of_scope == ["Stratex/app/engine.py"]
