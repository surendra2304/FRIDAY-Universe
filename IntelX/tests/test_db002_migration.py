"""TASK-DB-002 — migration accounting + schema inventory tests (scoping doc 5).

Runs in CI against the test suite's explicit SQLite URL (see
``IntelX/tests/conftest.py``). Tests are NOT run by this authoring
pass — they are written for CI (see MANIFEST.md).
"""

from __future__ import annotations

import json
from pathlib import Path

from intelx.db.base import Base
from intelx.db.models import WatchEnvelope, WatchSeen
from intelx.watches.db_seen_store import count_file_records

# The 19 IntelX tables declared before TASK-DB-002 (scoping doc section 2.1
# says 18 — that count is wrong; the file declares 19 model classes, verified
# first-hand by counting `class ... (Base)` in models.py, LiveResearchRun included).
EXPECTED_INTELX_TABLES = {
    "research_runs",
    "tasks",
    "sources",
    "documents",
    "chunks",
    "entities",
    "entity_aliases",
    "entity_relations",
    "entity_merges",
    "claims",
    "evidence",
    "findings",
    "artifacts",
    "events",
    "audit_events",
    "review_decisions",
    "policies",
    "api_keys",
    "live_research_runs",
    # TASK-DB-002 additions:
    "watch_seen",
    "watch_envelopes",
}


def test_db002_migration_counts(tmp_path: Path) -> None:
    """Scoping test 12: migration dry-run reports exact before/after counts.

    The board requires the migration to quote counts before and after
    per record class. ``count_file_records`` is the dry-run accounting
    the migration leg uses: it counts what the fixture files hold
    without writing anything. The live migration must report the same
    classes with real counts in the evidence doc.
    """
    state = {
        "version": 1,
        "watches": {
            "ai-model-releases": {
                "seen": {
                    "fp-one": {"status": "alerted"},
                    "fp-two": {"status": "below_threshold"},
                },
                "title_fps": {},
                "alerts_by_day": {},
            },
            "space-watch": {
                "seen": {"fp-three": {"status": "baseline"}},
                "title_fps": {},
                "alerts_by_day": {},
            },
        },
    }
    (tmp_path / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (tmp_path / "outbox.jsonl").write_text(
        '{"schema": "intelx.watch_alert/1", "dedupe_key": "a"}\n'
        '{"schema": "intelx.watch_alert/1", "dedupe_key": "b"}\n',
        encoding="utf-8",
    )
    forecast_state = {
        "forecasts": {"f1": {}, "f2": {}},
        "actuals": {"SYM": [[1700000000, 1.5], [1700003600, 1.6]]},
        "calibration": {"SYM": {}},
    }
    (tmp_path / "forecast_state.json").write_text(
        json.dumps(forecast_state), encoding="utf-8"
    )

    counts = count_file_records(
        tmp_path / "state.json",
        tmp_path / "outbox.jsonl",
        tmp_path / "forecast_state.json",
    )
    assert counts["seen_entries"] == 3
    assert counts["envelopes"] == 2
    assert counts["forecasts"] == 2
    assert counts["actuals"] == 2
    assert counts["calibration"] == 1
    assert counts["unreadable_files"] == []

    # Missing files count as zero; unparseable files are named, not dropped.
    counts = count_file_records(tmp_path / "missing.json", None, None)
    assert counts["seen_entries"] == 0
    (tmp_path / "broken.json").write_text("{not json", encoding="utf-8")
    counts = count_file_records(tmp_path / "broken.json", None, None)
    assert counts["seen_entries"] == 0
    assert str(tmp_path / "broken.json") in counts["unreadable_files"]


def test_db002_schema_inventory() -> None:
    """Scoping test 13: the declared models match the expected ADB #2 inventory.

    IntelX ships 19 pre-existing tables + the 2 TASK-DB-002 tables
    (21 total). If a model is added or dropped without updating this
    list, the test fails loudly instead of the bootstrap silently
    missing a table on ADB #2. The Futuris 13-table inventory is
    asserted by Futuris's own test suite, not here.
    """
    assert set(Base.metadata.tables) == EXPECTED_INTELX_TABLES

    seen_columns = {c.name for c in WatchSeen.__table__.columns}
    assert seen_columns == {
        "watch_id",
        "fingerprint",
        "title_fingerprint",
        "status",
        "first_seen",
        "fired_at",
    }
    assert {c.name for c in WatchSeen.__table__.primary_key.columns} == {
        "watch_id",
        "fingerprint",
    }

    envelope_columns = {c.name for c in WatchEnvelope.__table__.columns}
    assert envelope_columns == {
        "envelope_id",
        "watch_id",
        "dedupe_key",
        "title",
        "summary",
        "url",
        "publisher",
        "published_at",
        "fired_at",
        "score",
        "score_reasons",
        "alert_class",
        "severity",
        "envelope_json",
        "created_at",
    }
    assert {c.name for c in WatchEnvelope.__table__.primary_key.columns} == {
        "envelope_id"
    }
    unique_columns = {
        c.name
        for c in WatchEnvelope.__table__.columns
        if c.unique
    }
    assert "dedupe_key" in unique_columns
