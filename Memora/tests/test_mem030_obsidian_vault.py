"""TASK-MEM-030 — Obsidian-vault second-brain presentation + nightly summaries.

Locks the vault builder (``core.memory.vault``) and the nightly
per-agent summariser (``core.memory.nightly_summary``) against plain
record dicts shaped like ``MemoryRecordRead`` — no live service, no
database: the modules under test are stdlib-only and read whatever
records the caller hands them.
"""

import json

import pytest

from core.memory.nightly_summary import (
    load_records_json,
    run_daily_cycle,
    run_nightly,
    summarize_agent_day,
)
from core.memory.vault import (
    AGENTS,
    VAULT_FOLDERS,
    build_vault,
    normalize_record,
    render_memory_note,
    route,
    safe_filename,
)

DATE = "2026-11-25"


def rec(**kw):
    """One store record; overrides win (provenance replaces wholesale)."""
    base = {
        "id": "mem-001",
        "content_text": "FRIDAY learned that Surendra prefers morning briefings.",
        "memory_type": "episodic",
        "lifecycle_state": "active",
        "namespace_path": "memora://friday/private",
        "agent_id": "friday",
        "created_at": "2026-11-25T08:00:00+05:30",
        "confidence": 0.9,
        "importance": 0.7,
        "scope": "SHARED",
        "source": "session_capture",
        "provenance": {"session_id": "friday-abc123", "event_kind": "observation"},
    }
    base.update(kw)
    return base


def event(**kw):
    """One capture event (a record with a session id)."""
    base = rec()
    base.update(kw)
    return base


# ---------------------------------------------------------------- vault


def test_all_seven_folders_created_and_index_exists(tmp_path):
    manifest = build_vault([rec()], tmp_path)
    for folder in VAULT_FOLDERS:
        assert (tmp_path / folder).is_dir()
    index = (tmp_path / "00 - Second Brain.md").read_text(encoding="utf-8")
    for folder in VAULT_FOLDERS:
        assert folder in index
    assert manifest["folders"]["Memories"] == 1


@pytest.mark.parametrize(
    "overrides, folder",
    [
        ({"memory_type": "project"}, "Projects"),
        ({"memory_type": "semantic"}, "Resources"),
        ({"memory_type": "procedural"}, "Resources"),
        ({"memory_type": "tool"}, "Resources"),
        ({"memory_type": "system"}, "Resources"),
        ({"memory_type": "preference"}, "Areas"),
        ({"memory_type": "decision"}, "Areas"),
        ({"memory_type": "relationship"}, "Areas"),
        ({"memory_type": "episodic"}, "Memories"),
        ({"memory_type": "experience"}, "Memories"),
        ({"memory_type": "working"}, "Memories"),
        ({"lifecycle_state": "candidate"}, "Inbox"),
        ({"memory_type": "semantic", "lifecycle_state": "candidate"}, "Inbox"),
        ({"lifecycle_state": "archived"}, "Archive"),
        ({"lifecycle_state": "superseded"}, "Archive"),
        ({"lifecycle_state": "deleted"}, "Archive"),
        ({"namespace_path": "memora://forge/projects/alpha"}, "Projects"),
    ],
)
def test_routing_table(tmp_path, overrides, folder):
    record = normalize_record(rec(id="route-1", **overrides))
    assert route(record) == folder
    build_vault([rec(id="route-1", **overrides)], tmp_path)
    assert (tmp_path / folder / "route-1.md").is_file()


def test_private_excluded_by_default_and_counted(tmp_path):
    manifest = build_vault(
        [rec(id="priv-1", scope="PRIVATE"), rec(id="pub-1", scope="SHARED")],
        tmp_path,
    )
    assert not (tmp_path / "Memories" / "priv-1.md").exists()
    assert (tmp_path / "Memories" / "pub-1.md").is_file()
    assert manifest["skipped_private"] == 1
    assert manifest["folders"]["Memories"] == 1


def test_private_included_with_opt_in(tmp_path):
    manifest = build_vault(
        [rec(id="priv-1", scope="PRIVATE")], tmp_path, include_private=True
    )
    assert (tmp_path / "Memories" / "priv-1.md").is_file()
    assert manifest["skipped_private"] == 0


def test_unknown_scope_without_namespace_is_private(tmp_path):
    record = rec(id="mystery-1", scope=None, namespace_path=None, agent_id="friday")
    manifest = build_vault([record], tmp_path)
    assert manifest["skipped_private"] == 1
    assert not (tmp_path / "Memories" / "mystery-1.md").exists()


