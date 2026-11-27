"""TASK-FRD-062 — CRM workspace surface tests (hermetic).

Store tests run against an in-memory SQLite engine (the sanctioned
test-only backend: ``CrmStore(engine=...)`` is gated by
``ephemeral_backend_allowed``); tool tests monkeypatch
``friday.crm.store.default_store`` and
``friday.proactive.followup_registry.default_registry`` the way the
follow-up suite does. No Oracle DSN, no network, no real Memora client.
"""

from __future__ import annotations

import time

import pytest
from sqlalchemy import create_engine

from friday.core import oracle
from friday.core.types import SafetyLevel
from friday.crm.store import DEAL_STAGES, CrmStore
from friday.proactive.followup_registry import FollowUpRegistry
from friday.tools.builtin.crm_tools import (
    CrmContactAddTool,
    CrmContactGetTool,
    CrmContactListTool,
    CrmDealAddTool,
    CrmDealStageTool,
    CrmFollowupsDueTool,
)


@pytest.fixture()
def store():
    engine = create_engine("sqlite://")
    return CrmStore(engine=engine)


@pytest.fixture()
def registry(tmp_path):
    return FollowUpRegistry(store_path=str(tmp_path / "registry.json"), memora_client=None)


@pytest.fixture()
def wired(monkeypatch, store, registry):
    """Tools bound to the test store + test registry."""
    import friday.crm.store as store_mod
    import friday.proactive.followup_registry as fr

    monkeypatch.setattr(store_mod, "default_store", lambda: store)
    monkeypatch.setattr(fr, "default_registry", lambda: registry)
    return store, registry


# ---------------------------------------------------------------------------
# store: contacts
# ---------------------------------------------------------------------------

def test_contact_add_get_round_trip(store):
    contact = store.add_contact(
        "Asha Verma", email="asha@example.com", company="CometWorks", source="voice"
    )
    assert contact["name"] == "Asha Verma"
    assert contact["email"] == "asha@example.com"
    assert contact["company"] == "CometWorks"
    assert contact["source"] == "voice"
    assert contact["unreachable"] is False
    assert store.get_contact(contact["id"])["name"] == "Asha Verma"


def test_contact_without_email_or_phone_is_flagged_unreachable(store):
    contact = store.add_contact("No Channels")
    assert contact["email"] is None
    assert contact["phone"] is None
    assert contact["unreachable"] is True


def test_contact_requires_name(store):
    with pytest.raises(ValueError):
        store.add_contact("   ")


def test_duplicate_email_rejected(store):
    store.add_contact("First", email="dup@example.com")
    with pytest.raises(ValueError, match="already exists"):
        store.add_contact("Second", email="DUP@example.com")  # case-insensitive


def test_find_contacts_fragment_and_company(store):
    store.add_contact("Asha Verma", company="CometWorks")
    store.add_contact("Ashok Rao", company="Acme")
    store.add_contact("Meera Nair", company="CometWorks")
    assert [c["name"] for c in store.find_contacts("ash")] == ["Asha Verma", "Ashok Rao"]
    assert [c["name"] for c in store.find_contacts(company="cometworks")] == [
        "Asha Verma",
        "Meera Nair",
    ]
    assert store.find_contacts("zzz") == []


def test_resolve_contact_exact_id_and_ambiguous(store):
    a = store.add_contact("Asha Verma")
    assert store.resolve_contact(a["id"])["id"] == a["id"]
    assert store.resolve_contact("asha")["id"] == a["id"]
    store.add_contact("Asha Kapoor")
    with pytest.raises(ValueError, match="matches 2 contacts"):
        store.resolve_contact("asha")
    with pytest.raises(KeyError, match="no contact matches"):
        store.resolve_contact("nobody here")


# ---------------------------------------------------------------------------
# store: deals
# ---------------------------------------------------------------------------

def test_deal_add_requires_existing_contact(store):
    with pytest.raises(KeyError, match="no contact with id"):
        store.add_deal("missing-id", "Some deal")


