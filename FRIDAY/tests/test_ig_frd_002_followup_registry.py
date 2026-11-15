"""TASK-IG-FRD-002 — persistent follow-up registry tests (hermetic)."""

from __future__ import annotations

import time

import pytest

from friday.proactive.followup_registry import (
    STATUS_DONE,
    STATUS_DROPPED,
    STATUS_OPEN,
    FollowUpRegistry,
)


class FakeMemora:
    """Records record_fact calls; can be told to fail or error-dict."""

    def __init__(self, mode: str = "success"):
        self.mode = mode
        self.calls: list[dict] = []

    def record_fact(self, agent_name, fact_text, category="preference", importance=0.95):
        self.calls.append(
            {"agent": agent_name, "text": fact_text, "category": category, "importance": importance}
        )
        if self.mode == "success":
            return {"status": "success", "id": "mem-123"}
        if self.mode == "local_only":
            return {"status": "local_only", "id": "loc-9"}
        if self.mode == "error_dict":
            return {"status": "error", "error": "403 policy: semantic reserved"}
        raise RuntimeError("memora unreachable")


@pytest.fixture()
def registry(tmp_path):
    return FollowUpRegistry(
        store_path=str(tmp_path / "registry.json"), memora_client=FakeMemora()
    )


def test_add_persists_and_mirrors_episodically(registry):
    rec = registry.add("Chase the landlord about the deposit", "flat 4B", source="voice")
    assert rec["status"] == STATUS_OPEN
    assert rec["memora_mirror"]["status"] == "ok"
    fake = registry._memora
    assert len(fake.calls) == 1
    assert fake.calls[0]["category"] == "followup"
    assert "FOLLOWUP (open)" in fake.calls[0]["text"]


def test_add_requires_title(registry):
    with pytest.raises(ValueError):
        registry.add("   ")


def test_mirror_failure_is_reported_not_faked(tmp_path):
    reg = FollowUpRegistry(
        store_path=str(tmp_path / "r.json"), memora_client=FakeMemora("raise")
    )
    rec = reg.add("Pay the electricity bill")
    assert rec["status"] == STATUS_OPEN  # the follow-up itself stands
    assert rec["memora_mirror"]["status"] == "failed"
    assert "unreachable" in rec["memora_mirror"]["detail"]


def test_mirror_error_dict_is_failure_not_success(tmp_path):
    # The MEM-008 lesson: an error dict from record_fact is NOT a store.
    reg = FollowUpRegistry(
        store_path=str(tmp_path / "r.json"), memora_client=FakeMemora("error_dict")
    )
    rec = reg.add("Check the invoice")
    assert rec["memora_mirror"]["status"] == "failed"


def test_mirror_local_only_is_ok_and_labelled(tmp_path):
    reg = FollowUpRegistry(
        store_path=str(tmp_path / "r.json"), memora_client=FakeMemora("local_only")
    )
    rec = reg.add("Renew the domain")
    assert rec["memora_mirror"]["status"] == "ok"
    assert "local_only" in rec["memora_mirror"]["detail"]


def test_no_memora_client_means_unavailable_mirror(tmp_path):
    reg = FollowUpRegistry(store_path=str(tmp_path / "r.json"), memora_client=None)
    rec = reg.add("Call the bank")
    assert rec["memora_mirror"]["status"] == "unavailable"


def test_complete_and_drop_are_explicit(registry):
    a = registry.add("A")
    b = registry.add("B")
    done = registry.complete(a["id"], "paid in full")
    assert done["status"] == STATUS_DONE
    dropped = registry.drop(b["id"])
    assert dropped["status"] == STATUS_DROPPED
    assert registry.list(status=STATUS_OPEN) == []
    with pytest.raises(ValueError):
        registry.complete(a["id"])  # already closed
    with pytest.raises(KeyError):
        registry.complete("fu-missing")


def test_due_followups_dated_and_undated(registry):
    now = time.time()
    registry.add("past due", due_at=now - 60)
    registry.add("future", due_at=now + 3600)
    registry.add("undated fresh")
    due = registry.due_followups(now_epoch=now)
    assert [d["title"] for d in due] == ["past due"]
    # An undated item older than the stale window surfaces too.
    old = registry.add("undated old")
    old_created = now - 49 * 3600
    registry._cache[3]["created_at"] = old_created  # age it in place
    due2 = registry.due_followups(now_epoch=now)
    assert "undated old" in [d["title"] for d in due2]
    assert "undated fresh" not in [d["title"] for d in due2]


def test_registry_survives_reopen(tmp_path):
    path = str(tmp_path / "registry.json")
    r1 = FollowUpRegistry(store_path=path, memora_client=FakeMemora())
    rec = r1.add("Persist across restarts")
    r2 = FollowUpRegistry(store_path=path, memora_client=None)
    assert r2.get(rec["id"])["title"] == "Persist across restarts"


def test_tools_round_trip(tmp_path, monkeypatch):
    import friday.proactive.followup_registry as fr
    from friday.tools.builtin.followup_tools import (
        FollowUpAddTool,
        FollowUpCompleteTool,
        FollowUpListTool,
    )

    fake = FakeMemora()
    monkeypatch.setattr(
        fr,
        "default_registry",
        lambda: FollowUpRegistry(store_path=str(tmp_path / "t.json"), memora_client=fake),
    )
    add = FollowUpAddTool().execute(title="Chase the refund", due_in_hours=1)
    assert not add.is_error
    fid = add.metadata["followup_id"]
    listed = FollowUpListTool().execute()
    assert "Chase the refund" in listed.content
    done = FollowUpCompleteTool().execute(followup_id=fid)
    assert not done.is_error
    assert FollowUpListTool().execute().content == "No open follow-ups."
    bad = FollowUpAddTool().execute(title="")
    assert bad.is_error