def test_record_without_id_skipped_and_counted(tmp_path):
    manifest = build_vault([rec(id=""), rec(id=None), rec()], tmp_path)
    assert manifest["skipped_no_id"] == 2
    assert manifest["folders"]["Memories"] == 1


def test_frontmatter_body_and_links(tmp_path):
    build_vault([rec()], tmp_path)
    text = (tmp_path / "Memories" / "mem-001.md").read_text(encoding="utf-8")
    assert "id: 'mem-001'" in text
    assert "agent: 'friday'" in text
    assert "type: 'episodic'" in text
    assert "lifecycle: 'active'" in text
    assert "session: 'friday-abc123'" in text
    assert "event_kind: 'observation'" in text
    assert "Surendra prefers morning briefings" in text
    assert "[[friday]]" in text
    assert "[[00 - Second Brain]]" in text


def test_filename_sanitization_no_path_escape(tmp_path):
    assert safe_filename("../evil") == "evil"
    assert safe_filename("a/b\\c:d") == "a_b_c_d"
    build_vault([rec(id="../evil")], tmp_path)
    assert (tmp_path / "Memories" / "evil.md").is_file()
    assert not (tmp_path.parent / "evil.md").exists()


def test_idempotent_rerun_same_files_and_contents(tmp_path):
    first = build_vault([rec(), rec(id="mem-002", memory_type="semantic")], tmp_path)
    # The index note carries a generation timestamp, so it is excluded
    # from the byte comparison; every other note must be identical.
    compared = [p for p in first["written"] if p != "00 - Second Brain.md"]
    before = {
        p: (tmp_path / p).read_text(encoding="utf-8") for p in compared
    }
    second = build_vault([rec(), rec(id="mem-002", memory_type="semantic")], tmp_path)
    assert second["written"] == first["written"]
    for path, text in before.items():
        assert (tmp_path / path).read_text(encoding="utf-8") == text
    assert (tmp_path / "00 - Second Brain.md").is_file()


def test_agent_hub_notes_for_all_ten_agents(tmp_path):
    build_vault([], tmp_path)
    for agent in AGENTS:
        note = tmp_path / "Areas" / "Agents" / (agent + ".md")
        assert note.is_file()
        assert "No memories filed for this agent yet." in note.read_text(
            encoding="utf-8"
        )


def test_agent_derived_from_namespace(tmp_path):
    record = rec(id="ns-1", agent_id=None, namespace_path="memora://sentinel/private")
    build_vault([record], tmp_path)
    text = (tmp_path / "Memories" / "ns-1.md").read_text(encoding="utf-8")
    assert "agent: 'sentinel'" in text


def test_empty_store_builds_empty_vault(tmp_path):
    manifest = build_vault([], tmp_path)
    assert all(count == 0 for count in manifest["folders"].values())
    assert (tmp_path / "00 - Second Brain.md").is_file()


def test_render_memory_note_title_falls_back_to_id(tmp_path):
    record = normalize_record(rec(id="abc1234567890", content_text=""))
    assert record["title"].startswith("Untitled memory")
    assert "abc1234567890"[:12] in render_memory_note(record)


# ---------------------------------------------------------------- nightly


def test_one_summary_per_agent_with_events(tmp_path):
    events = [
        event(id="e1", agent_id="friday", provenance={"session_id": "friday-s1", "event_kind": "tool_call"}),
        event(id="e2", agent_id="friday", content_text="Decided to retry the sync.",
              provenance={"session_id": "friday-s1", "event_kind": "decision"}),
        event(id="e3", agent_id="friday", content_text="Observed the queue drain.",
              provenance={"session_id": "friday-s2", "event_kind": "observation"}),
        event(id="e4", agent_id="forge", content_text="Edited the deploy script.",
              provenance={"session_id": "forge-s1", "event_kind": "file_edit"}),
    ]
    manifest = run_nightly(events, DATE, tmp_path)
    assert set(manifest["agents"]) == set(AGENTS)
    friday = manifest["agents"]["friday"]
    assert friday["events"] == 3
    assert friday["sessions"] == 2
    text = (tmp_path / "Daily Logs" / "2026-11-25-friday.md").read_text(encoding="utf-8")
    assert "3 captured event(s) across 2 session(s)" in text
    assert "- tool_call: 1" in text
    assert "- decision: 1" in text
    assert "- observation: 1" in text
    assert "## Session friday-s1" in text
    assert "## Session friday-s2" in text
    assert "[[e1]]" in text and "[[e2]]" in text and "[[e3]]" in text
    assert "Decided to retry the sync." in text


