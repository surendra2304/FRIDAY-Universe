#!/usr/bin/env python3
"""Replay a request log through the TASK-INF-006 safe response cache.

Measures the hit-rate and latency saving the cache would have produced on
a recorded request stream, without calling any provider.

Log format (JSONL, one request per line):
    {"prompt": "...", "context": {...}, "principal_id": "user-1" | null,
     "temperature": 0.0, "latency_ms": 1234.0,
     "template_id": "market_summary" | null, "slots": {...}}

A header line may register templates:
    {"_templates": [{"template_id": "market_summary", "version": "1",
                     "invariant_slots": ["request_id"]}]}

``latency_ms`` is the latency the provider originally took for that
request. On a simulated hit, that latency counts as saved (minus a 0.2ms
lookup allowance); on a miss the virtual clock advances by the latency,
so TTL expiry is exercised in request-stream time rather than wall time.

Safety accounting: personalised requests (a principal id, or one inside
``context``) are counted separately, and any hit served to a *different*
principal than the one that stored the entry is reported as a violation.
With the default policy, personalised answers are never stored, so the
only correct outcome is zero personalised hits and zero violations.

Usage:
    python3 replay_response_cache.py LOG.jsonl [--json]
    python3 replay_response_cache.py --generate-sample OUT.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.inference_runtime.response_cache import (  # noqa: E402
    CachePolicy,
    SafeResponseCache,
    TemplateSpec,
)

LOOKUP_COST_MS = 0.2


class _VirtualClock:
    """Process-local monotonic clock so TTLs run in stream time."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def monotonic(self) -> float:
        return self.now

    def advance_ms(self, ms: float) -> None:
        self.now += ms / 1000.0


def replay_log(entries: list[dict[str, Any]], policy: CachePolicy | None = None) -> dict[str, Any]:
    clock = _VirtualClock()
    real_monotonic = time.monotonic
    time.monotonic = clock.monotonic  # the cache reads time.monotonic
    try:
        cache = SafeResponseCache(policy or CachePolicy())
        for entry in entries:
            templates = entry.get("_templates")
            if templates:
                for spec in templates:
                    cache.register_template(
                        TemplateSpec(
                            template_id=spec["template_id"],
                            version=str(spec.get("version", "1")),
                            invariant_slots=frozenset(spec.get("invariant_slots", [])),
                        )
                    )
        totals = {
            "requests": 0,
            "hits": 0,
            "hits_exact": 0,
            "hits_template": 0,
            "misses": 0,
            "bypasses": 0,
            "latency_saved_ms": 0.0,
            "provider_latency_ms": 0.0,
            "personalised_requests": 0,
            "personalised_hits": 0,
            "cross_principal_violations": 0,
        }
        # key -> principal that stored it, to audit who each hit served.
        stored_principal: dict[str, str | None] = {}
        for entry in entries:
            if "_templates" in entry:
                continue
            totals["requests"] += 1
            latency_ms = float(entry.get("latency_ms", 0.0))
            totals["provider_latency_ms"] += latency_ms
            context = entry.get("context") or {}
            principal = entry.get("principal_id")
            context_class = cache.classify(
                principal_id=principal, context=context, prompt_text=entry.get("prompt", "")
            )
            fingerprint = SafeResponseCache.context_fingerprint(context, principal)
            payload = {
                "prompt": entry.get("prompt", ""),
                "temperature": entry.get("temperature", 0.0),
                "max_tokens": entry.get("max_tokens"),
                "model": entry.get("model"),
                # A per-request id makes every raw request unique, so
                # template entries can only hit through the template key —
                # which is exactly the production situation the template
                # mechanism exists for.
                "request_id": entry.get("request_id"),
            }
            is_personalised = context_class.value == "personalised"
            if is_personalised:
                totals["personalised_requests"] += 1
            lookup = cache.lookup(
                namespace=entry.get("namespace", "replay"),
                payload=payload,
                context_class=context_class,
                context_fingerprint=fingerprint,
                template_id=entry.get("template_id"),
                template_slots=entry.get("slots"),
                stochastic=float(entry.get("temperature", 0.0)) > 0,
            )
            if lookup.hit:
                totals["hits"] += 1
                totals["hits_exact" if lookup.match_kind == "exact" else "hits_template"] += 1
                totals["latency_saved_ms"] += max(0.0, latency_ms - LOOKUP_COST_MS)
                clock.advance_ms(LOOKUP_COST_MS)
                if is_personalised:
                    totals["personalised_hits"] += 1
                    if stored_principal.get(lookup.key) != (principal or None):
                        totals["cross_principal_violations"] += 1
            else:
                if lookup.reason.startswith("bypass:"):
                    totals["bypasses"] += 1
                else:
                    totals["misses"] += 1
                clock.advance_ms(latency_ms)
                stored_key = cache.store(
                    namespace=entry.get("namespace", "replay"),
                    payload=payload,
                    value={"text": "<simulated>"},
                    context_class=context_class,
                    context_fingerprint=fingerprint,
                    principal_id=principal,
                    original_latency_seconds=latency_ms / 1000.0,
                    template_id=entry.get("template_id"),
                    template_slots=entry.get("slots"),
                    stochastic=float(entry.get("temperature", 0.0)) > 0,
                )
                if not stored_key.startswith("bypass:"):
                    stored_principal[stored_key] = principal or None
        totals["hit_rate"] = round(totals["hits"] / totals["requests"], 4) if totals["requests"] else 0.0
        totals["latency_saved_ms"] = round(totals["latency_saved_ms"], 1)
        totals["provider_latency_ms"] = round(totals["provider_latency_ms"], 1)
        totals["cache_stats"] = cache.stats()
        return totals
    finally:
        time.monotonic = real_monotonic


