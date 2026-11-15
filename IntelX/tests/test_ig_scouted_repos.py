"""Tests for TASK-IG-INT-06 — scouted open-source repo registry.

The registry is generated from the verified spec cards in
~/workspace/ig-references/repos/ (+ INDEX.md); these tests pin the audited
facts so drift between the shipped registry and the cards is caught.
"""

from __future__ import annotations

from intelx.scouted_repos import all_entries, by_agent, by_fit, by_repo, summary


def test_registry_has_all_32_verified_cards() -> None:
    entries = all_entries()
    assert len(entries) == 32
    assert len({e["card"] for e in entries}) == 32
    for entry in entries:
        assert entry["repo"] and "/" in entry["repo"]
        assert entry["repo_url"].startswith("https://github.com/")
        assert entry["license"]
        assert entry["fit"] in {"adopt", "adapt", "reference-only", "reject"}
        assert entry["fit_rationale"]


def test_fit_counts_match_the_cards() -> None:
    counts = summary()["fit_counts"]
    # Cards + repos/INDEX.md agree on these numbers (see module docstring
    # for the roll-up summary transposition note).
    assert counts == {"adopt": 2, "adapt": 15, "reference-only": 13, "reject": 2}


def test_binding_verdicts_spot_checks() -> None:
    agent_reach = by_repo("Panniantong/Agent-Reach")
    assert agent_reach is not None
    assert agent_reach["fit"] == "adapt"
    assert agent_reach["friday_agents"] == ["IntelX"]
    assert agent_reach["source_videos"] == ["DerbBtfzj8p"]
    # The two hardware rejects from the corpus pass.
    rejects = {e["repo"] for e in by_fit("reject")}
    assert rejects == {"Niko1221/Strata", "Lightricks/LTX-2"}
    # The two adopts.
    adopts = {e["repo"] for e in by_fit("adopt")}
    assert adopts == {"Genymobile/scrcpy", "lnkiai/m3e-canvas"}


def test_queries() -> None:
    intelx = by_agent("IntelX")
    assert [e["repo"] for e in intelx] == ["Panniantong/Agent-Reach"]
    assert len(by_fit("adopt")) == 2
    assert by_repo("does/not-exist") is None
    s = summary()
    assert s["count"] == 32
    assert s["agent_counts"]["Stratex"] >= 4


def test_every_entry_traces_to_corpus_sources() -> None:
    for entry in all_entries():
        assert entry["source_videos"], entry["card"]
        assert all(len(code) == 11 for code in entry["source_videos"])
