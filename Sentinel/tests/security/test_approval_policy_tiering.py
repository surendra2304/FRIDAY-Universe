"""Risk-tiered approval policy (TASK-SEN-019).

Owner decision (2026-11-18): Sentinel auto-approves low-risk items itself
and prompts the owner only for high-risk ones. These tests pin:

- the classifier matrix: every hard bound (live money, owner-data
  deletion, credential changes, Sentinel policy changes) prompts even
  when the caller claims LOW; LOW + read-only/internal/attested-
  reversible auto-approves; GUARDED (the historical default), MEDIUM,
  HIGH, CRITICAL and unknown levels prompt — a caller is never downgraded;
- dispatcher integration: an auto-approval is APPROVED immediately, its
  waiter is released, NO owner notification is dispatched, and the
  auto-approval is written to the tamper-evident audit ledger; if the
  ledger write fails, the item falls back to the owner prompt
  (fail-closed: no ledger entry, no auto-approval);
- a HIGH item still dispatches to the owner through the shared
  SEN-006/SEN-008 Telegram channel;
- pending-queue persistence (SENTINEL_PENDING_APPROVALS_PATH): a pending
  item survives a dispatcher restart with its approve/deny token intact,
  an expired pending restores as EXPIRED, and a decided item restores as
  a record so its status still resolves;
- the SEN-019 hardening follow-up: (b1) bare credential nouns (a lone
  token / secret, plurals, compounds, details-smuggled) prompt as
  credential_change at LOW, with whole-token precision pins so ordinary
  actions (tokenizer, secretary, key metrics, usage-qualified token
  metering in the action) still auto-approve; (b2) non-string
  action / risk_level / details inputs return the fail-closed
  OWNER_PROMPT decision instead of raising.
"""

import asyncio
import json
import time
import urllib.request

import pytest

import sentinel.gatekeeper.approval_dispatcher as dispatcher_module
from sentinel.audit.audit_logger import AuditLogger
from sentinel.gatekeeper.approval_dispatcher import (
    ApprovalDispatcher,
    approval_dispatcher,
)
from sentinel.gatekeeper.approval_policy import ApprovalTier, classify_approval

CRED_NAMES = (
    "TELEGRAM_BOT_TOKEN",
    "SENTINEL_TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "SENTINEL_TELEGRAM_CHAT_ID",
    "DISCORD_WEBHOOK_URL",
    "SENTINEL_DISCORD_WEBHOOK_URL",
)


@pytest.fixture(autouse=True)
def _clean_channel_state(monkeypatch):
    """Mirror the SEN-006 fixture: no channel credentials unless a test
    configures them, and no queue persistence unless a test opts in."""
    for name in CRED_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("SENTINEL_ENV_FILE", raising=False)
    monkeypatch.delenv("SENTINEL_PENDING_APPROVALS_PATH", raising=False)
    dispatcher_module._FILE_ENV_CACHE = None
    yield
    dispatcher_module._FILE_ENV_CACHE = None


def _fresh_dispatcher():
    """Simulate a process restart: drop the singleton so the next
    ApprovalDispatcher() re-initialises its in-RAM state."""
    ApprovalDispatcher._instance = None
    return ApprovalDispatcher()


@pytest.fixture
def _restore_singleton():
    saved = ApprovalDispatcher._instance
    yield
    ApprovalDispatcher._instance = saved


# ----------------------------------------------------------------------
# Classifier matrix
# ----------------------------------------------------------------------

