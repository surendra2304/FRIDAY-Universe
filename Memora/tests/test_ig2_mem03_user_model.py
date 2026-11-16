"""
TASK-IG2-MEM-03 — Hermes structured user-model profile.

Contracts locked here:
- the profile starts absent and says so (no invented fields);
- update_field validates kind/field/value, versions the profile
  record, supersedes the previous version, and reports the previous
  value it replaced; history keeps the replaced value;
- an owner correction lands as a standing_rule at confidence 1.0;
- consult returns the current entry or an explicit absence;
- render_profile puts standing rules first and is honest when empty;
- the profile record is a PREFERENCE record findable as one record —
  get_profile always reads the newest version only.
"""
from core.identity.service import IdentityService
from core.memory.user_model_service import UserModelService
from storage.relational.models import MemoryRecord, MemoryType


def _setup(test_db):
    IdentityService.register_agent(test_db, "friday")


def test_profile_starts_absent_and_honest(test_db):
    _setup(test_db)
    profile = UserModelService.get_profile(test_db, actor_name="friday")
    assert profile["exists"] is False
    assert profile["fields"] == {}
    assert UserModelService.consult(test_db, actor_name="friday", field="timezone")["found"] is False
    assert "nothing assumed" in UserModelService.render_profile(test_db, actor_name="friday")


def test_update_field_creates_and_versions_profile(test_db):
    _setup(test_db)
    first = UserModelService.update_field(
        test_db, actor_name="friday", field="timezone", value="Asia/Kolkata",
        kind="fact", source_ref="owner statement 2026-11-14",
    )
    assert first["updated"] is True and first["version"] == 1 and first["previous_value"] is None

    second = UserModelService.update_field(
        test_db, actor_name="friday", field="briefing_time", value="08:50", kind="preference",
    )
    assert second["version"] == 2

    profile = UserModelService.get_profile(test_db, actor_name="friday")
    assert profile["version"] == 2
    assert profile["fields"]["timezone"]["value"] == "Asia/Kolkata"
    assert profile["fields"]["briefing_time"]["value"] == "08:50"

    record = test_db.query(MemoryRecord).filter(MemoryRecord.id == profile["record_id"]).one()
    assert record.memory_type == MemoryType.PREFERENCE
    assert "briefing_time: 08:50" in record.content_text


def test_update_replaces_value_and_keeps_history(test_db):
    _setup(test_db)
    UserModelService.update_field(
        test_db, actor_name="friday", field="briefing_time", value="09:30", kind="preference",
    )
    changed = UserModelService.update_field(
        test_db, actor_name="friday", field="briefing_time", value="08:50", kind="preference",
    )
    assert changed["changed"] is True
    assert changed["previous_value"] == "09:30"
    entry = UserModelService.consult(test_db, actor_name="friday", field="briefing_time")
    assert entry["found"] is True and entry["value"] == "08:50"
    profile = UserModelService.get_profile(test_db, actor_name="friday")
    history = profile["fields"]["briefing_time"]["history"]
    assert history and history[-1]["value"] == "09:30"
    assert profile["fields"]["briefing_time"]["update_count"] == 2


def test_correction_is_standing_rule_at_full_confidence(test_db):
    _setup(test_db)
    out = UserModelService.learn_from_correction(
        test_db, actor_name="friday", field="spend_policy",
        value="free tier only — no paid services", source_ref="owner directive 2026-11-15",
    )
    assert out["updated"] is True
    entry = UserModelService.consult(test_db, actor_name="friday", field="spend_policy")
    assert entry["kind"] == "standing_rule"
    assert entry["confidence"] == 1.0


def test_validation_rejects_unknown_kind_and_empty_values(test_db):
    _setup(test_db)
    bad_kind = UserModelService.update_field(
        test_db, actor_name="friday", field="x", value="y", kind="guess",
    )
    assert bad_kind["updated"] is False and bad_kind["reason"].startswith("unknown_kind")
    empty = UserModelService.update_field(
        test_db, actor_name="friday", field="x", value="  ", kind="fact",
    )
    assert empty["updated"] is False and empty["reason"] == "empty_value"
    assert UserModelService.get_profile(test_db, actor_name="friday")["exists"] is False


def test_render_puts_standing_rules_first(test_db):
    _setup(test_db)
    UserModelService.update_field(
        test_db, actor_name="friday", field="briefing_time", value="08:50", kind="preference",
    )
    UserModelService.learn_from_correction(
        test_db, actor_name="friday", field="voice_priority", value="speed first — no long silences",
    )
    rendered = UserModelService.render_profile(test_db, actor_name="friday")
    assert rendered.index("voice_priority") < rendered.index("briefing_time")
    assert "standing_rule" in rendered
