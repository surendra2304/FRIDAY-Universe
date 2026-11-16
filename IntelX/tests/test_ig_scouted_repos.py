"""Tests for TASK-IG-INT-06 — scouted open-source repo registry.

The registry is generated from the verified spec cards in
~/workspace/ig-references/repos/ (+ INDEX.md) by
IntelX/scripts/generate_scouted_repos.py; these tests pin the audited
facts so drift between the shipped registry and the cards is caught.
Wave 1 (32 cards, 2026-11-15) was extended to all 102 verified cards
(waves 2 + 2b, 2026-11-16) by the IG full-watch incorporation
(package items X-06/X-08).
"""

from __future__ import annotations

from intelx.scouted_repos import all_entries, by_agent, by_fit, by_repo, summary


def test_registry_has_all_102_verified_cards() -> None:
    entries = all_entries()
    assert len(entries) == 102
    assert len({e["card"] for e in entries}) == 102
    for entry in entries:
        assert entry["repo"] and "/" in entry["repo"]
        assert entry["repo_url"].startswith("https://github.com/")
        assert entry["license"]
        assert entry["fit"] in {"adopt", "adapt", "reference-only", "reject"}
        assert entry["fit_rationale"]


def test_fit_counts_match_the_cards() -> None:
    counts = summary()["fit_counts"]
    # Cards + repos/INDEX.md agree on these numbers (see module docstring
    # for the wave-1 roll-up summary transposition note).
    assert counts == {"adopt": 6, "adapt": 40, "reference-only": 46, "reject": 10}


def test_binding_verdicts_spot_checks() -> None:
    agent_reach = by_repo("Panniantong/Agent-Reach")
    assert agent_reach is not None
    assert agent_reach["fit"] == "adapt"
    assert agent_reach["friday_agents"] == ["IntelX"]
    assert agent_reach["source_videos"] == ["DerbBtfzj8p"]
    # Wave-2 spot check: the camofox sidecar card (X-08 inventory).
    camofox = by_repo("jo-inc/camofox-browser")
    assert camofox is not None
    assert camofox["fit"] == "adapt"
    assert camofox["friday_agents"] == ["IntelX", "FRIDAY"]
    assert camofox["source_videos"] == ["DZpdEVQAiDr", "Dc-zw_Vicxs", "Deg346vDphY"]
    # The rejects: the two wave-1 hardware rejects plus the eight wave-2
    # rejects (incl. the X-09 awareness-only opendirectory-finder, which
    # is registered, never implemented).
    rejects = {e["repo"] for e in by_fit("reject")}
    assert rejects == {
        "Niko1221/Strata",
        "Lightricks/LTX-2",
        "black-forest-labs/flux2",
        "ace-step/ACE-Step-1.5",
        "NVlabs/Sana",
        "meituan-longcat/LongCat-Video",
        "deepbeepmeep/WanGP",
        "miuuyy/codex-chatgpt-web",
        "Comfy-Org/ComfyUI",
        "ewasion/opendirectory-finder",
    }
    # The adopts.
    adopts = {e["repo"] for e in by_fit("adopt")}
    assert adopts == {
        "Genymobile/scrcpy",
        "lnkiai/m3e-canvas",
        "cathrynlavery/diagram-design",
        "multica-ai/andrej-karpathy-skills",
        "Graphify-Labs/graphify",
        "alibaba/open-code-review",
    }


def test_queries() -> None:
    intelx = by_agent("IntelX")
    assert [e["repo"] for e in intelx] == [
        "Panniantong/Agent-Reach",
        "jo-inc/camofox-browser",
        "LearningCircuit/local-deep-research",
        "thalha-a9/helix",
        "ewasion/opendirectory-finder",
        "apurvsinghgautam/robin",
    ]
    assert len(by_fit("adopt")) == 6
    assert by_repo("does/not-exist") is None
    s = summary()
    assert s["count"] == 102
    assert s["agent_counts"]["Stratex"] >= 4


def test_every_entry_traces_to_corpus_sources() -> None:
    for entry in all_entries():
        assert entry["source_videos"], entry["card"]
        assert all(len(code) == 11 for code in entry["source_videos"])
