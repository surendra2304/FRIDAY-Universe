from __future__ import annotations

import re

PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*([^\s,;]+)"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"-----BEGIN .*PRIVATE KEY-----[\s\S]*?-----END .*PRIVATE KEY-----"),
)


def redact(text: str) -> str:
    value = text
    value = PATTERNS[0].sub(lambda m: f"{m.group(1)}=[REDACTED]", value)
    for pattern in PATTERNS[1:]:
        value = pattern.sub("[REDACTED]", value)
    return value


def safe_error(message: str, max_chars: int = 10000) -> str:
    return redact(message)[:max_chars]