def test_deal_defaults_to_lead_and_records_creation_history(store):
    contact = store.add_contact("Asha Verma")
    deal = store.add_deal(contact["id"], "Website copy package", value_text="$500")
    assert deal["stage"] == "lead"
    assert deal["value_text"] == "$500"
    assert deal["stage_changed_at"] == deal["created_at"]
    assert deal["stage_history"] == [
        {"from": None, "to": "lead", "at": deal["created_at"]}
    ]


def test_deal_rejects_invalid_stage(store):
    contact = store.add_contact("Asha Verma")
    with pytest.raises(ValueError, match="valid stages"):
        store.add_deal(contact["id"], "Bad stage deal", stage="closed-won")


def test_deal_stage_move_records_history_and_timestamp(store):
    contact = store.add_contact("Asha Verma")
    deal = store.add_deal(contact["id"], "Website copy package")
    moved = store.set_deal_stage(deal["id"], "proposal")
    assert moved["previous_stage"] == "lead"
    assert moved["stage"] == "proposal"
    assert moved["stage_changed_at"] >= deal["stage_changed_at"]
    assert moved["stage_history"][-1] == {
        "from": "lead",
        "to": "proposal",
        "at": moved["stage_changed_at"],
    }
    # Full walk through the pipeline keeps every move.
    for stage in ("negotiation", "won"):
        moved = store.set_deal_stage(deal["id"], stage)
    assert [h["to"] for h in moved["stage_history"]] == [
        "lead",
        "proposal",
        "negotiation",
        "won",
    ]


def test_deal_stage_move_to_same_stage_is_a_noop(store):
    contact = store.add_contact("Asha Verma")
    deal = store.add_deal(contact["id"], "Package")
    same = store.set_deal_stage(deal["id"], "lead")
    assert same.get("stage_unchanged") is True
    assert len(same["stage_history"]) == 1  # no history row written


def test_deal_stage_rejects_invalid_stage_and_unknown_deal(store):
    contact = store.add_contact("Asha Verma")
    deal = store.add_deal(contact["id"], "Package")
    with pytest.raises(ValueError, match="valid stages"):
        store.set_deal_stage(deal["id"], "shipped")
    with pytest.raises(KeyError, match="no deal with id"):
        store.set_deal_stage("missing-id", "won")


def test_list_deals_filters(store):
    c1 = store.add_contact("Asha Verma")
    c2 = store.add_contact("Ashok Rao")
    store.add_deal(c1["id"], "Deal one")
    store.add_deal(c1["id"], "Deal two", stage="proposal")
    store.add_deal(c2["id"], "Deal three")
    assert [d["title"] for d in store.list_deals(contact_id=c1["id"])] == [
        "Deal one",
        "Deal two",
    ]
    assert [d["title"] for d in store.list_deals(stage="proposal")] == ["Deal two"]
    assert store.resolve_deal("deal two")["title"] == "Deal two"
    with pytest.raises(KeyError, match="no deal matches"):
        store.resolve_deal("no such deal")


def test_tables_are_declared_in_oracle_metadata():
    assert "contacts" in oracle.metadata.tables
    assert "deals" in oracle.metadata.tables
    assert set(DEAL_STAGES) == {
        "lead",
        "contacted",
        "proposal",
        "negotiation",
        "won",
        "lost",
    }


# ---------------------------------------------------------------------------
# registry: CRM link
# ---------------------------------------------------------------------------

def test_registry_crm_link_passthrough_and_filter(registry):
    linked = registry.add(
        "Chase the invoice", contact_id="c-1", deal_id="d-1", due_at=time.time() - 60
    )
    registry.add("Unlinked", due_at=time.time() - 60)
    assert linked["contact_id"] == "c-1"
    assert linked["deal_id"] == "d-1"
    assert [r["title"] for r in registry.list(contact_id="c-1")] == ["Chase the invoice"]
    assert [r["title"] for r in registry.due_followups(contact_id="c-1")] == [
        "Chase the invoice"
    ]
    assert [r["title"] for r in registry.due_followups(deal_id="d-1")] == [
        "Chase the invoice"
    ]
    assert [r["title"] for r in registry.due_followups(contact_id="c-2")] == []


