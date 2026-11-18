"""Sentinel risk-tiered approval policy (TASK-SEN-019).

Owner decision (2026-11-18): Sentinel auto-approves low-risk items itself
and prompts the owner only for high-risk ones. This module is the
classifier behind that decision. It is pure (no I/O, no imports beyond the
standard library) and fail-closed: anything it does not positively
recognise as low-risk is routed to the owner.

Taxonomy grounding — the tiers are built from the approval vocabulary that
already exists in this codebase, not invented here:

- The gatekeeper dispatcher's guarded categories (see
  ``approval_dispatcher``'s module docstring): live trade execution,
  system modifications / code deployments, security overrides / killswitch
  triggers, sensitive external operations. Every submission used to prompt
  the human; ``risk_level`` is a caller-supplied string defaulting to
  ``"GUARDED"``.
- The PolicyEngine's impact ordering (``sentinel.core.policy.engine``):
  NONE < LOW < MEDIUM < HIGH < CRITICAL. A caller-supplied level is only
  ever taken at face value or escalated by this policy — never downgraded:
  GUARDED / MEDIUM / HIGH / CRITICAL / unknown all prompt.

Hard bounds (checked FIRST, over the action text and the details payload,
so risk cannot be smuggled past the classifier in the details):

- ``live_money`` — live trade/order execution or real-money movement.
  Sentinel can never auto-approve these (owner's retained line: real
  money is always his explicit decision).
- ``owner_data_deletion`` — any destructive verb (delete / remove /
  purge / wipe / erase / destroy / drop / truncate). Deletion is
  irreversible by definition, and the dispatcher cannot prove a deletion
  target is not owner data, so every deletion prompts.
- ``credential_change`` — credential / password / secret / API-key /
  signing-key material being changed, rotated, or read out.
- ``sentinel_policy_change`` — anything that would alter the approval
  machinery itself (approval policy, auto-approve configuration, kill
  switch). Sentinel can never approve a change to its own policy.

Auto-approve requires ALL of the following:

1. The caller's ``risk_level`` normalises to a low claim
   (LOW / NONE / MINIMAL / ROUTINE).
2. No hard-bound pattern anywhere in the action or details.
3. The action positively matches the low-risk class:
   - read-only: a leading read verb (read / get / list / check / status /
     health / scan / audit / report / fetch / query / inspect / monitor /
     view / describe / ping / verify / validate / show / lookup / search /
     watch / observe / measure / count) and no write verb anywhere else
     in the action; or
   - internal: a leading internal-housekeeping token (heartbeat /
     metrics / telemetry / internal / housekeeping / upkeep); or
   - reversible: the caller explicitly attests ``details["reversible"]
     is True`` (attestation alone is never enough — the hard-bound and
     destructive checks above still apply, and the caller's risk claim
     must still be low).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

try:
    from enum import StrEnum
except ImportError:  # Python < 3.11: behaviour-identical fallback
    from enum import Enum as _StrEnumBase

    class StrEnum(str, _StrEnumBase):
        """Stand-in for enum.StrEnum (3.11+) on older interpreters."""

        __str__ = str.__str__
        __format__ = str.__format__

        @staticmethod
        def _generate_next_value_(name, start, count, last_values):
            return name.lower()


class ApprovalTier(StrEnum):
    AUTO_APPROVE = "AUTO_APPROVE"
    OWNER_PROMPT = "OWNER_PROMPT"


@dataclass(frozen=True)
class ApprovalClassification:
    tier: ApprovalTier
    category: str
    reason: str
    hard_bound: bool = False

    @property
    def auto_approve(self) -> bool:
        return self.tier is ApprovalTier.AUTO_APPROVE


# --- Caller risk claims -------------------------------------------------
# Only an explicit low claim can ever be auto-approved. GUARDED (the
# dispatcher's historical default), MEDIUM, HIGH, CRITICAL and anything
# unrecognised prompt the owner: the policy never downgrades a caller.
_LOW_RISK_CLAIMS = frozenset({"LOW", "NONE", "MINIMAL", "ROUTINE"})

# --- Low-risk action class ----------------------------------------------
_READ_ONLY_VERBS = frozenset({
    "read", "get", "list", "check", "status", "health", "scan", "audit",
    "report", "fetch", "query", "inspect", "monitor", "view", "describe",
    "ping", "verify", "validate", "show", "lookup", "search", "watch",
    "observe", "measure", "count",
})
_INTERNAL_LEADERS = frozenset({
    "heartbeat", "metrics", "telemetry", "internal", "housekeeping", "upkeep",
})
# A write verb anywhere after a read verb ("check then deploy") defeats
# the read-only classification.
_WRITE_VERBS = frozenset({
    "write", "send", "post", "publish", "upload", "create", "update",
    "modify", "deploy", "install", "start", "stop", "restart", "execute",
    "run", "apply", "set", "enable", "disable", "configure", "grant",
    "revoke", "approve", "deny", "trigger", "launch", "build", "release",
})

# --- Hard bounds ----------------------------------------------------------
_DESTRUCTIVE_TOKENS = frozenset({
    "delete", "deletes", "deleted", "deletion", "remove", "removes",
    "removal", "purge", "wipe", "erase", "destroy", "drop", "truncate",
    "shred",
})
_LIVE_TRADE_TOKENS = frozenset({
    "trade", "trades", "trading", "order", "orders", "execution",
    "execute", "buy", "sell",
})
_MONEY_MOVEMENT_TOKENS = frozenset({
    "withdraw", "withdrawal", "withdrawals", "payout", "payouts",
})
_CREDENTIAL_PHRASES = (
    "credential", "password", "passwd", "api key", "api_key", "apikey",
    "access token", "auth token", "bot token", "signing key",
    "private key", "secret key",
)
_POLICY_CHANGE_VERBS = frozenset({
    "change", "update", "modify", "set", "edit", "alter", "disable",
    "enable", "configure", "write",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _haystack(action: str, details: dict | None) -> str:
    parts = [action or ""]
    if details:
        try:
            parts.append(json.dumps(details, default=str, sort_keys=True))
        except (TypeError, ValueError):
            parts.append(str(details))
    return " ".join(parts)


def _hard_bound_category(action: str, details: dict | None) -> str | None:
    """Return the hard-bound category that fires, or None.

    Order is deliberate: money first, then irreversibility, then
    credentials, then the policy machinery itself.
    """
    text = _haystack(action, details).lower()
    tokens = _tokens(text)
    token_set = set(tokens)

    # Live money: a live trade/order, or money leaving an account.
    if "live" in token_set and token_set & _LIVE_TRADE_TOKENS:
        return "live_money"
    if "real money" in text or "real-money" in text or "live_money" in text:
        return "live_money"
    if token_set & _MONEY_MOVEMENT_TOKENS:
        return "live_money"

    # Deletion of owner data: any destructive verb. Irreversible actions
    # are never in the low-risk class, whatever the caller claims.
    if token_set & _DESTRUCTIVE_TOKENS:
        return "owner_data_deletion"

    # Credential changes (or reading credential material out).
    lowered = text.lower()
    if any(phrase in lowered for phrase in _CREDENTIAL_PHRASES):
        return "credential_change"
    if "secret" in token_set and token_set & _POLICY_CHANGE_VERBS:
        return "credential_change"

    # Changes to Sentinel's own approval/policy machinery.
    if "kill switch" in lowered or "kill_switch" in lowered or "killswitch" in token_set:
        return "sentinel_policy_change"
    if "auto-approve" in lowered or "auto_approve" in lowered or "autoapprove" in token_set:
        return "sentinel_policy_change"
    if "policy" in token_set and token_set & _POLICY_CHANGE_VERBS:
        return "sentinel_policy_change"

    return None


def classify_approval(
    *,
    agent_name: str,
    action: str,
    risk_level: str = "GUARDED",
    details: dict | None = None,
) -> ApprovalClassification:
    """Classify one approval request into AUTO_APPROVE or OWNER_PROMPT.

    Never raises on odd input: unrecognised shapes prompt the owner.
    ``agent_name`` is accepted for symmetry with the dispatcher's
    submission signature and for future per-agent policy; the current
    policy is deliberately agent-agnostic (a trusted name must never be
    what makes an action auto-approvable).
    """
    hard = _hard_bound_category(action or "", details)
    if hard is not None:
        return ApprovalClassification(
            tier=ApprovalTier.OWNER_PROMPT,
            category=hard,
            reason=f"Hard bound '{hard}': Sentinel can never auto-approve this category; the owner decides.",
            hard_bound=True,
        )

    claim = (risk_level or "").strip().upper()
    if claim not in _LOW_RISK_CLAIMS:
        return ApprovalClassification(
            tier=ApprovalTier.OWNER_PROMPT,
            category="caller_risk_not_low",
            reason=(
                f"Caller risk level '{claim or 'UNSPECIFIED'}' is not a low claim; "
                "only LOW-risk items are auto-approved, and caller levels are never downgraded."
            ),
        )

    tokens = _tokens(action or "")
    if not tokens:
        return ApprovalClassification(
            tier=ApprovalTier.OWNER_PROMPT,
            category="action_not_low_risk",
            reason="Empty or unparseable action; cannot positively classify as low-risk.",
        )

    leader = tokens[0]
    if leader in _READ_ONLY_VERBS and not (set(tokens[1:]) & _WRITE_VERBS):
        return ApprovalClassification(
            tier=ApprovalTier.AUTO_APPROVE,
            category="read_only",
            reason=f"Read-only action ('{leader} ...') with a LOW caller risk claim and no hard-bound pattern.",
        )
    if leader in _INTERNAL_LEADERS and not (set(tokens[1:]) & _WRITE_VERBS):
        return ApprovalClassification(
            tier=ApprovalTier.AUTO_APPROVE,
            category="internal",
            reason=f"Internal housekeeping action ('{leader} ...') with a LOW caller risk claim and no hard-bound pattern.",
        )
    if isinstance(details, dict) and details.get("reversible") is True:
        return ApprovalClassification(
            tier=ApprovalTier.AUTO_APPROVE,
            category="reversible_attested",
            reason=(
                "Caller attests the action is reversible (details.reversible is True), "
                "risk claim is LOW, and no destructive or hard-bound pattern is present."
            ),
        )

    return ApprovalClassification(
        tier=ApprovalTier.OWNER_PROMPT,
        category="action_not_low_risk",
        reason=(
            "Action does not positively match the low-risk class "
            "(read-only / internal / caller-attested reversible), so the owner decides."
        ),
    )