@pytest.mark.parametrize(
    "action,details,category",
    [
        # Live money — the owner's retained line, always his decision.
        ("execute live trade EURUSD", {}, "live_money"),
        ("live order placement", {"symbol": "BTCUSDT"}, "live_money"),
        ("withdraw funds to bank", {}, "live_money"),
        ("process payout", {}, "live_money"),
        # Deletion — irreversible, target unprovable, always prompts.
        ("delete old report file", {}, "owner_data_deletion"),
        ("remove stale records", {}, "owner_data_deletion"),
        ("purge cache entries", {}, "owner_data_deletion"),
        # Credentials — change, rotation, or read-out.
        ("rotate api key", {}, "credential_change"),
        ("update bot token", {}, "credential_change"),
        ("read credential store", {}, "credential_change"),
        ("reset owner password", {}, "credential_change"),
        # Sentinel's own policy machinery — never self-approved.
        ("update approval policy thresholds", {}, "sentinel_policy_change"),
        ("disable kill switch", {}, "sentinel_policy_change"),
        ("enable auto-approve for deployments", {}, "sentinel_policy_change"),
        # Risk smuggled in the details payload is still caught.
        ("status check", {"note": "then delete the archive"}, "owner_data_deletion"),
        ("status check", {"note": "rotate the api key afterwards"}, "credential_change"),
    ],
)
def test_hard_bounds_prompt_even_at_low(action, details, category):
    result = classify_approval(
        agent_name="STRATEX", action=action, risk_level="LOW", details=details
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.hard_bound is True
    assert result.category == category


@pytest.mark.parametrize(
    "action,details,category",
    [
        ("check fleet health", {}, "read_only"),
        ("read positions summary", {}, "read_only"),
        ("list pending tasks", {}, "read_only"),
        ("scan open ports", {}, "read_only"),
        ("fetch market data snapshot", {}, "read_only"),
        ("heartbeat report", {}, "internal"),
        ("metrics collection sweep", {}, "internal"),
        ("restart preview renderer", {"reversible": True}, "reversible_attested"),
    ],
)
def test_low_risk_class_auto_approves(action, details, category):
    result = classify_approval(
        agent_name="FRIDAY", action=action, risk_level="LOW", details=details
    )
    assert result.tier is ApprovalTier.AUTO_APPROVE
    assert result.category == category


@pytest.mark.parametrize("risk_level", ["GUARDED", "MEDIUM", "HIGH", "CRITICAL", "WHATEVER", ""])
def test_non_low_claims_always_prompt(risk_level):
    result = classify_approval(
        agent_name="FRIDAY", action="check fleet health",
        risk_level=risk_level, details={},
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == "caller_risk_not_low"


@pytest.mark.parametrize(
    "action,details",
    [
        ("deploy new build", {}),               # write action, no attestation
        ("restart the voice worker", {}),       # reversible in fact, unattested -> prompt
        ("check then deploy the fix", {}),      # write verb defeats the read verb
        ("", {}),                               # unparseable
    ],
)
def test_low_claim_with_unlisted_action_prompts(action, details):
    result = classify_approval(
        agent_name="FORGE", action=action, risk_level="LOW", details=details
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == "action_not_low_risk"


# ----------------------------------------------------------------------
# Dispatcher integration: auto-approval + audit ledger
# ----------------------------------------------------------------------

def _tmp_audit_logger(tmp_path) -> AuditLogger:
    return AuditLogger(
        log_path=str(tmp_path / "audit.jsonl"),
        signing_key="sen019-test-signing-key-32chars!!",
    )


def test_auto_approval_writes_audit_and_notifies_nobody(monkeypatch, tmp_path):
    dispatcher = _fresh_dispatcher()
    audit = _tmp_audit_logger(tmp_path)
    dispatcher._audit_logger = audit

    def fail_urlopen(req, timeout=None):
        raise AssertionError("no owner notification may be sent for an auto-approval")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    pending = dispatcher.submit_approval(
        agent_name="FRIDAY",
        action="check fleet health",
        details={"scope": "all agents"},
        risk_level="LOW",
    )
    assert pending.status.value == "APPROVED"
    assert pending.policy_tier == "AUTO_APPROVE"
    assert pending.policy_category == "read_only"
    assert "Auto-approved by Sentinel approval policy" in (pending.decision_reason or "")
    # The waiter is released immediately with an approval.
    assert asyncio.run(dispatcher.wait_for_decision(pending.token, timeout_sec=1.0)) is True
    # The ledger carries exactly the auto-approval, chain intact, no token.
    assert audit.entry_count() == 1
    assert audit.verify_integrity() is True
    line = (tmp_path / "audit.jsonl").read_text(encoding="utf-8").strip()
    entry = json.loads(line)
    assert entry["event_type"] == "APPROVAL_AUTO_APPROVED"
    assert entry["actor"] == "sentinel-approval-policy"
    assert entry["decision"] == "AUTO_APPROVED"
    assert entry["details"]["request_id"] == pending.request_id
    assert entry["details"]["policy_category"] == "read_only"
    assert pending.token not in line


def test_auto_approval_falls_back_to_prompt_when_audit_unavailable(monkeypatch):
    dispatcher = _fresh_dispatcher()

    class _BrokenAudit:
        def log_event(self, **kwargs):
            raise RuntimeError("ledger unavailable")

    dispatcher._audit_logger = _BrokenAudit()
    pending = dispatcher.submit_approval(
        agent_name="FRIDAY",
        action="check fleet health",
        details={},
        risk_level="LOW",
    )
    # Fail-closed: no ledger entry, no auto-approval — the owner is asked.
    assert pending.status.value == "PENDING"
    assert pending.policy_tier == "OWNER_PROMPT"
    assert pending.policy_category == "read_only"


def test_high_risk_prompts_via_shared_telegram_channel(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "TELEGRAM_BOT_TOKEN=file-token\nTELEGRAM_CHAT_ID=file-chat\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dispatcher_module, "_env_file_candidates", lambda: [env_file])
    sent = []

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        sent.append(req)
        return _Resp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    pending = approval_dispatcher.submit_approval(
        agent_name="STRATEX",
        action="execute live trade EURUSD",
        details={"symbol": "EURUSD"},
        risk_level="LOW",  # even a LOW claim cannot move a hard bound
    )
    assert pending.status.value == "PENDING"
    assert pending.policy_tier == "OWNER_PROMPT"
    assert pending.policy_category == "live_money"
    assert len(sent) == 1
    assert sent[0].full_url == "https://api.telegram.org/botfile-token/sendMessage"
    payload = json.loads(sent[0].data.decode("utf-8"))
    assert payload["chat_id"] == "file-chat"
    assert "GUARDED ACTION APPROVAL" in payload["text"]


def test_guarded_default_behaves_as_before(monkeypatch):
    def fail_urlopen(req, timeout=None):
        raise AssertionError("unconfigured channel must not be called")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)
    pending = approval_dispatcher.submit_approval(
        agent_name="TEST",
        action="check fleet health",
        details={},
    )
    assert pending.status.value == "PENDING"
    assert pending.policy_tier == "OWNER_PROMPT"
    assert pending.policy_category == "caller_risk_not_low"


# ----------------------------------------------------------------------
# Pending-queue persistence
# ----------------------------------------------------------------------

def test_pending_survives_restart_and_decide_still_works(monkeypatch, tmp_path, _restore_singleton):
    queue_file = tmp_path / "pending_approvals.json"
    monkeypatch.setenv("SENTINEL_PENDING_APPROVALS_PATH", str(queue_file))

    first = _fresh_dispatcher()
    pending = first.submit_approval(
        agent_name="FORGE",
        action="deploy new build",
        details={"build": "g5"},
        risk_level="GUARDED",
    )
    assert pending.status.value == "PENDING"
    assert queue_file.exists()

    # Restart: a brand-new dispatcher restores the queue from disk.
    second = _fresh_dispatcher()
    restored_list = second.get_pending_list()
    assert [p["token"] for p in restored_list] == [pending.token]
    assert restored_list[0]["policy_category"] == "caller_risk_not_low"

    decided = second.decide(pending.token, approve=True)
    assert decided is not None and decided.status.value == "APPROVED"

    # The decision itself is durable: a third instance sees the record.
    third = _fresh_dispatcher()
    third._ensure_restored()
    record = third._pending.get(pending.token)
    assert record is not None and record.status.value == "APPROVED"
    assert third.get_pending_list() == []


def test_expired_pending_restores_as_expired(monkeypatch, tmp_path, _restore_singleton):
    queue_file = tmp_path / "pending_approvals.json"
    monkeypatch.setenv("SENTINEL_PENDING_APPROVALS_PATH", str(queue_file))

    first = _fresh_dispatcher()
    pending = first.submit_approval(
        agent_name="FORGE",
        action="deploy new build",
        details={},
        risk_level="GUARDED",
        timeout_sec=0.05,
    )
    time.sleep(0.1)
    second = _fresh_dispatcher()
    second._ensure_restored()
    record = second._pending.get(pending.token)
    assert record is not None and record.status.value == "EXPIRED"
    assert second.get_pending_list() == []


def test_no_queue_file_no_persistence(monkeypatch, tmp_path, _restore_singleton):
    # Env unset (autouse fixture): the historical RAM-only behaviour.
    first = _fresh_dispatcher()
    first.submit_approval(
        agent_name="FORGE", action="deploy new build", details={}, risk_level="GUARDED"
    )
    second = _fresh_dispatcher()
    assert second.get_pending_list() == []


# ----------------------------------------------------------------------
# SEN-019 hardening (b1): bare credential nouns
# ----------------------------------------------------------------------
# On the pre-hardening classifier every action below AUTO_APPROVED at
# LOW when it led with a read verb: the credential pass only matched
# exact phrases ("api key", "bot token", "secret key", ...) plus
# "secret" next to a policy-change verb, so a lone "token" / "secret"
# named by a read-only action escaped it entirely.

@pytest.mark.parametrize(
    "action,details",
    [
        ("check token", {}),
        ("read token", {}),
        ("fetch secret", {}),
        ("read secret", {}),
        ("check secrets", {}),
        ("list tokens", {}),
        ("status token", {}),
        ("check token expiry", {}),
        ("rotate token", {}),
        ("token", {}),
        ("secret", {}),
        # Underscore compounds tokenise apart and are caught by the
        # bare-noun pass; single-token compounds are caught as compounds.
        ("read access_token", {}),
        ("read privatekey", {}),
        ("read access key", {}),
        ("fetch passphrase", {}),
        # A reversible attestation never excuses a hard bound.
        ("check token", {"reversible": True}),
        # Bare nouns smuggled in the details payload.
        ("status check", {"note": "token"}),
        ("status check", {"target": "secret"}),
        ("status check", {"token": "abc123"}),
        # The usage exception is action-only: it never applies to the
        # details payload, even with the qualifier word present.
        ("status check", {"note": "token usage"}),
        # ... and a usage-qualified action cannot launder a secret in
        # the details.
        ("check token usage", {"note": "also read the secret"}),
        # Secret is never usage-excused.
        ("check secret usage", {}),
    ],
)
def test_bare_credential_nouns_prompt_at_low(action, details):
    result = classify_approval(
        agent_name="FRIDAY", action=action, risk_level="LOW", details=details
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.hard_bound is True
    assert result.category == "credential_change"


@pytest.mark.parametrize(
    "action,category",
    [
        # Whole-token matching: lookalikes are different tokens, not
        # credential nouns — substring matching would false-positive
        # every one of these ordinary actions.
        ("check tokenizer health", "read_only"),
        ("scan tokenization pipeline", "read_only"),
        ("fetch secretary report", "read_only"),
        ("read keyboard layout", "read_only"),
        # A bare "key" is an ordinary adjective, deliberately not a
        # credential noun on its own (credential uses are phrases).
        ("list key metrics", "read_only"),
        # Usage-qualified token metering in the ACTION: LLM token
        # usage is an ordinary fleet measurement, not credential
        # material. Every token occurrence must be qualified.
        ("check token usage metrics", "read_only"),
        ("count tokens used", "read_only"),
        ("measure token consumption", "read_only"),
        ("report token counts by agent", "read_only"),
    ],
)
def test_bare_noun_precision_ordinary_actions_still_auto_approve(action, category):
    result = classify_approval(
        agent_name="FRIDAY", action=action, risk_level="LOW", details={}
    )
    assert result.tier is ApprovalTier.AUTO_APPROVE
    assert result.category == category


def test_bare_token_dispatcher_does_not_auto_approve(monkeypatch, tmp_path):
    """Dispatcher-level pin for (b1): a LOW 'check token' submission
    must stay PENDING for the owner — pre-hardening it was APPROVED
    with no prompt — and no audit-ledger auto-approval is written."""
    dispatcher = _fresh_dispatcher()
    audit = _tmp_audit_logger(tmp_path)
    dispatcher._audit_logger = audit
    pending = dispatcher.submit_approval(
        agent_name="FRIDAY",
        action="check token",
        details={},
        risk_level="LOW",
    )
    assert pending.status.value == "PENDING"
    assert pending.policy_tier == "OWNER_PROMPT"
    assert pending.policy_category == "credential_change"
    assert audit.entry_count() == 0


# ----------------------------------------------------------------------
# SEN-019 hardening (b2): non-string inputs never raise
# ----------------------------------------------------------------------
# Pre-hardening, classify_approval raised on these shapes despite its
# "never raises" contract (action=123 -> TypeError in the haystack
# join; risk_level=123 -> AttributeError on .strip) — submissions were
# fail-closed only because the exception aborted them. Now they return
# the fail-closed OWNER_PROMPT decision (category "invalid_input").

@pytest.mark.parametrize(
    "action",
    [None, 123, 12.5, True, b"check fleet health", ["check", "health"], {"a": 1}, ("check",)],
)
def test_non_string_action_prompts_instead_of_raising(action):
    result = classify_approval(
        agent_name="FRIDAY", action=action, risk_level="LOW", details={}
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == "invalid_input"
    assert result.auto_approve is False


@pytest.mark.parametrize(
    "risk_level",
    [None, 123, 1.0, b"LOW", ["LOW"], {"level": "LOW"}],
)
def test_non_string_risk_level_prompts_instead_of_raising(risk_level):
    result = classify_approval(
        agent_name="FRIDAY", action="check fleet health",
        risk_level=risk_level, details={},
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == "invalid_input"
    assert result.auto_approve is False


def test_both_inputs_non_string_prompt_instead_of_raising():
    result = classify_approval(
        agent_name="FRIDAY", action=123, risk_level=456, details={}
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == "invalid_input"


@pytest.mark.parametrize(
    "details,category,hard_bound",
    [
        # A non-mapping payload the policy cannot structurally inspect
        # prompts as invalid input...
        (123, "invalid_input", False),
        ("plain note", "invalid_input", False),
        # ...unless a hard bound still fires over its text first: the
        # more specific, safer verdict wins.
        ("token", "credential_change", True),
        (["delete", "the", "archive"], "owner_data_deletion", True),
    ],
)
def test_non_dict_details_never_raise_and_never_auto_approve(details, category, hard_bound):
    result = classify_approval(
        agent_name="FRIDAY", action="check fleet health",
        risk_level="LOW", details=details,
    )
    assert result.tier is ApprovalTier.OWNER_PROMPT
    assert result.category == category
    assert result.hard_bound is hard_bound


def test_non_string_agent_name_still_classifies():
    # agent_name is deliberately unused by the policy (a trusted name
    # must never make an action auto-approvable); an odd value there
    # neither raises nor changes the verdict.
    result = classify_approval(
        agent_name=123, action="check fleet health", risk_level="LOW", details={}
    )
    assert result.tier is ApprovalTier.AUTO_APPROVE
    assert result.category == "read_only"