# ---------------------------------------------------------------------------
# tools: round trip through the acceptance script
# ---------------------------------------------------------------------------

def test_tools_are_safe_so_voice_can_offer_them():
    # The Gemini Live session only offers SafetyLevel.SAFE tools; the whole
    # CRM surface must be voice-visible per the board acceptance.
    for cls in (
        CrmContactAddTool,
        CrmContactGetTool,
        CrmContactListTool,
        CrmDealAddTool,
        CrmDealStageTool,
        CrmFollowupsDueTool,
    ):
        assert cls.safety_level is SafetyLevel.SAFE, cls.name


def test_acceptance_script_round_trip(wired):
    store, registry = wired
    # (1) "Add a contact" -> spoken confirmation with the id read back.
    added = CrmContactAddTool().execute(name="Asha Verma", email="asha@example.com")
    assert not added.is_error
    contact_id = added.metadata["contact_id"]
    assert contact_id in added.content
    # (2) Open a deal, then move it to proposal -> old -> new stage spoken.
    deal = CrmDealAddTool().execute(
        contact_ref="Asha", title="Website copy package", value_text="$500"
    )
    assert not deal.is_error
    assert "[stage lead]" in deal.content
    moved = CrmDealStageTool().execute(deal_ref="Website copy", new_stage="proposal")
    assert not moved.is_error
    assert "lead to proposal" in moved.content
    # (3) A follow-up linked to the contact, due now, reads back with the name.
    registry.add(
        "Send the draft", contact_id=contact_id, due_at=time.time() - 10
    )
    due = CrmFollowupsDueTool().execute()
    assert not due.is_error
    assert "Send the draft" in due.content
    assert "Asha Verma" in due.content
    due_for_contact = CrmFollowupsDueTool().execute(contact_ref="Asha")
    assert "Send the draft" in due_for_contact.content


def test_tools_fail_closed_on_unknown_and_ambiguous(wired):
    store, registry = wired
    # Unknown contact name is reported, never guessed.
    assert CrmContactGetTool().execute(contact_ref="Ghost Person").is_error
    assert CrmDealAddTool().execute(contact_ref="Ghost", title="X").is_error
    assert CrmFollowupsDueTool().execute(contact_ref="Ghost").is_error
    # Invalid stage is rejected with the valid list.
    store.add_contact("Asha Verma")
    bad_stage = CrmDealAddTool().execute(
        contact_ref="Asha", title="Package", stage="shipped"
    )
    assert bad_stage.is_error
    assert "lead" in bad_stage.content and "won" in bad_stage.content
    # Ambiguous name is reported, not resolved to the first match.
    store.add_contact("Asha Kapoor")
    ambiguous = CrmContactGetTool().execute(contact_ref="Asha")
    assert ambiguous.is_error
    assert "matches 2 contacts" in ambiguous.content
    # Unknown deal is reported.
    assert CrmDealStageTool().execute(deal_ref="No such deal", new_stage="won").is_error
    # Moving to the current stage reports it instead of failing.
    deal = CrmDealAddTool().execute(contact_ref="Asha Verma", title="Solo deal")
    assert not deal.is_error
    same = CrmDealStageTool().execute(deal_ref="Solo deal", new_stage="lead")
    assert not same.is_error
    assert "already at stage lead" in same.content


def test_contact_list_and_get_show_deals(wired):
    store, registry = wired
    contact = store.add_contact("Asha Verma", company="CometWorks")
    store.add_deal(contact["id"], "Website copy package", stage="proposal")
    listed = CrmContactListTool().execute(company="CometWorks")
    assert "Asha Verma" in listed.content
    card = CrmContactGetTool().execute(contact_ref=contact["id"])
    assert "Website copy package [proposal]" in card.content
    assert CrmContactListTool().execute(query="nobody").content == "No contacts match."
    assert CrmFollowupsDueTool().execute().content == "No follow-ups are due."
