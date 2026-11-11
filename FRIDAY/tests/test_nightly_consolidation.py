"""Checklist B7 (MASTER_COMPLETION_CHECKLIST): nightly memory consolidation.

While the owner sleeps, FRIDAY tidies the day's memories: near-duplicates are
merged (older copy superseded through the auditable lifecycle — the same one
the owner's corrections use), and a one-line day summary is stored.

Contracts locked here, against a REAL MemoraClient on a temp sqlite store
(same local backend the server uses when remote Memora is unreachable):
- consolidate_day_memories merges near-duplicates, keeps distinct facts,
  skips its own prior summaries and stores exactly one marked day summary;
- the night window gate (02:00–05:00 IST) fires at most once per night and
  never outside it;
- every failure is honest and isolated (a failed supersede is a skipped
  merge, a failed summary store is reported, nothing raises into a caller);
- the chat fast-path routes consolidation phrasings to the real pass and
  never hijacks remember/recall/forget/correct.
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.memory.memora_client import MemoraClient  # noqa: E402
from friday.proactive import nightly_consolidation as nc  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoraClient:
    """A MemoraClient pointed at a fresh local sqlite store."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/memora_b7.db")
    monkeypatch.setenv("FRIDAY_MEMORA_REMOTE_ENABLED", "false")
    c = MemoraClient()
    c.remote_enabled = False
    c.base_url = ""
    c._backend = "sqlite"
    c.local_db_path = str(tmp_path / "memora_b7.db")
    c._ensure_tables()
    return c


@pytest.fixture(autouse=True)
def _reset_latch():
    nc.reset_for_tests()
    yield
    nc.reset_for_tests()


def _ist(hour: int, minute: int = 0, day: int = 11) -> datetime:
    from friday.core.owner_time import OWNER_TZ

    return datetime(2026, 11, day, hour, minute, tzinfo=OWNER_TZ)


# ---------------------------------------------------------------------------
# consolidation pass — real client, real store
# ---------------------------------------------------------------------------

