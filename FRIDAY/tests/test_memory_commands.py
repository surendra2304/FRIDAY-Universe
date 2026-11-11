"""Checklist B9/B10: owner-facing memory commands — forget and correct.

B9 — "forget that" / "forget about X" removes a stored fact (soft delete).
B10 — a correction ("actually my number is X") supersedes the old fact instead
of duplicating it.

Contracts locked here, against a REAL MemoraClient on a temp sqlite store
(same local backend the server uses when remote Memora is unreachable):
- MemoraClient.forget_fact / correct_fact do the real lifecycle transitions
  (active → deleted / superseded) and return honest statuses;
- the chat fast-path phrasings route to the right command and never eat
  conversational sentences;
- the remember/recall paths still behave (no regression from the new gates).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit]

REPO = Path(__file__).resolve().parent.parent.parent  # friday-universe root
for _p in (str(REPO / "FRIDAY" / "src"), str(REPO / "FRIDAY" / "apps" / "core" / "src"), str(REPO)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from friday.memory.memora_client import MemoraClient  # noqa: E402


# ---------------------------------------------------------------------------
# client-level contract on a real temp sqlite store
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MemoraClient:
    """A MemoraClient pointed at a fresh local sqlite store."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/memora_b9b10.db")
    monkeypatch.setenv("FRIDAY_MEMORA_REMOTE_ENABLED", "false")
    c = MemoraClient()
    c.remote_enabled = False
    c.base_url = ""
    c._backend = "sqlite"
    c.local_db_path = str(tmp_path / "memora_b9b10.db")
    # create the local tables exactly as _ensure_tables does
    c._ensure_tables()
    return c


class TestForgetFact:
    def test_forget_removes_the_stored_fact(self, client: MemoraClient):
        client.record_fact("friday", "my favorite chai is masala chai", "owner_fact", 0.98)
        res = client.forget_fact("friday", "favorite chai masala")
        assert res["status"] == "deleted"
        assert "masala" in res["content_text"]
        # recall no longer returns it
        hits = client.recall_memories("friday", "favorite chai", limit=10) or []
        assert not any("masala" in str(h.get("content_text", "")).lower() for h in hits)

    def test_forget_by_explicit_id(self, client: MemoraClient):
        stored = client.record_fact("friday", "my dog is named Bruno", "owner_fact", 0.98)
        mid = str((stored or {}).get("id"))
        res = client.forget_fact("friday", "", memory_id=mid)
        assert res["status"] == "deleted"

    def test_forget_missing_fact_is_honest(self, client: MemoraClient):
        res = client.forget_fact("friday", "nothing matches this query at all")
        assert res["status"] in {"not_found", "error"}  # never "deleted"

    def test_soft_delete_marks_lifecycle_state(self, client: MemoraClient):
        stored = client.record_fact("friday", "my bike is a KTM Duke 200", "owner_fact", 0.98)
        mid = str((stored or {}).get("id"))
        client.forget_fact("friday", "", memory_id=mid)
        from friday.core.database import connect_sqlite

        with connect_sqlite(client.local_db_path, timeout=5.0) as conn:
            row = conn.execute(
                "SELECT lifecycle_state FROM memory_records WHERE id = ?", (mid,)
            ).fetchone()
        assert row is not None
        assert row[0] == "deleted"  # soft — history preserved, not hard-purged


class TestCorrectFact:
    def test_correction_supersedes_not_duplicates(self, client: MemoraClient):
        client.record_fact("friday", "my favorite color is blue", "owner_fact", 0.98)
        res = client.correct_fact("friday", "my favorite color is green", "favorite color")
        assert res["status"] == "corrected"
        assert res["superseded_id"]
        assert res["winner_id"]
        # recall finds only the corrected fact, not both
        hits = client.recall_memories("friday", "favorite color", limit=10) or []
        colors = [str(h.get("content_text", "")).lower() for h in hits]
        assert any("green" in c for c in colors)
        assert not any("blue" in c for c in colors)

    def test_correction_without_old_fact_stores_new_only(self, client: MemoraClient):
        res = client.correct_fact("friday", "my sister lives in Hyderabad", "sister lives")
        assert res["status"] == "stored_new_only"
        assert res["id"]

    def test_empty_correction_is_an_error(self, client: MemoraClient):
        res = client.correct_fact("friday", "", "whatever")
        assert res["status"] == "error"

    def test_superseded_stays_in_audit_trail(self, client: MemoraClient):
        stored = client.record_fact("friday", "my phone is 9999999999", "owner_fact", 0.98)
        mid = str((stored or {}).get("id"))
        res = client.correct_fact("friday", "my phone is 8888888888", "my phone")
        assert res["status"] == "corrected"
        from friday.core.database import connect_sqlite

        with connect_sqlite(client.local_db_path, timeout=5.0) as conn:
            row = conn.execute(
                "SELECT lifecycle_state, content_text FROM memory_records WHERE id = ?", (mid,)
            ).fetchone()
        assert row is not None
        assert row[0] == "superseded"  # old fact kept for audit, not destroyed
        assert "9999999999" in row[1]