def test_silent_agent_gets_honest_no_work_note(tmp_path):
    run_nightly([event(agent_id="friday")], DATE, tmp_path)
    text = (tmp_path / "Daily Logs" / "2026-11-25-memora.md").read_text(encoding="utf-8")
    assert "No captured work for memora on 2026-11-25." in text
    assert "nothing is invented" in text


def test_events_from_other_days_excluded(tmp_path):
    events = [
        event(id="today-1", created_at="2026-11-25T08:00:00+05:30"),
        event(id="yesterday-1", created_at="2026-11-24T08:00:00+05:30"),
    ]
    manifest = run_nightly(events, DATE, tmp_path)
    assert manifest["agents"]["friday"]["events"] == 1
    text = (tmp_path / "Daily Logs" / "2026-11-25-friday.md").read_text(encoding="utf-8")
    assert "[[today-1]]" in text
    assert "yesterday-1" not in text


def test_unknown_kind_normalized_to_observation(tmp_path):
    run_nightly(
        [event(provenance={"session_id": "friday-s1", "event_kind": "telepathy"})],
        DATE,
        tmp_path,
    )
    text = (tmp_path / "Daily Logs" / "2026-11-25-friday.md").read_text(encoding="utf-8")
    assert "- observation: 1" in text
    assert "telepathy" not in text


def test_duplicate_first_lines_collapsed(tmp_path):
    events = [
        event(id="d1", content_text="Same line twice.",
              provenance={"session_id": "friday-s1", "event_kind": "observation"}),
        event(id="d2", content_text="Same line twice.",
              provenance={"session_id": "friday-s1", "event_kind": "observation"}),
    ]
    run_nightly(events, DATE, tmp_path)
    text = (tmp_path / "Daily Logs" / "2026-11-25-friday.md").read_text(encoding="utf-8")
    assert text.count("Same line twice.") == 1


def test_private_event_excluded_from_summary_by_default(tmp_path):
    events = [event(id="priv-e1", scope="PRIVATE")]
    manifest = run_nightly(events, DATE, tmp_path)
    assert manifest["agents"]["friday"]["events"] == 0
    manifest2 = run_nightly(events, DATE, tmp_path, include_private=True)
    assert manifest2["agents"]["friday"]["events"] == 1


def test_non_capture_records_not_summarised(tmp_path):
    memory = rec(
        id="sem-1", memory_type="semantic", source="manual",
        provenance={}, content_text="A durable fact.",
    )
    manifest = run_nightly([memory], DATE, tmp_path)
    assert manifest["agents"]["friday"]["events"] == 0


def test_summarize_agent_day_rejects_bad_date():
    with pytest.raises(ValueError):
        summarize_agent_day("friday", "25-11-2026", [])
    with pytest.raises(ValueError):
        run_nightly([], "tomorrow", "/tmp")


def test_load_records_json_list_and_jsonl(tmp_path):
    list_file = tmp_path / "list.json"
    list_file.write_text(json.dumps([rec(), rec(id="mem-002")]), encoding="utf-8")
    assert [r["id"] for r in load_records_json(list_file)] == ["mem-001", "mem-002"]
    jsonl_file = tmp_path / "records.jsonl"
    jsonl_file.write_text(
        json.dumps(rec()) + "\n" + json.dumps(rec(id="mem-003")) + "\n",
        encoding="utf-8",
    )
    assert [r["id"] for r in load_records_json(jsonl_file)] == ["mem-001", "mem-003"]
    empty_file = tmp_path / "empty.json"
    empty_file.write_text("", encoding="utf-8")
    assert load_records_json(empty_file) == []


def test_run_daily_cycle_combines_vault_and_summaries(tmp_path):
    semantic = rec(
        id="sem-9", memory_type="semantic", source="manual", provenance={},
    )
    manifest = run_daily_cycle([event(), semantic], DATE, tmp_path)
    assert (tmp_path / "Memories" / "mem-001.md").is_file()
    assert (tmp_path / "Resources" / "sem-9.md").is_file()
    assert (tmp_path / "Daily Logs" / "2026-11-25-friday.md").is_file()
    assert manifest["vault"]["folders"]["Memories"] == 1
    assert manifest["nightly"]["agents"]["friday"]["events"] == 1
    assert manifest["nightly"]["agents"]["memora"]["events"] == 0
