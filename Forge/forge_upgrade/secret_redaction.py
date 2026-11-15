from __future__ import annotations

import re

PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN .*PRIVATE KEY-----[\s\S]*?-----END .*PRIVATE KEY-----"),
)

# Credentials carried in the userinfo segment of a URL, e.g.
# https://x-access-token:<secret>@github.com/owner/repo.git or
# https://user:<password>@host/path. Neither the keyword pattern (the
# username is not a keyword) nor the token-shape patterns (an arbitrary
# password has no known prefix) cover this position, and it is exactly how
# a GitHub token reached Forge's workspace terminal.log files
# (SEN-005 finding F-1, remediated by TASK-SEN-011).
URL_USERINFO_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]*://[^\s/:@]+:)[^\s/@]+@")


def redact(text: str) -> str:
    value = text
    value = PATTERNS[0].sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    for pattern in PATTERNS[1:]:
        value = pattern.sub("[REDACTED]", value)
    value = URL_USERINFO_PATTERN.sub(r"\1[REDACTED]@", value)
    return value


def safe_error(message: str, max_chars: int = 10000) -> str:
    return redact(message)[:max_chars]
