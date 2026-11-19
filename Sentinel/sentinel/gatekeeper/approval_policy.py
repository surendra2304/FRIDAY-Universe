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
  signing-key material being changed, rotated, or read out. This includes
  BARE credential nouns (a lone ``token`` / ``secret``, their plurals, and
  single-token compounds such as ``privatekey`` / ``access_token``):
  the SEN-019 hardening follow-up found that an action naming only the
  bare noun escaped the exact-phrase pass and could auto-approve at LOW
  (``check token``, ``read secret``). Bare nouns are matched as whole
  tokens, never substrings, so lookalikes stay in the low-risk class
  (``tokenizer``, ``secretary``, ``keyboard``, a bare ``key`` in
  ``key metrics``), and a bare ``token`` in the ACTION is excused only
  when every occurrence is usage-qualified (``token usage``,
  ``count tokens``, ``token consumption`` — LLM-usage metering, not
  credential material). The exception never applies to ``secret`` and
  never to the details payload: a bare noun smuggled in details always
  prompts, and a details key literally named ``token`` is credential
  material by name.
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

Never-raises hardening (SEN-019 follow-up): ``classify_approval`` claims
above that it never raises on odd input, but non-string ``action`` /
``risk_level`` values used to raise inside it (``TypeError`` /
``AttributeError``) — callers were fail-closed only by accident, because
the exception happened to abort the submission. Non-string inputs now
return the fail-closed OWNER_PROMPT decision (category
``invalid_input``) BY DESIGN, and the classifier body is guarded so no
unexpected shape can raise out of it.
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
    "private key", "secret key", "access key", "auth key",
    "encryption key", "master key", "passphrase",
)
# --- Bare credential nouns (SEN-019 hardening) ----------------------------
# Matched as WHOLE tokens (the _tokens regex splits on non-alphanumerics,
# so "access_token" tokenises to "access" + "token" and is caught by the
# bare-noun pass, while "tokenizer" / "secretary" are single different
# tokens and are NOT caught). A bare "key" is deliberately NOT in these
# sets: it is an ordinary adjective in this fleet ("key metrics",
# "key findings") and every credential use of it is a phrase above.
_BARE_SECRET_NOUNS = frozenset({"secret", "secrets"})
_BARE_TOKEN_NOUNS = frozenset({"token", "tokens"})
# Single-token compounds whose spaced forms are phrases above.
_CREDENTIAL_COMPOUND_TOKENS = frozenset({
    "privatekey", "secretkey", "accesstoken", "authtoken", "bottoken",
    "signingkey", "accesskey", "encryptionkey",
})
# A bare token noun in the ACTION is excused only when EVERY occurrence
# sits next to one of these usage qualifiers ("token usage",
# "count tokens used", "token consumption"): that is metering of LLM
# tokens, not credential material. The exception is action-only and
# token-only — see the module docstring.
_TOKEN_USAGE_QUALIFIERS = frozenset({
    "usage", "used", "count", "counts", "counted", "counting",
    "consumption", "quota", "budget", "spend", "spending",
})
_POLICY_CHANGE_VERBS = frozenset({
    "change", "update", "modify", "set", "edit", "alter", "disable",
    "enable", "configure", "write",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _details_text(details: dict | None) -> str:
    if not details:
        return ""
    try:
        return json.dumps(details, default=str, sort_keys=True)
    except (TypeError, ValueError):
        return str(details)


def _haystack(action: str, details: dict | None) -> str:
    parts = [action or ""]
    details_text = _details_text(details)
    if details_text:
        parts.append(details_text)
    return " ".join(parts)


def _token_noun_is_usage_only(tokens: list[str]) -> bool:
    """True when every token/tokens occurrence is usage-qualified."""
    occurrences = [i for i, tok in enumerate(tokens) if tok in _BARE_TOKEN_NOUNS]
    if not occurrences:
        return False
    for i in occurrences:
        neighbours = set()
        if i > 0:
            neighbours.add(tokens[i - 1])
        if i + 1 < len(tokens):
            neighbours.add(tokens[i + 1])
        if not (neighbours & _TOKEN_USAGE_QUALIFIERS):
            return False
    return True


def _has_bare_credential(action: str, details: dict | None) -> bool:
    """Bare credential nouns (SEN-019 hardening): see module docstring."""
    action_tokens = _tokens(action or "")
    details_tokens = _tokens(_details_text(details))
    # Secrets and credential compounds are never excused, in the action
    # or smuggled in the details payload.
    if (set(action_tokens) | set(details_tokens)) & (
        _BARE_SECRET_NOUNS | _CREDENTIAL_COMPOUND_TOKENS
    ):
        return True
    # A bare token noun in the DETAILS always fires: the payload cannot
    # prove a usage context, and a key literally named "token" is
    # credential material by name.
    if set(details_tokens) & _BARE_TOKEN_NOUNS:
        return True
    # A bare token noun in the ACTION fires unless every occurrence is
    # usage-qualified (LLM token metering).
    if set(action_tokens) & _BARE_TOKEN_NOUNS:
        return not _token_noun_is_usage_only(action_tokens)
    return False


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
    # Bare credential nouns (SEN-019 hardening). This supersedes the
    # original narrow pass, which fired only when "secret" co-occurred
    # with a policy-change verb — a lone "token" / "secret" named by a
    # read-only action escaped it and auto-approved at LOW.
    if _has_bare_credential(action, details):
        return "credential_change"

    # Changes to Sentinel's own approval/policy machinery.
    if "kill switch" in lowered or "kill_switch" in lowered or "killswitch" in token_set:
        return "sentinel_policy_change"
    if "auto-approve" in lowered or "auto_approve" in lowered or "autoapprove" in token_set:
        return "sentinel_policy_change"
    if "policy" in token_set and token_set & _POLICY_CHANGE_VERBS:
        return "sentinel_policy_change"

    return None


def _invalid_input(reason: str) -> ApprovalClassification:
    return ApprovalClassification(
        tier=ApprovalTier.OWNER_PROMPT,
        category="invalid_input",
        reason=reason,
    )


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

    SEN-019 hardening: non-string ``action`` / ``risk_level`` values
    return the fail-closed OWNER_PROMPT decision (category
    ``invalid_input``) instead of raising — earlier they raised
    ``TypeError`` / ``AttributeError`` inside this function, so the
    fail-closed outcome was an accident of the crash, not the design.
    The reason names the offending TYPE only, never the value (an odd
    value may itself be credential material). Any other unexpected
    shape is caught by the guard around the implementation and also
    prompts: this function never raises.
    """
    if not isinstance(action, str):
        return _invalid_input(
            f"Action is not a string (got {type(action).__name__}); "
            "cannot positively classify as low-risk, so the owner decides."
        )
    if not isinstance(risk_level, str):
        return _invalid_input(
            f"Risk level is not a string (got {type(risk_level).__name__}); "
            "only an explicit LOW string claim can auto-approve, so the owner decides."
        )
    try:
        return _classify_approval_impl(
            agent_name=agent_name, action=action,
            risk_level=risk_level, details=details,
        )
    except Exception:  # never raises: any odd shape prompts the owner
        return _invalid_input(
            "Unparseable approval input; cannot positively classify "
            "as low-risk, so the owner decides."
        )


def _classify_approval_impl(
    *,
    agent_name: str,
    action: str,
    risk_level: str = "GUARDED",
    details: dict | None = None,
) -> ApprovalClassification:
    hard = _hard_bound_category(action or "", details)
    if hard is not None:
        return ApprovalClassification(
            tier=ApprovalTier.OWNER_PROMPT,
            category=hard,
            reason=f"Hard bound '{hard}': Sentinel can never auto-approve this category; the owner decides.",
            hard_bound=True,
        )

    if details is not None and not isinstance(details, dict):
        return _invalid_input(
            f"Details is not a mapping (got {type(details).__name__}); "
            "a payload the policy cannot structurally inspect cannot "
            "positively classify as low-risk, so the owner decides."
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
