from __future__ import annotations

import re
import shlex
from dataclasses import dataclass
from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    APPROVE = "approve"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class CommandDecision:
    decision: Decision
    reason: str
    normalized: str
    risk: str


HIGH_RISK_PATTERNS = (
    r"(^|[\s;&|])rm(\s|$)",
    r"(^|[\s;&|])del(\s|$)",
    r"(^|[\s;&|])rmdir(\s|$)",
    r"(^|[\s;&|])format(\s|$)",
    r"(^|[\s;&|])shutdown(\s|$)",
    r"(^|[\s;&|])reboot(\s|$)",
    r"(^|[\s;&|])curl\s+[^|]*\|\s*(sh|bash|powershell)",
    r"(^|[\s;&|])wget\s+[^|]*\|\s*(sh|bash|powershell)",
    r"(^|[\s;&|])sudo(\s|$)",
    r"(^|[\s;&|])chmod\s+777(\s|$)",
    r"(^|[\s;&|])git\s+push(\s|$)",
    r"(^|[\s;&|])git\s+reset\s+--hard(\s|$)",
)

SECRETS = (
    re.compile(r"(?i)\bAWS_SECRET_ACCESS_KEY\s*=\s*\S+"),
    re.compile(r"(?i)\bGITHUB_TOKEN\s*=\s*\S+"),
    re.compile(r"(?i)\bOPENAI_API_KEY\s*=\s*\S+"),
    re.compile(r"-----BEGIN .*PRIVATE KEY-----"),
)


class CommandPolicy:
    def __init__(self, auto_approve_low_risk: bool = True):
        self.auto_approve_low_risk = auto_approve_low_risk

    def evaluate(
        self, command: str, *, allow_network: bool = False, allow_git_push: bool = False
    ) -> CommandDecision:
        normalized = " ".join(command.strip().split())
        if not normalized:
            return CommandDecision(Decision.DENY, "empty command", normalized, "critical")
        for secret_pattern in SECRETS:
            if secret_pattern.search(normalized):
                return CommandDecision(
                    Decision.DENY, "secret-like command rejected", normalized, "critical"
                )
        for risk_pattern in HIGH_RISK_PATTERNS:
            if re.search(risk_pattern, normalized, re.I):
                if "git push" in normalized.lower() and allow_git_push:
                    return CommandDecision(
                        Decision.APPROVE,
                        "git push requires explicit trusted path",
                        normalized,
                        "high",
                    )
                return CommandDecision(
                    Decision.APPROVE,
                    "high-risk command requires explicit approval",
                    normalized,
                    "high",
                )
        if not allow_network and re.search(r"\b(curl|wget|nc|ssh|scp|ftp)\b", normalized, re.I):
            return CommandDecision(
                Decision.APPROVE, "network access requires explicit policy", normalized, "medium"
            )
        try:
            argv = shlex.split(normalized)
        except ValueError as exc:
            return CommandDecision(
                Decision.DENY, f"malformed shell syntax: {exc}", normalized, "high"
            )
        if not argv:
            return CommandDecision(Decision.DENY, "no executable", normalized, "critical")
        return CommandDecision(
            Decision.ALLOW if self.auto_approve_low_risk else Decision.APPROVE,
            "low-risk command",
            normalized,
            "low",
        )
