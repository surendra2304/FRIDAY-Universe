"""Per-key health monitor for Inference's provider key pools.

TASK-INF-003 (Wave 5). The gateway's ``KeyPool`` knows how many keys a
provider has and how many are quarantined *right now*, and
``app.core.key_inventory`` counts configured keys — but nothing in the
fleet could answer the operator's actual question: **which configured
keys are still alive, which are dead, and which are merely exhausted?**
A pool can report "11 keys configured" while 9 of them return 401.

This module answers that question, per key, with three hard rules:

1. **Fingerprints only.** Reports carry a truncated SHA-256 fingerprint
   (``sha256:<12 hex>``), the pool, the source variable name, an HTTP
   status and a latency. Key values are never printed, logged, stored
   in a report object, or included in an exception message.
2. **Third-party keys stay separate.** ``THIRD_PARTY_*`` keys belong to
   a friend's accounts (owner decision, 2026-11-14). They are collected
   and reported as their own ``third_party`` pool for each provider and
   are never merged into the primary counts — unlike
   ``Settings.get_provider_keys()``, which merges every bucket into one
   routing list (correct for routing, wrong for an audit).
3. **Zero generation cost.** Probes hit each provider's cheapest
   authenticated read endpoint (model list / auth-key info). No probe
   ever asks a model to generate a token, so a full sweep spends no
   quota beyond one metadata request per key.

Classification (per key):

- ``live``      — probe returned HTTP 200.
- ``dead``      — the credential itself is rejected: 401, 403, or a
  Gemini 400 carrying ``API_KEY_INVALID`` / "API key not valid".
- ``exhausted`` — the credential is valid but unusable right now:
  429 (rate limit / ``RESOURCE_EXHAUSTED`` quota) or 402 (no credits).
- ``transient`` — 5xx, timeout or network error: no verdict on the key.
- ``unknown``   — any other response; the HTTP status is reported.
- ``not_probed``— inventory-only mode (``--inventory-only``).

Usage::

    python -m app.core.key_pool_health [--json] [--inventory-only]
                                       [--provider gemini]...

Exit codes: 0 = every probed key live (or inventory-only), 1 = at
least one dead or exhausted key, 2 = the sweep itself could not run.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.core.config import settings

#: Providers this monitor knows how to probe, per the task scope.
PROVIDERS: tuple[str, ...] = ("gemini", "groq", "openrouter")

#: Pool bucket names, in report order.
POOLS: tuple[str, ...] = ("primary", "third_party", "fallback")


class KeyStatus(str, Enum):
    LIVE = "live"
    DEAD = "dead"
    EXHAUSTED = "exhausted"
    TRANSIENT = "transient"
    UNKNOWN = "unknown"
    NOT_PROBED = "not_probed"


def fingerprint_key(key: str) -> str:
    """Return the report-safe fingerprint of a key: ``sha256:<12 hex>``.

    A truncated one-way hash identifies a key across runs (so an
    operator can tell *which* key died) without revealing any of it.
    """
    return "sha256:" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _split_keys(raw: Any) -> list[str]:
    if not raw:
        return []
    out: list[str] = []
    for part in str(raw).split(","):
        cleaned = part.strip().strip("'\"")
        if cleaned:
            out.append(cleaned)
    return out


def _bucket_vars(provider: str) -> dict[str, list[str]]:
    """Map pool bucket -> config attribute names holding its keys.

    Mirrors the attribute layout of ``app.core.config.Settings``
    (singular + plural per bucket). The legacy
    ``THIRD_PARTY_FALLBACK_API_KEY`` is a third-party Gemini key and is
    bucketed as such.
    """
    prov = provider.upper()
    buckets: dict[str, list[str]] = {
        "primary": [f"{prov}_API_KEYS", f"{prov}_API_KEY"],
        "third_party": [f"THIRD_PARTY_{prov}_KEYS", f"THIRD_PARTY_{prov}_KEY"],
        "fallback": [f"{prov}_FALLBACK_KEYS", f"{prov}_FALLBACK_KEY"],
    }
    if prov == "GEMINI":
        buckets["third_party"].append("THIRD_PARTY_FALLBACK_API_KEY")
    return buckets


@dataclass(frozen=True)
class KeyEntry:
    """One configured key and where it came from. ``key`` is the secret;

    it exists only so the prober can authenticate, and is excluded from
    every report structure (see :class:`KeyHealth`, which is built from
    the fingerprint, never from the key)."""

    provider: str
    pool: str
    source: str
    fingerprint: str
    key: str = field(repr=False)


def collect_key_pools(config: Any = None) -> list[KeyEntry]:
    """Collect every configured key for the probed providers.

    Buckets stay separate: a key configured under ``THIRD_PARTY_*`` is
    returned with ``pool="third_party"`` even though routing merges it.
    Deduplication happens *within* a (provider, pool) bucket only, so
    pool counts stay truthful; a key appearing in two buckets yields
    two entries (surfaced in the report's ``duplicates`` list).
    """
    if config is None:
        config = settings
    entries: list[KeyEntry] = []
    for provider in PROVIDERS:
        for pool, attrs in _bucket_vars(provider).items():
            seen: set[str] = set()
            for attr in attrs:
                for key in _split_keys(getattr(config, attr, None)):
                    fp = fingerprint_key(key)
                    if fp in seen:
                        continue
                    seen.add(fp)
                    entries.append(
                        KeyEntry(
                            provider=provider,
                            pool=pool,
                            source=attr,
                            fingerprint=fp,
                            key=key,
                        )
                    )
    return entries


def find_cross_pool_duplicates(entries: list[KeyEntry]) -> list[dict[str, Any]]:
    """Fingerprints configured in more than one pool (never values)."""
    by_fp: dict[str, list[str]] = {}
    for e in entries:
        by_fp.setdefault(e.fingerprint, []).append(f"{e.provider}:{e.pool}")
    return [
        {"fingerprint": fp, "pools": sorted(set(pools))}
        for fp, pools in sorted(by_fp.items())
        if len(set(pools)) > 1
    ]


# ---------------------------------------------------------------------------
# Probe specifications and classification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProbeSpec:
    url: str
    auth_header: str
    auth_prefix: str = ""


PROBE_SPECS: dict[str, ProbeSpec] = {
    # Gemini: model list with the dedicated API-key header. Free, and a
    # bad key is a 400 API_KEY_INVALID rather than a billable call.
    "gemini": ProbeSpec(
        url="https://generativelanguage.googleapis.com/v1beta/models",
        auth_header="x-goog-api-key",
    ),
    # Groq: OpenAI-compatible model list, bearer auth.
    "groq": ProbeSpec(
        url="https://api.groq.com/openai/v1/models",
        auth_header="Authorization",
        auth_prefix="Bearer ",
    ),
    # OpenRouter: /models is public (proves nothing about a key); the
    # auth-key endpoint reports the key's own limit/usage and 401s on a
    # dead key.
    "openrouter": ProbeSpec(
        url="https://openrouter.ai/api/v1/auth/key",
        auth_header="Authorization",
        auth_prefix="Bearer ",
    ),
}

#: Provider error codes that are safe to surface in a report. Anything
#: else in a response body is dropped — bodies are never quoted raw.
_KNOWN_ERROR_CODES = (
    "API_KEY_INVALID",
    "PERMISSION_DENIED",
    "RESOURCE_EXHAUSTED",
    "RATE_LIMIT_EXCEEDED",
    "INSUFFICIENT_CREDITS",
    "INVALID_API_KEY",
)


def _error_code(body: str | None) -> str | None:
    if not body:
        return None
    for code in _KNOWN_ERROR_CODES:
        if code in body:
            return code
    if "api key not valid" in body.lower():
        return "API_KEY_INVALID"
    return None


def classify_response(
    provider: str, http_status: int | None, body: str | None = None
) -> tuple[KeyStatus, str]:
    """Classify one probe response. Returns (status, detail).

    ``detail`` is built only from the HTTP status and a whitelisted
    provider error code — never from the raw body.
    """
    code = _error_code(body)
    suffix = f" ({code})" if code else ""
    if http_status is None:
        return KeyStatus.TRANSIENT, "no response (timeout/network)"
    if http_status == 200:
        return KeyStatus.LIVE, "probe ok"
    if http_status == 429:
        return KeyStatus.EXHAUSTED, f"rate limited / quota{suffix}"
    if http_status == 402:
        return KeyStatus.EXHAUSTED, f"payment required / credits{suffix}"
    if http_status in (401, 403):
        return KeyStatus.DEAD, f"credential rejected HTTP {http_status}{suffix}"
    if http_status == 400 and code == "API_KEY_INVALID":
        return KeyStatus.DEAD, f"credential rejected HTTP 400{suffix}"
    if 500 <= http_status <= 599:
        return KeyStatus.TRANSIENT, f"provider error HTTP {http_status}{suffix}"
    return KeyStatus.UNKNOWN, f"unexpected HTTP {http_status}{suffix}"


# ---------------------------------------------------------------------------
# Probing (transport injectable for tests)
# ---------------------------------------------------------------------------


class ProbeTransport(Protocol):
    async def get(self, url: str, headers: dict[str, str]) -> tuple[int, str]:
        """GET and return (http_status, body_text). Raise on transport errors."""
        ...


class HttpxTransport:
    """Default transport: one shared httpx client for the whole sweep."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout
        self._client: Any = None

    async def __aenter__(self) -> "HttpxTransport":
        import httpx

        self._client = httpx.AsyncClient(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get(self, url: str, headers: dict[str, str]) -> tuple[int, str]:
        if self._client is None:
            raise RuntimeError("HttpxTransport used outside its context manager")
        resp = await self._client.get(url, headers=headers)
        return resp.status_code, resp.text[:2048]


@dataclass
class KeyHealth:
    provider: str
    pool: str
    source: str
    fingerprint: str
    status: str
    http_status: int | None
    latency_ms: float | None
    detail: str


@dataclass
class PoolSummary:
    provider: str
    pool: str
    total: int = 0
    live: int = 0
    dead: int = 0
    exhausted: int = 0
    transient: int = 0
    unknown: int = 0
    not_probed: int = 0


@dataclass
class HealthReport:
    generated_at: float
    probed: bool
    keys: list[KeyHealth]
    pools: list[PoolSummary]
    duplicates: list[dict[str, Any]]

    def totals(self) -> dict[str, int]:
        totals: dict[str, int] = {"total": len(self.keys)}
        for status in KeyStatus:
            totals[status.value] = sum(1 for k in self.keys if k.status == status.value)
        return totals

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "probed": self.probed,
            "totals": self.totals(),
            "pools": [asdict(p) for p in self.pools],
            "keys": [asdict(k) for k in self.keys],
            "duplicates": self.duplicates,
        }


def _summarise(keys: list[KeyHealth]) -> list[PoolSummary]:
    summaries: dict[tuple[str, str], PoolSummary] = {}
    for provider in PROVIDERS:
        for pool in POOLS:
            summaries[(provider, pool)] = PoolSummary(provider=provider, pool=pool)
    for k in keys:
        summary = summaries[(k.provider, k.pool)]
        summary.total += 1
        setattr(summary, k.status, getattr(summary, k.status) + 1)
    return [s for s in summaries.values() if s.total > 0]


async def probe_entries(
    entries: list[KeyEntry],
    transport: ProbeTransport,
    concurrency: int = 5,
) -> HealthReport:
    """Probe every entry (bounded concurrency) and build the report."""
    semaphore = asyncio.Semaphore(max(1, concurrency))

    async def _probe(entry: KeyEntry) -> KeyHealth:
        spec = PROBE_SPECS[entry.provider]
        headers = {spec.auth_header: spec.auth_prefix + entry.key}
        started = time.monotonic()
        try:
            async with semaphore:
                http_status, body = await transport.get(spec.url, headers)
        except Exception:  # noqa: BLE001 - any transport failure is transient
            http_status, body = None, None
        latency_ms = round((time.monotonic() - started) * 1000.0, 1)
        status, detail = classify_response(entry.provider, http_status, body)
        return KeyHealth(
            provider=entry.provider,
            pool=entry.pool,
            source=entry.source,
            fingerprint=entry.fingerprint,
            status=status.value,
            http_status=http_status,
            latency_ms=latency_ms,
            detail=detail,
        )

    keys = await asyncio.gather(*(_probe(e) for e in entries))
    keys_sorted = sorted(keys, key=lambda k: (k.provider, k.pool, k.fingerprint))
    return HealthReport(
        generated_at=time.time(),
        probed=True,
        keys=keys_sorted,
        pools=_summarise(keys_sorted),
        duplicates=find_cross_pool_duplicates(entries),
    )


def inventory_report(entries: list[KeyEntry]) -> HealthReport:
    """Report configured pools without probing (status ``not_probed``)."""
    keys = sorted(
        (
            KeyHealth(
                provider=e.provider,
                pool=e.pool,
                source=e.source,
                fingerprint=e.fingerprint,
                status=KeyStatus.NOT_PROBED.value,
                http_status=None,
                latency_ms=None,
                detail="inventory only; not probed",
            )
            for e in entries
        ),
        key=lambda k: (k.provider, k.pool, k.fingerprint),
    )
    return HealthReport(
        generated_at=time.time(),
        probed=False,
        keys=keys,
        pools=_summarise(keys),
        duplicates=find_cross_pool_duplicates(entries),
    )


async def run_health_check(
    config: Any = None,
    providers: tuple[str, ...] | None = None,
    timeout: float = 10.0,
    concurrency: int = 5,
    probe: bool = True,
) -> HealthReport:
    entries = collect_key_pools(config)
    if providers:
        wanted = {p.lower() for p in providers}
        entries = [e for e in entries if e.provider in wanted]
    if not probe:
        return inventory_report(entries)
    async with HttpxTransport(timeout=timeout) as transport:
        return await probe_entries(entries, transport, concurrency=concurrency)


# ---------------------------------------------------------------------------
# Reporting / CLI
# ---------------------------------------------------------------------------


def render_text(report: HealthReport) -> str:
    lines: list[str] = []
    mode = "PROBED" if report.probed else "INVENTORY ONLY (not probed)"
    lines.append(f"Inference key-pool health — {mode}")
    for pool in report.pools:
        lines.append(
            f"{pool.provider.upper()} {pool.pool}: total={pool.total} "
            f"live={pool.live} dead={pool.dead} exhausted={pool.exhausted} "
            f"transient={pool.transient} unknown={pool.unknown} "
            f"not_probed={pool.not_probed}"
        )
    totals = report.totals()
    lines.append(
        f"TOTAL: {totals['total']} keys — live={totals['live']} "
        f"dead={totals['dead']} exhausted={totals['exhausted']} "
        f"transient={totals['transient']} unknown={totals['unknown']} "
        f"not_probed={totals['not_probed']}"
    )
    for dup in report.duplicates:
        lines.append(
            f"DUPLICATE fingerprint {dup['fingerprint']} configured in pools: "
            + ", ".join(dup["pools"])
        )
    lines.append("Per-key (fingerprints only):")
    for k in report.keys:
        http = k.http_status if k.http_status is not None else "-"
        latency = f"{k.latency_ms}ms" if k.latency_ms is not None else "-"
        lines.append(
            f"  {k.provider} {k.pool} {k.fingerprint} status={k.status} "
            f"http={http} latency={latency} source={k.source} — {k.detail}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None, config: Any = None) -> int:
    parser = argparse.ArgumentParser(
        prog="key_pool_health",
        description="Per-key health of Inference's provider key pools "
        "(fingerprints/counts only; key values are never printed).",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--inventory-only",
        action="store_true",
        help="report configured pools without probing any key",
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=list(PROVIDERS),
        help="restrict to a provider (repeatable)",
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args(argv)

    try:
        report = asyncio.run(
            run_health_check(
                config=config,
                providers=tuple(args.provider) if args.provider else None,
                timeout=args.timeout,
                concurrency=args.concurrency,
                probe=not args.inventory_only,
            )
        )
    except Exception as exc:  # noqa: BLE001 - sweep failure must not leak anything
        print(f"key-pool health sweep failed: {type(exc).__name__}")
        return 2

    print(json.dumps(report.to_dict(), indent=2) if args.json else render_text(report))
    totals = report.totals()
    if not report.probed:
        return 0
    return 1 if (totals["dead"] or totals["exhausted"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