class TestConsolidateDayMemories:
    def test_near_duplicates_merged_older_superseded(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai")
        client.record_fact("friday", "my favorite chai is masala chai and I review the fleet every morning at 9")
        report = nc.consolidate_day_memories(client, now=_ist(3))
        assert report["status"] == "consolidated"
        assert report["duplicates_merged"] == 1
        # the richer statement stays live; the shorter copy is superseded
        hits = client.recall_memories("friday", "favorite chai", limit=10)
        live = [h for h in hits if str(h.get("lifecycle_state", "active")) != "superseded"]
        chai_lines = [h for h in live if "chai" in str(h.get("content_text", "")).lower()
                      and not str(h.get("content_text", "")).startswith(nc.SUMMARY_PREFIX)]
        assert len(chai_lines) == 1
        assert "review the fleet" in chai_lines[0]["content_text"]

    def test_distinct_facts_all_kept(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai")
        client.record_fact("friday", "my daughter's favorite cartoon is Bluey")
        client.record_fact("friday", "I review the fleet every morning at 9")
        report = nc.consolidate_day_memories(client, now=_ist(3))
        assert report["duplicates_merged"] == 0
        assert report["records_examined"] >= 3

    def test_summary_stored_once_and_marked(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai")
        report = nc.consolidate_day_memories(client, now=_ist(3))
        assert report["summary_stored"] is True
        assert report["summary_text"].startswith(nc.SUMMARY_PREFIX)
        hits = client.recall_memories("friday", "Daily memory summary", limit=10)
        summaries = [h for h in hits if str(h.get("content_text", "")).startswith(nc.SUMMARY_PREFIX)]
        assert len(summaries) == 1
        # second pass the same night does not stack another summary
        report2 = nc.consolidate_day_memories(client, now=_ist(4))
        assert report2["summary_stored"] is True
        hits2 = client.recall_memories("friday", "Daily memory summary", limit=10)
        summaries2 = [h for h in hits2 if str(h.get("content_text", "")).startswith(nc.SUMMARY_PREFIX)]
        assert len(summaries2) == 1

    def test_prior_summaries_never_consolidated(self, client: MemoraClient):
        client.record_fact("friday", f"{nc.SUMMARY_PREFIX} 2026-11-10: 2 memories kept — quiet day.")
        client.record_fact("friday", f"{nc.SUMMARY_PREFIX} 2026-11-09: 5 memories kept — busy day.")
        report = nc.consolidate_day_memories(client, now=_ist(3))
        # two near-identical summaries must NOT be merged or counted as the day's memories
        assert report["duplicates_merged"] == 0
        assert report["records_examined"] == 0

    def test_empty_day_is_honest_nothing_to_do(self, client: MemoraClient):
        report = nc.consolidate_day_memories(client, now=_ist(3))
        assert report["status"] == "consolidated"
        assert report["records_examined"] == 0
        assert report["summary_stored"] is False
        assert report["note"] == "no live memories found for the day"

    def test_failed_supersede_reported_not_faked(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai")
        client.record_fact("friday", "my favorite chai is masala chai with ginger")

        class RefusesSupersede(MemoraClient):
            def supersede_fact(self, *a, **k):
                return {"status": "error", "error": "refused"}

        refuses = RefusesSupersede.__new__(RefusesSupersede)
        refuses.__dict__.update(client.__dict__)
        report = nc.consolidate_day_memories(refuses, now=_ist(3))
        assert report["duplicates_merged"] == 0
        assert report["merges_skipped"] == 1
        assert report["status"] == "consolidated"  # the pass itself survived

    def test_raising_client_never_propagates(self):
        class Exploding:
            def recall_memories(self, *a, **k):
                raise RuntimeError("store down")

        report = nc.consolidate_day_memories(Exploding(), now=_ist(3))
        assert report["status"] == "consolidated"  # gather is defensive; nothing found
        assert report["records_examined"] == 0

    def test_summary_store_failure_reported(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai")

        class NoRecord(MemoraClient):
            def record_fact(self, *a, **k):
                raise RuntimeError("store down")

        stubborn = NoRecord.__new__(NoRecord)
        stubborn.__dict__.update(client.__dict__)
        report = nc.consolidate_day_memories(stubborn, now=_ist(3))
        assert report["summary_stored"] is False
        assert report["status"] == "consolidated"


# ---------------------------------------------------------------------------
# night window gate
# ---------------------------------------------------------------------------

class TestNightWindowGate:
    def test_runs_inside_window(self, client: MemoraClient):
        report = nc.maybe_run_nightly_consolidation(client, now=_ist(2, 30))
        assert report is not None
        assert report["status"] == "consolidated"

    def test_silent_outside_window(self, client: MemoraClient):
        for hour in (0, 1, 5, 8, 13, 23):
            assert nc.maybe_run_nightly_consolidation(client, now=_ist(hour)) is None

    def test_once_per_night(self, client: MemoraClient):
        first = nc.maybe_run_nightly_consolidation(client, now=_ist(2))
        second = nc.maybe_run_nightly_consolidation(client, now=_ist(4))
        assert first is not None
        assert second is None

    def test_next_night_runs_again(self, client: MemoraClient):
        assert nc.maybe_run_nightly_consolidation(client, now=_ist(3, day=11)) is not None
        assert nc.maybe_run_nightly_consolidation(client, now=_ist(3, day=12)) is not None

    def test_gate_error_never_raises(self):
        class Exploding:
            def recall_memories(self, *a, **k):
                raise RuntimeError("store down")

        report = nc.maybe_run_nightly_consolidation(Exploding(), now=_ist(3))
        assert report is not None  # gate consumed the night but the run is honest
        assert report["status"] == "consolidated"


# ---------------------------------------------------------------------------
# supersede_fact — the B7 merge primitive on the real client
# ---------------------------------------------------------------------------

class TestSupersedeFact:
    def test_supersedes_local_record(self, client: MemoraClient):
        stored = client.record_fact("friday", "old duplicate fact about chai preferences")
        rid = str((stored or {}).get("id") or "")
        assert rid
        result = client.supersede_fact("friday", rid, winner_id="other-id", reason="test merge")
        assert result["status"] == "superseded"

    def test_empty_id_is_an_error(self, client: MemoraClient):
        assert client.supersede_fact("friday", "")["status"] == "error"


# ---------------------------------------------------------------------------
# chat fast-path phrasings
# ---------------------------------------------------------------------------

FIRE_PHRASES = [
    "consolidate your memories",
    "consolidate my memories",
    "clean up your memory",
    "tidy up your memories",
    "organize your memories",
    "consolidate the memories now",
]

NO_FIRE_PHRASES = [
    "remember this boss: my favorite chai is masala chai",
    "what do you remember about me",
    "do you remember my chai preference",
    "forget about the chai preference",
    "actually my favorite chai is cardamom chai",
    "clean up your workspace",
    "organize your tools",
    "what's the fleet status",
    "hello friday",
    "consolidate the database servers",
]


class TestFastPathPhrasings:
    @pytest.mark.parametrize("phrase", FIRE_PHRASES)
    def test_consolidation_phrasings_fire(self, phrase: str):
        from friday.api.server import _memory_consolidation_intent

        assert _memory_consolidation_intent(phrase) is True

    @pytest.mark.parametrize("phrase", NO_FIRE_PHRASES)
    def test_other_intents_untouched(self, phrase: str):
        from friday.api.server import _memory_consolidation_intent

        assert _memory_consolidation_intent(phrase) is False

    def test_consolidate_without_memory_word_does_not_fire(self):
        from friday.api.server import _memory_consolidation_intent

        assert _memory_consolidation_intent("consolidate the fleet") is False
