"""Per-provider free-tier quota accounting for Inference (TASK-INF-007).

Why this exists
---------------
FRIDAY has repeatedly gone *answerless by surprise*: a free-tier daily quota
died silently mid-day and the failure only surfaced as a user-facing outage.
The pieces that already existed solve different problems —

* ``app/inference_runtime/quotas.py`` is per-*tenant* admission control
  (requests/tokens per minute for calling agents), and
* ``app/analytics/usage_analytics.py`` aggregates whatever callers *report*
  (its own docstring records that callers once fabricated the provider),

— neither counts what the providers actually let us spend. This module is
the provider-side ledger: :class:`app.providers.gateway.ModelGateway`
records **every attempt it makes** (primary, fallback rungs, streams) here,
and the ledger measures those attempts against the declared free-tier
limits:

* **Gemini** — ~20 requests/day per project+model on the production model.
  Each API key is accounted as one project bucket, per model, per
  Pacific day (the free-tier window resets at midnight Pacific).
* **Groq** — an operator-observed fleet ceiling of 8,000 tokens/minute
  across *all* Groq keys, accounted on a rolling 60-second window.
* Everything else is **accounted but has no declared limit** (state
  ``no_declared_limit``) — the ledger never invents a limit it was not given.
* **Bytez** (TASK-IG2-INF-01) is accounted but carries the distinct state
  ``unproven_free_tier``: its documented $0 tier states no recurring free
  allowance, so no limit may be declared — and no fleet budget may count
  on Bytez volume — until the empirical probe in
  ``app.providers.bytez_probe`` has measured real volume across repeated
  runs and an operator declares a limit from that evidence.

Warning before exhaustion is the point: a bucket enters ``warning`` at
:data:`WARN_FRACTION` (default 80%) of its limit and ``exhausted`` at the
limit — or the moment the provider itself returns a 429 for a
daily-limited bucket, because the provider's verdict outranks our count.
The picture is served at ``GET /v1/quota``.

Honesty bounds (also stated in every snapshot)
----------------------------------------------
* Counts are attempts made **through this Inference process** since the
  ledger started, plus today's events replayed from the JSONL ledger after
  a restart. Usage of the same keys by other clients (e.g. FRIDAY's own
  direct Gemini pool) is not visible here and is not claimed.
* Token figures are the providers' own reported usage. A response that
  reports no usage is counted as a request with *unmeasured* tokens —
  never as zero tokens.
* API keys are represented only by a truncated SHA-256 fingerprint
  (``sha256(key)[:10]``). Key values are never stored, logged, returned,
  or written to the ledger file.

Persistence is an append-only JSONL file per Pacific day under
``app/.data/`` (repo house rule: no SQLite). Writes are best-effort: a
persistence failure is counted in the snapshot and never breaks serving.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

PACIFIC = ZoneInfo("America/Los_Angeles")

#: Declared free-tier limits. Each is operator-overridable via the
#: environment so a tier change is a config edit, not a code change.
GEMINI_DAILY_REQUEST_LIMIT = max(1, int(os.environ.get("INFERENCE_GEMINI_DAILY_REQUEST_LIMIT", "20")))
GROQ_FLEET_TPM_LIMIT = max(1, int(os.environ.get("INFERENCE_GROQ_FLEET_TPM_LIMIT", "8000")))
WARN_FRACTION = min(1.0, max(0.0, float(os.environ.get("INFERENCE_QUOTA_WARN_FRACTION", "0.8"))))

_DEFAULT_LEDGER_DIR = Path(__file__).resolve().parent.parent / ".data"
LEDGER_DIR = Path(os.environ.get("INFERENCE_QUOTA_LEDGER_DIR", str(_DEFAULT_LEDGER_DIR)))

#: Providers with no metered quota at all (self-hosted / transport shims).
UNMETERED_PROVIDERS = frozenset({"local", "litellm", "llamacpp", "vllm", "sglang", "ollama"})

#: Providers whose free tier is documented but whose recurring free volume
#: is UNPROVEN (TASK-IG2-INF-01). Attempts are accounted like any other
#: provider, but the snapshot state is ``unproven_free_tier`` and no limit
#: or used-fraction is ever reported for them: nothing may budget against
#: volume that has not been measured. A provider leaves this set only when
#: an operator declares a measured limit for it in code.
UNPROVEN_FREE_TIER_PROVIDERS = frozenset({"bytez"})

OUTCOMES = frozenset({"success", "rate_limited", "unavailable", "timeout", "error"})

def key_fingerprint(api_key: str | None) -> str | None:
    """Stable, non-reversible identity for a key. Never returns the key."""
    if not api_key:
        return None
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:10]


def pacific_date(ts: float) -> str:
    """The Pacific-calendar date (ISO) containing epoch ``ts``."""
    return datetime.fromtimestamp(ts, tz=PACIFIC).date().isoformat()


def next_reset_ts(ts: float) -> float:
    """Epoch of the next Pacific midnight strictly after ``ts``."""
    local = datetime.fromtimestamp(ts, tz=PACIFIC)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return midnight.timestamp()


def _iso_utc(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _new_bucket() -> dict[str, Any]:
    return {
        "requests": 0,
        "successes": 0,
        "rate_limited": 0,
        "unavailable": 0,
        "timeouts": 0,
        "errors": 0,
        "tokens_measured_requests": 0,
        "total_tokens": 0,
        "exhausted_by_provider_429": False,
        "first_ts": None,
        "last_ts": None,
    }


class QuotaLedger:
    """Thread-safe in-memory ledger + append-only JSONL persistence."""

    def __init__(self, ledger_dir: Path | None = None) -> None:
        self._dir = Path(ledger_dir) if ledger_dir is not None else LEDGER_DIR
        self._lock = threading.Lock()
        # (provider, key_fp|"unattributed", model, pacific_date) -> counters
        self._daily: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        # Rolling Groq window: (ts, total_tokens|None) for every Groq attempt.
        self._groq_window: deque[tuple[float, int | None]] = deque()
        self._events_recorded = 0
        self._events_replayed = 0
        self._persist_failures = 0
        self._load_today()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def _path_for(self, date_iso: str) -> Path:
        return self._dir / f"quota_ledger-{date_iso}.jsonl"

    def _load_today(self) -> None:
        """Replay today's JSONL events (post-restart continuity)."""
        path = self._path_for(pacific_date(time.time()))
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
                self._apply(event)
                self._events_replayed += 1
            except (ValueError, KeyError, TypeError):
                continue  # a torn final line must not kill startup

    def _persist(self, event: dict[str, Any]) -> None:
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            with open(self._path_for(event["date"]), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(event) + "\n")
        except OSError:
            self._persist_failures += 1

    # ------------------------------------------------------------------
    # recording
    # ------------------------------------------------------------------
    def _apply(self, event: dict[str, Any]) -> None:
        provider = event["provider"]
        key = (provider, event.get("key_fp") or "unattributed", event.get("model") or "unknown", event["date"])
        bucket = self._daily.get(key)
        if bucket is None:
            bucket = _new_bucket()
            self._daily[key] = bucket
        outcome = event.get("outcome") or "error"
        bucket["requests"] += 1
        if outcome == "success":
            bucket["successes"] += 1
        elif outcome == "rate_limited":
            bucket["rate_limited"] += 1
            if provider == "gemini":
                # A 429 against a daily-limited bucket is the provider
                # declaring the day over for this key+model, whatever our
                # count says. The provider's verdict outranks the count.
                bucket["exhausted_by_provider_429"] = True
        elif outcome == "unavailable":
            bucket["unavailable"] += 1
        elif outcome == "timeout":
            bucket["timeouts"] += 1
        else:
            bucket["errors"] += 1
        total = event.get("total_tokens")
        if isinstance(total, int) and total > 0:
            bucket["tokens_measured_requests"] += 1
            bucket["total_tokens"] += total
        ts = float(event.get("ts") or 0.0)
        if bucket["first_ts"] is None or ts < bucket["first_ts"]:
            bucket["first_ts"] = ts
        if bucket["last_ts"] is None or ts > bucket["last_ts"]:
            bucket["last_ts"] = ts
        if provider == "groq":
            self._groq_window.append((ts, total if isinstance(total, int) and total > 0 else None))

    def record(
        self,
        *,
        provider: str,
        model: str | None,
        api_key: str | None = None,
        key_fp: str | None = None,
        outcome: str = "success",
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        ts: float | None = None,
    ) -> None:
        """Record one provider attempt. Never raises into the serving path."""
        try:
            when = time.time() if ts is None else float(ts)
            if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
                total_tokens = prompt_tokens + completion_tokens
            event = {
                "ts": when,
                "date": pacific_date(when),
                "provider": (provider or "unknown").lower().strip(),
                "model": model or "unknown",
                "key_fp": key_fp if key_fp is not None else key_fingerprint(api_key),
                "outcome": outcome if outcome in OUTCOMES else "error",
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
            }
            with self._lock:
                self._apply(event)
                self._events_recorded += 1
                self._prune(when)
            self._persist(event)
        except Exception:  # noqa: BLE001 - accounting must never break serving
            pass

    def record_response(
        self,
        *,
        provider: str,
        model: str | None,
        api_key: str | None,
        outcome: str,
        response: Any | None,
    ) -> None:
        """Record an attempt whose token usage comes from a ProviderResponse.

        A response reporting 0/None usage is *unmeasured*, not zero: the
        request counts, the tokens do not.
        """
        prompt = completion = total = None
        if response is not None:
            p = getattr(response, "prompt_tokens", None)
            c = getattr(response, "completion_tokens", None)
            t = getattr(response, "total_tokens", None)
            if isinstance(t, int) and t > 0:
                total = t
                prompt = p if isinstance(p, int) and p > 0 else None
                completion = c if isinstance(c, int) and c > 0 else None
            elif isinstance(p, int) and isinstance(c, int) and (p + c) > 0:
                prompt, completion, total = p, c, p + c
        self.record(
            provider=provider,
            model=(getattr(response, "model", None) or model),
            api_key=api_key,
            outcome=outcome,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )

    def _prune(self, now: float) -> None:
        today = pacific_date(now)
        stale = [k for k in self._daily if k[3] != today]
        for k in stale:
            del self._daily[k]
        cutoff = now - 60.0
        while self._groq_window and self._groq_window[0][0] < cutoff:
            self._groq_window.popleft()

    # ------------------------------------------------------------------
    # state computation
    # ------------------------------------------------------------------
    @staticmethod
    def _gemini_bucket_state(bucket: dict[str, Any]) -> str:
        if bucket["exhausted_by_provider_429"] or bucket["requests"] >= GEMINI_DAILY_REQUEST_LIMIT:
            return "exhausted"
        if bucket["requests"] >= WARN_FRACTION * GEMINI_DAILY_REQUEST_LIMIT:
            return "warning"
        return "ok"

    def _groq_rolling(self, now: float) -> dict[str, Any]:
        cutoff = now - 60.0
        window = [(ts, tok) for ts, tok in self._groq_window if ts >= cutoff]
        measured = [tok for _, tok in window if tok is not None]
        tokens = sum(measured)
        fraction = (tokens / GROQ_FLEET_TPM_LIMIT) if GROQ_FLEET_TPM_LIMIT > 0 else 0.0
        state = "exhausted" if fraction >= 1.0 else "warning" if fraction >= WARN_FRACTION else "ok"
        return {
            "measured_tokens": tokens,
            "limit_tokens_per_minute": GROQ_FLEET_TPM_LIMIT,
            "used_fraction": round(fraction, 4),
            "state": state,
            "requests_in_window": len(window),
            "measured_requests_in_window": len(measured),
            "basis": "rolling 60 seconds, fleet-wide across all Groq keys, provider-reported tokens only",
        }

    def snapshot(self, now: float | None = None) -> dict[str, Any]:
        """The full current usage picture, as served at ``GET /v1/quota``."""
        when = time.time() if now is None else float(now)
        today = pacific_date(when)
        reset_ts = next_reset_ts(when)
        with self._lock:
            self._prune(when)
            buckets = {k: dict(v) for k, v in self._daily.items() if k[3] == today}
            groq = self._groq_rolling(when)
            coverage = {
                "events_recorded_this_process": self._events_recorded,
                "events_replayed_on_start": self._events_replayed,
                "persist_failures": self._persist_failures,
            }

        providers: dict[str, dict[str, Any]] = {}
        warnings: list[str] = []
        for (provider, key_fp, model, _date), b in sorted(buckets.items()):
            entry = providers.setdefault(
                provider,
                {"requests_today": 0, "successes_today": 0, "rate_limited_today": 0, "daily_buckets": []},
            )
            entry["requests_today"] += b["requests"]
            entry["successes_today"] += b["successes"]
            entry["rate_limited_today"] += b["rate_limited"]
            row: dict[str, Any] = {
                "key_fingerprint": None if key_fp == "unattributed" else key_fp,
                "key_attributed": key_fp != "unattributed",
                "model": model,
                "requests": b["requests"],
                "successes": b["successes"],
                "rate_limited": b["rate_limited"],
                "unavailable": b["unavailable"],
                "timeouts": b["timeouts"],
                "errors": b["errors"],
                "total_tokens": b["total_tokens"] if b["tokens_measured_requests"] else None,
                "tokens_measured_requests": b["tokens_measured_requests"],
                "first_seen_utc": _iso_utc(b["first_ts"]) if b["first_ts"] else None,
                "last_seen_utc": _iso_utc(b["last_ts"]) if b["last_ts"] else None,
            }
            if provider == "gemini":
                state = self._gemini_bucket_state(b)
                row["limit_requests_per_day"] = GEMINI_DAILY_REQUEST_LIMIT
                row["used_fraction"] = round(b["requests"] / GEMINI_DAILY_REQUEST_LIMIT, 4)
                row["state"] = state
                row["exhausted_by_provider_429"] = b["exhausted_by_provider_429"]
                if state != "ok":
                    warnings.append(
                        f"gemini key {key_fp} model {model}: {b['requests']}/{GEMINI_DAILY_REQUEST_LIMIT} "
                        f"requests today — {state.upper()}"
                        + (" (provider returned 429)" if b["exhausted_by_provider_429"] else "")
                        + f"; window resets {_iso_utc(reset_ts)}"
                    )
            entry["daily_buckets"].append(row)

        for provider, entry in providers.items():
            entry["daily_buckets"].sort(key=lambda r: -r["requests"])
            if provider == "gemini":
                # Fleet state: a model is exhausted when EVERY key bucket
                # for it is exhausted; the provider is exhausted only when
                # every model is — FRIDAY goes answerless at that point,
                # not before. Warning fires earlier: any model fully
                # exhausted, or every key for a model at/past the warning
                # line, or any single key exhausted.
                states_by_model: dict[str, list[str]] = {}
                for row in entry["daily_buckets"]:
                    states_by_model.setdefault(row["model"], []).append(row["state"])
                model_states = []
                for states in states_by_model.values():
                    if all(s == "exhausted" for s in states):
                        model_states.append("exhausted")
                    elif all(s in ("warning", "exhausted") for s in states) or any(
                        s == "exhausted" for s in states
                    ):
                        model_states.append("warning")
                    else:
                        model_states.append("ok")
                if model_states and all(s == "exhausted" for s in model_states):
                    entry["state"] = "exhausted"
                elif any(s in ("warning", "exhausted") for s in model_states):
                    entry["state"] = "warning"
                else:
                    entry["state"] = "ok"
                entry["keys_seen_today"] = len({r["key_fingerprint"] for r in entry["daily_buckets"] if r["key_fingerprint"]})
            elif provider == "groq":
                entry["rolling_minute"] = groq
                entry["state"] = groq["state"]
            elif provider in UNMETERED_PROVIDERS:
                entry["state"] = "unmetered"
            elif provider in UNPROVEN_FREE_TIER_PROVIDERS:
                # TASK-IG2-INF-01: accounted, but no limit exists to measure
                # against — the free volume is unproven until the Bytez
                # quota probe measures it and an operator declares a limit.
                entry["state"] = "unproven_free_tier"
            else:
                entry["state"] = "no_declared_limit"

        # A Groq burst that straddles Pacific midnight lives in the rolling
        # window even though its daily bucket belongs to yesterday.
        if "groq" not in providers and groq["requests_in_window"]:
            providers["groq"] = {
                "requests_today": 0,
                "successes_today": 0,
                "rate_limited_today": 0,
                "daily_buckets": [],
                "rolling_minute": groq,
                "state": groq["state"],
            }
        if providers.get("groq", {}).get("state") in ("warning", "exhausted"):
            warnings.append(
                f"groq fleet: {groq['measured_tokens']}/{GROQ_FLEET_TPM_LIMIT} tokens in the "
                f"last minute — {groq['state'].upper()}"
            )

        any_exhausted = any(e.get("state") == "exhausted" for e in providers.values())
        any_warning = any_exhausted or any(e.get("state") == "warning" for e in providers.values()) or bool(warnings)
        return {
            "service": "inference",
            "generated_at_utc": _iso_utc(when),
            "pacific_date": today,
            "window_reset": {
                "timezone": "America/Los_Angeles",
                "next_reset_utc": _iso_utc(reset_ts),
                "seconds_to_reset": int(reset_ts - when),
            },
            "limits": {
                "gemini_daily_requests_per_key_model": GEMINI_DAILY_REQUEST_LIMIT,
                "gemini_basis": (
                    "operator-declared free-tier figure (~20 requests/day per project+model on the "
                    "production model); each API key is accounted as one project bucket"
                ),
                "groq_fleet_tokens_per_minute": GROQ_FLEET_TPM_LIMIT,
                "groq_basis": "operator-observed fleet-wide ceiling across all Groq keys, rolling 60 seconds",
                "warning_fraction": WARN_FRACTION,
            },
            "providers": providers,
            "warnings": warnings,
            "any_warning": any_warning,
            "any_exhausted": any_exhausted,
            "coverage": coverage,
            "honesty": {
                "basis": (
                    "Counts are provider attempts made through this Inference process since the "
                    "ledger started, plus today's JSONL events replayed after a restart. Usage of "
                    "the same keys by other clients (e.g. FRIDAY's own direct pool) is not visible "
                    "here. Unmeasured token counts are reported as null, never as zero."
                )
            },
        }


#: Process-wide singleton; the gateway records into this instance.
quota_ledger = QuotaLedger()