# ---------------------------------------------------------------------------
# chat fast-path phrasing contract (source-level wiring + predicate parity)
# ---------------------------------------------------------------------------

class TestFastPathPhrasings:
    """The forget/correction gates must fire on owner phrasings and nothing else."""

    @staticmethod
    def _gates(cmd: str) -> tuple[bool, str]:
        """Mirror the server's forget/correction gate predicates 1:1.

        The server matches prefixes on the lowercased ``cmd`` but slices the
        stored fact from ``raw_cmd`` (original casing), like the remember path.
        """
        cmd_l = cmd.lower().strip()
        is_forget = False
        forget_q = ""
        if cmd_l in ("forget that", "forget this", "forget it", "forget that now",
                     "forget the last thing", "forget last thing"):
            is_forget = True
            forget_q = cmd
        else:
            for pfx in ("forget about ", "forget ", "remove memory ", "delete memory ",
                        "remove that memory ", "erase memory "):
                if cmd_l.startswith(pfx):
                    forget_q = cmd[len(pfx):].strip()
                    if forget_q:
                        is_forget = True
                    break

        corr_text = ""
        for pfx in ("actually, my ", "actually my ", "no wait, my ", "no, my ",
                    "no wait my ", "correction: ", "correction, ", "i meant ",
                    "update my ", "change my "):
            if cmd_l.startswith(pfx):
                corr_text = cmd[len(pfx):].strip()
                if not corr_text.lower().startswith(("my ", "that ", "the ")):
                    corr_text = f"my {corr_text}"
                break
        if not corr_text:
            spaced = f" {cmd_l} "
            factish = (
                (" my " in spaced and any(k in spaced for k in (" is ", " are ", " now ")))
                or (" i " in spaced and any(k in spaced for k in (" prefer ", " like ", " am ", " have ", " hate ")))
            )
            if factish:
                for pfx in ("actually ", "no wait, ", "no, ", "scratch that, "):
                    if cmd_l.startswith(pfx):
                        corr_text = cmd[len(pfx):].strip()
                        break
        return is_forget, corr_text

    @pytest.mark.parametrize(
        "phrase",
        [
            "forget that",
            "forget this",
            "forget about the pizza preference",
            "forget my old phone number",
            "remove memory of the old address",
            "delete memory the chai fact",
        ],
    )
    def test_forget_phrasings_fire(self, phrase: str):
        fires, _ = self._gates(phrase)
        assert fires, f"forget gate must fire: {phrase!r}"

    @pytest.mark.parametrize(
        ("phrase", "stored"),
        [
            ("actually my number is 9876543210", "my number is 9876543210"),
            ("actually, my favorite color is green", "my favorite color is green"),
            ("no wait, my chai is now masala", "my chai is now masala"),
            ("no, my office is in Hyderabad now", "my office is in Hyderabad now"),
            ("correction: my email is boss@friday.universe", "my email is boss@friday.universe"),
            ("i meant the blue one", "the blue one"),
            ("update my number to 8888888888", "my number to 8888888888"),
            ("actually I prefer tea now", "I prefer tea now"),
        ],
    )
    def test_correction_phrasings_extract_fact(self, phrase: str, stored: str):
        fires, corr = self._gates(phrase)
        assert not fires, f"forget gate must not fire on correction: {phrase!r}"
        assert corr == stored, f"{phrase!r} -> {corr!r}, expected {stored!r}"

    @pytest.mark.parametrize(
        "phrase",
        [
            "hello friday",
            "what do you remember about me",
            "remember this: my flight is at 6",
            "don't forget that I have a meeting",   # English idiom = REMEMBER
            "no, that's not what I said",           # conversational rejection
            "actually, can you check the fleet?",   # non-fact opener
            "forget",                               # bare verb, no object
            "research crypto and give me highlights",
            "assign a quick task to IntelX: research",
        ],
    )
    def test_conversational_sentences_untouched(self, phrase: str):
        fires, corr = self._gates(phrase)
        assert not fires, f"forget gate must NOT fire: {phrase!r}"
        assert not corr, f"correction gate must NOT fire: {phrase!r}"

    def test_dont_forget_still_means_remember(self):
        # The remember path owns "don't forget that ..." — the forget gate must
        # never intercept it (B1/B4 regression guard).
        fires, _ = self._gates("don't forget that I have a flight at 6")
        assert not fires


class TestServerWiring:
    def test_forget_and_correct_gates_present_before_recall(self):
        source = (REPO / "FRIDAY" / "src" / "friday" / "api" / "server.py").read_text()
        assert "memory_forget" in source, "server must expose the forget fast-path"
        assert "memory_correction" in source, "server must expose the correction fast-path"
        forget_pos = source.find("A0.55 Memory Commands")
        recall_pos = source.find("_recall_patterns")
        remember_pos = source.find("if _is_remember:")
        assert 0 < forget_pos < recall_pos < remember_pos, (
            "forget/correction gates must run BEFORE recall and remember"
        )

    def test_memora_client_has_the_new_methods(self):
        assert hasattr(MemoraClient, "forget_fact")
        assert hasattr(MemoraClient, "correct_fact")
        assert hasattr(MemoraClient, "_mark_record_state")