def generate_sample(path: Path) -> None:
    """Deterministic sample log built from the request shapes the fleet's
    own callers produce (repeated FRIDAY questions, repeated unified task
    calls under one context, template task calls with varying request
    ids, and personalised repeats across four principals). Latencies are
    illustrative provider latencies in the range the fleet observes; the
    log is synthetic and labelled as such — replay a real exported log
    for production figures."""
    rng = random.Random(6006)
    lines: list[dict[str, Any]] = [
        {"_templates": [{"template_id": "market_summary", "version": "1",
                         "invariant_slots": ["request_id"]}]}
    ]

    def lat(lo: float, hi: float) -> float:
        return round(rng.uniform(lo, hi), 1)

    # Repeated public questions (FRIDAY ask path shape).
    public_qs = [
        "What is the capital of France?",
        "Explain photosynthesis in two sentences",
        "What is a hash map?",
        "Summarize the reporting strategy",
        "What is inference",
        "Define eventual consistency",
        "What is the boiling point of water?",
        "Explain the difference between TCP and UDP",
        "What is a circuit breaker pattern?",
        "How does a Kalman filter work?",
    ]
    for q in public_qs:
        for _ in range(6):
            lines.append({"prompt": q, "context": {}, "principal_id": None,
                          "temperature": 0.0, "latency_ms": lat(800, 4000)})

    # Repeated task calls under one shared context (unified manager shape).
    modules = [f"module_{i}" for i in range(10)]
    for m in modules:
        for _ in range(5):
            lines.append({"prompt": f"Generate unit tests for {m}",
                          "context": {"workspace": "friday", "repo": "FRIDAY-Universe"},
                          "principal_id": None, "temperature": 0.0,
                          "latency_ms": lat(3000, 9000)})

    # Personalised repeats across four principals: must never be served
    # to another principal (default policy stores none of them).
    for p in range(4):
        for _ in range(10):
            lines.append({"prompt": "What is my current portfolio balance?",
                          "context": {"session_id": f"sess-{p}"},
                          "principal_id": f"user-{p}", "temperature": 0.0,
                          "latency_ms": lat(1000, 5000)})

    # Template task calls: request_id is invariant, symbol is semantic.
    for symbol in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XAUUSD", "EURUSD"]:
        for i in range(8):
            lines.append({"prompt": "Produce the hourly market summary",
                          "context": {}, "principal_id": None, "temperature": 0.0,
                          "latency_ms": lat(2000, 6000),
                          "request_id": f"req-{symbol}-{i}",
                          "template_id": "market_summary",
                          "slots": {"symbol": symbol, "request_id": f"req-{symbol}-{i}"}})

    # One-off unique prompts: always misses.
    for i in range(50):
        lines.append({"prompt": f"Unique question number {i} about topic {i * 7 % 13}",
                      "context": {}, "principal_id": None, "temperature": 0.0,
                      "latency_ms": lat(800, 4000)})

    rng.shuffle(lines[1:])
    with path.open("w", encoding="utf-8") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")
    print(f"wrote {len(lines)} lines to {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", nargs="?", type=Path)
    parser.add_argument("--generate-sample", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.generate_sample:
        generate_sample(args.generate_sample)
        return 0
    if not args.log:
        parser.error("a log path is required (or use --generate-sample)")

    entries = [
        json.loads(line)
        for line in args.log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    result = replay_log(entries)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"requests:            {result['requests']}")
        print(f"hits:                {result['hits']} (exact {result['hits_exact']}, template {result['hits_template']})")
        print(f"hit rate:            {result['hit_rate']:.1%}")
        print(f"misses:              {result['misses']}  bypasses: {result['bypasses']}")
        print(f"provider latency:    {result['provider_latency_ms']:.0f} ms total")
        print(f"latency saved:       {result['latency_saved_ms']:.0f} ms "
              f"({result['latency_saved_ms'] / result['provider_latency_ms']:.1%} of provider time)")
        print(f"personalised:        {result['personalised_requests']} requests, "
              f"{result['personalised_hits']} hits, "
              f"{result['cross_principal_violations']} cross-principal violations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
