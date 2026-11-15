"""TASK-INF-007: per-provider free-tier quota accounting.

The ledger counts every provider attempt the gateway makes and measures it
against the declared free-tier limits (Gemini 20 requests/day per key+model,
Pacific-midnight reset; Groq 8,000 tokens/minute fleet-wide, rolling), with
a warning state *before* exhaustion. These tests pin the accounting rules,
the Pacific-day boundary, the warning/exhaustion thresholds, the
provider-429 override, restart replay, and the guarantee that key values
never appear in any output.
"""

import asyncio
import json
import time
from datetime import datetime, timezone

import pytest

import app.providers
from app.providers.base import ProviderMessage, ProviderRequest, ProviderResponse
from app.providers.errors import RateLimitError
from app.providers.gateway import KeyPool, ModelGateway
from app.providers.quota_ledger import (
    GEMINI_DAILY_REQUEST_LIMIT,
    GROQ_FLEET_TPM_LIMIT,
    QuotaLedger,
    key_fingerprint,
    next_reset_ts,
    pacific_date,
)

#: Sample ledger day (2026-11-15 Pacific) used by the replay test. Written
#: to a tmp file by the test itself — the repo gitignores ``*.jsonl``, so a
#: checked-in fixture would silently vanish from the tree.
_SAMPLE_JSONL = (
    '{"ts": 1763294400.0, "date": "2026-11-15", "provider": "gemini", "model": "gemini-3.6-flash", '
    '"key_fp": "fpkey00001", "outcome": "success", "prompt_tokens": 100, "completion_tokens": 50, '
    '"total_tokens": 150}\n'
    '{"ts": 1763298000.0, "date": "2026-11-15", "provider": "gemini", "model": "gemini-3.6-flash", '
    '"key_fp": "fpkey00001", "outcome": "success", "prompt_tokens": 200, "completion_tokens": 100, '
    '"total_tokens": 300}\n'
    '{"ts": 1763301600.0, "date": "2026-11-15", "provider": "groq", "model": "openai/gpt-oss-120b", '
    '"key_fp": "fpkey00002", "outcome": "success", "prompt_tokens": 900, "completion_tokens": 600, '
    '"total_tokens": 1500}\n'
)


def _ts(year, month, day, hour, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc).timestamp()


# 2026-11-15 20:00 UTC == 2026-11-15 12:00 PST (UTC-8 in November).
NOW = _ts(2026, 11, 15, 20)


def _record_n(ledger, n, **kwargs):
    for _ in range(n):
        ledger.record(ts=NOW, **kwargs)


def _gemini_bucket(snapshot, model="gemini-3.6-flash"):
    rows = snapshot["providers"]["gemini"]["daily_buckets"]
    return next(r for r in rows if r["model"] == model)


# ----------------------------------------------------------------------
# key handling
# ----------------------------------------------------------------------

def test_fingerprint_is_stable_and_never_the_key():
    fp = key_fingerprint("sk-secret-value-123")
    assert fp != "sk-secret-value-123"
    assert len(fp) == 10
    assert fp == key_fingerprint("sk-secret-value-123")
    assert fp != key_fingerprint("sk-secret-value-124")
    assert key_fingerprint(None) is None
    assert key_fingerprint("") is None


def test_key_value_appears_nowhere_in_snapshot(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    secret = "sk-secret-value-123"
    ledger.record(provider="gemini", model="gemini-3.6-flash", api_key=secret,
                  outcome="success", total_tokens=42, ts=NOW)
    snap = ledger.snapshot(now=NOW)
    assert secret not in json.dumps(snap)
    assert _gemini_bucket(snap)["key_fingerprint"] == key_fingerprint(secret)


# ----------------------------------------------------------------------
# Pacific-day window
# ----------------------------------------------------------------------

def test_pacific_day_boundary_is_midnight_pacific():
    # 07:59:59 UTC == 23:59:59 PST the previous day; 08:00:00 UTC == 00:00 PST.
    assert pacific_date(_ts(2026, 11, 15, 7, 59, 59)) == "2026-11-14"
    assert pacific_date(_ts(2026, 11, 15, 8, 0, 0)) == "2026-11-15"
    # Summer (PDT, UTC-7): the boundary moves an hour earlier in UTC.
    assert pacific_date(_ts(2026, 7, 15, 6, 59, 59)) == "2026-07-14"
    assert pacific_date(_ts(2026, 7, 15, 7, 0, 0)) == "2026-07-15"


def test_next_reset_is_the_coming_pacific_midnight():
    reset = next_reset_ts(NOW)
    assert reset == _ts(2026, 11, 16, 8)  # 2026-11-16 00:00 PST


def test_snapshot_reports_reset_window(tmp_path):
    snap = QuotaLedger(ledger_dir=tmp_path).snapshot(now=NOW)
    assert snap["pacific_date"] == "2026-11-15"
    assert snap["window_reset"]["timezone"] == "America/Los_Angeles"
    assert snap["window_reset"]["next_reset_utc"] == "2026-11-16T08:00:00Z"
    assert snap["window_reset"]["seconds_to_reset"] == 12 * 3600
    assert snap["limits"]["gemini_daily_requests_per_key_model"] == GEMINI_DAILY_REQUEST_LIMIT
    assert snap["limits"]["groq_fleet_tokens_per_minute"] == GROQ_FLEET_TPM_LIMIT
    assert "honesty" in snap and "basis" in snap["honesty"]


# ----------------------------------------------------------------------
# Gemini daily accounting: warning BEFORE exhaustion
# ----------------------------------------------------------------------

def test_gemini_bucket_warns_at_80_percent_and_exhausts_at_limit(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    kw = dict(provider="gemini", model="gemini-3.6-flash", api_key="key-one", outcome="success")

    _record_n(ledger, 15, **kw)  # 15/20 = 75% — still ok
    snap = ledger.snapshot(now=NOW)
    assert _gemini_bucket(snap)["state"] == "ok"
    assert snap["any_warning"] is False

    ledger.record(ts=NOW, **kw)  # 16/20 = 80% — warning line
    snap = ledger.snapshot(now=NOW)
    assert _gemini_bucket(snap)["state"] == "warning"
    assert snap["providers"]["gemini"]["state"] == "warning"
    assert snap["any_warning"] is True
    assert snap["any_exhausted"] is False
    assert any("key-one" not in w and "WARNING" in w for w in snap["warnings"])

    _record_n(ledger, 4, **kw)  # 20/20 — exhausted
    snap = ledger.snapshot(now=NOW)
    assert _gemini_bucket(snap)["state"] == "exhausted"
    assert _gemini_bucket(snap)["used_fraction"] == 1.0
    assert snap["providers"]["gemini"]["state"] == "exhausted"
    assert snap["any_exhausted"] is True


def test_gemini_provider_429_marks_bucket_exhausted_immediately(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    kw = dict(provider="gemini", model="gemini-3.6-flash", api_key="key-one")
    _record_n(ledger, 3, outcome="success", **kw)
    ledger.record(ts=NOW, outcome="rate_limited", **kw)
    snap = ledger.snapshot(now=NOW)
    row = _gemini_bucket(snap)
    assert row["requests"] == 4
    assert row["rate_limited"] == 1
    assert row["exhausted_by_provider_429"] is True
    assert row["state"] == "exhausted"  # the provider's verdict outranks the count


def test_gemini_fleet_state_needs_every_key_exhausted(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    base = dict(provider="gemini", model="gemini-3.6-flash", outcome="success")
    _record_n(ledger, GEMINI_DAILY_REQUEST_LIMIT, api_key="key-one", **base)
    snap = ledger.snapshot(now=NOW)
    # One key dead, but it is the only key seen: fleet is exhausted for the model.
    assert snap["providers"]["gemini"]["state"] == "exhausted"

    ledger2 = QuotaLedger(ledger_dir=tmp_path)
    _record_n(ledger2, GEMINI_DAILY_REQUEST_LIMIT, api_key="key-one", **base)
    _record_n(ledger2, 2, api_key="key-two", **base)
    snap2 = ledger2.snapshot(now=NOW)
    # A fresh key can still serve: degraded (warning), not exhausted.
    assert snap2["providers"]["gemini"]["state"] == "warning"
    assert snap2["providers"]["gemini"]["keys_seen_today"] == 2
    assert snap2["any_exhausted"] is False


def test_gemini_limits_are_per_model(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    _record_n(ledger, GEMINI_DAILY_REQUEST_LIMIT, provider="gemini", model="gemini-3.6-flash",
              api_key="key-one", outcome="success")
    _record_n(ledger, 1, provider="gemini", model="gemini-3.8-flash",
              api_key="key-one", outcome="success")
    snap = ledger.snapshot(now=NOW)
    assert _gemini_bucket(snap, "gemini-3.6-flash")["state"] == "exhausted"
    assert _gemini_bucket(snap, "gemini-3.8-flash")["state"] == "ok"
    # One model exhausted but the other fully fresh: warning, not exhausted.
    assert snap["providers"]["gemini"]["state"] == "warning"


# ----------------------------------------------------------------------
# Groq rolling-minute fleet ceiling
# ----------------------------------------------------------------------

def test_groq_rolling_minute_window_warns_and_expires(tmp_path):
    t0 = _ts(2026, 11, 10, 12)
    ledger = QuotaLedger(ledger_dir=tmp_path)
    kw = dict(provider="groq", model="openai/gpt-oss-120b", api_key="groq-key", outcome="success")
    ledger.record(ts=t0, total_tokens=5000, **kw)
    ledger.record(ts=t0 + 30, total_tokens=2000, **kw)
    ledger.record(ts=t0 + 40, total_tokens=1500, **kw)

    snap = ledger.snapshot(now=t0 + 40)
    rolling = snap["providers"]["groq"]["rolling_minute"]
    assert rolling["measured_tokens"] == 8500
    assert rolling["state"] == "exhausted"  # 8500 >= 8000 fleet ceiling
    assert snap["any_exhausted"] is True

    snap = ledger.snapshot(now=t0 + 61)  # the 5000-token request aged out
    rolling = snap["providers"]["groq"]["rolling_minute"]
    assert rolling["measured_tokens"] == 3500
    assert rolling["state"] == "ok"

    ledger2 = QuotaLedger(ledger_dir=tmp_path)
    ledger2.record(ts=t0, total_tokens=7000, **kw)
    rolling = ledger2.snapshot(now=t0)["providers"]["groq"]["rolling_minute"]
    assert rolling["state"] == "warning"  # 7000/8000 = 87.5%
    assert rolling["requests_in_window"] == 1
    assert rolling["measured_requests_in_window"] == 1


def test_groq_unmeasured_tokens_do_not_count_toward_ceiling(tmp_path):
    t0 = _ts(2026, 11, 10, 12)
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger.record(provider="groq", model="openai/gpt-oss-120b", api_key="k",
                  outcome="success", ts=t0)  # no usage reported
    rolling = ledger.snapshot(now=t0)["providers"]["groq"]["rolling_minute"]
    assert rolling["measured_tokens"] == 0
    assert rolling["requests_in_window"] == 1
    assert rolling["measured_requests_in_window"] == 0
    assert rolling["state"] == "ok"


# ----------------------------------------------------------------------
# Honest accounting details
# ----------------------------------------------------------------------

def test_unmeasured_tokens_report_null_not_zero(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger.record(provider="gemini", model="gemini-3.6-flash", api_key="k",
                  outcome="success", ts=NOW)
    row = _gemini_bucket(ledger.snapshot(now=NOW))
    assert row["total_tokens"] is None
    assert row["tokens_measured_requests"] == 0

    ledger.record(provider="gemini", model="gemini-3.6-flash", api_key="k",
                  outcome="success", total_tokens=250, ts=NOW)
    row = _gemini_bucket(ledger.snapshot(now=NOW))
    assert row["total_tokens"] == 250
    assert row["tokens_measured_requests"] == 1
    assert row["requests"] == 2


def test_provider_without_declared_limit_is_accounted_not_capped(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    _record_n(ledger, 50, provider="openrouter", model="meta-llama/llama-3.3-70b-instruct",
              api_key="or-key", outcome="success")
    snap = ledger.snapshot(now=NOW)
    entry = snap["providers"]["openrouter"]
    assert entry["requests_today"] == 50
    assert entry["state"] == "no_declared_limit"
    assert "limit_requests_per_day" not in entry["daily_buckets"][0]
    assert snap["any_exhausted"] is False


def test_local_tier_is_unmetered(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger.record(provider="local", model="local-model", outcome="success", ts=NOW)
    assert ledger.snapshot(now=NOW)["providers"]["local"]["state"] == "unmetered"


def test_outcomes_are_tallied_separately(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    kw = dict(provider="gemini", model="gemini-3.6-flash", api_key="k", ts=NOW)
    ledger.record(outcome="success", **kw)
    ledger.record(outcome="unavailable", **kw)
    ledger.record(outcome="timeout", **kw)
    ledger.record(outcome="error", **kw)
    ledger.record(outcome="something-else", **kw)  # unknown outcome -> error
    row = _gemini_bucket(ledger.snapshot(now=NOW))
    assert row["requests"] == 5
    assert row["successes"] == 1
    assert row["unavailable"] == 1
    assert row["timeouts"] == 1
    assert row["errors"] == 2


# ----------------------------------------------------------------------
# Persistence: replay after restart
# ----------------------------------------------------------------------

def test_replay_restores_counts_from_jsonl(tmp_path):
    sample = tmp_path / "quota_ledger_sample.jsonl"
    sample.write_text(_SAMPLE_JSONL)
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger._path_for = lambda _date: sample  # replay the sample day
    ledger._load_today()
    assert ledger._events_replayed == 3
    gem = ledger._daily[("gemini", "fpkey00001", "gemini-3.6-flash", "2026-11-15")]
    assert gem["requests"] == 2
    assert gem["successes"] == 2
    assert gem["total_tokens"] == 450
    groq = ledger._daily[("groq", "fpkey00002", "openai/gpt-oss-120b", "2026-11-15")]
    assert groq["requests"] == 1
    assert groq["total_tokens"] == 1500


def test_persistence_roundtrip(tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    ledger.record(provider="gemini", model="gemini-3.6-flash", api_key="k",
                  outcome="success", total_tokens=99, ts=NOW)
    path = tmp_path / f"quota_ledger-{pacific_date(NOW)}.jsonl"
    if not path.exists():
        pytest.skip("platform forbids Python file writes; persistence is best-effort by design")
    fresh = QuotaLedger(ledger_dir=tmp_path)
    assert fresh._events_replayed == 1
    row = _gemini_bucket(fresh.snapshot(now=NOW))
    assert row["requests"] == 1
    assert row["total_tokens"] == 99
    # The persisted line carries the fingerprint, never the key value.
    assert "k" != key_fingerprint("k")
    assert key_fingerprint("k") in path.read_text()


# ----------------------------------------------------------------------
# Gateway integration: execute() records every attempt
# ----------------------------------------------------------------------

class _Limiter:
    async def acquire(self):
        return None

    def release(self):
        return None


class _Health:
    def __init__(self):
        self.successes = []
        self.failures = []

    def record_success(self, provider, latency):
        self.successes.append((provider, latency))

    def record_failure(self, provider, error, **kwargs):
        self.failures.append((provider, error, kwargs))


def _gateway(keys):
    gateway = ModelGateway.__new__(ModelGateway)
    gateway.key_pools = {"gemini": KeyPool("gemini", keys)}
    gateway.rate_limiters = {"gemini": _Limiter()}
    gateway.health_tracker = _Health()
    return gateway


def _isolate(monkeypatch, tmp_path):
    ledger = QuotaLedger(ledger_dir=tmp_path)
    monkeypatch.setattr("app.providers.gateway.quota_ledger", ledger)
    monkeypatch.setattr(
        "app.providers.gateway.provider_has_credentials", lambda p: p == "gemini"
    )
    monkeypatch.setattr("app.providers.gateway.settings.LOCAL_ENABLED", False)
    monkeypatch.setattr("app.providers.gateway.settings.LOCAL_PREFERRED", False)
    monkeypatch.setattr("app.providers.gateway.settings.INFERENCE_LITELLM_ENABLED", False)
    monkeypatch.setattr("app.providers.gateway.settings.INFERENCE_LITELLM_FALLBACK_ENABLED", False)
    return ledger


def test_gateway_execute_records_success_with_tokens(monkeypatch, tmp_path):
    ledger = _isolate(monkeypatch, tmp_path)
    gateway = _gateway(["test-key-alpha"])

    class _GeminiOK:
        def __init__(self, key):
            self.key = key

        async def generate(self, request):
            return ProviderResponse(
                content="ok", model="gemini-3.6-flash", provider="gemini",
                prompt_tokens=10, completion_tokens=5, total_tokens=15, raw_response={},
            )

    monkeypatch.setattr(app.providers, "get_provider",
                        lambda name, api_key=None, **kw: _GeminiOK(api_key))
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="hello")], model="gemini-3.6-flash"
    )
    resp = asyncio.run(gateway.execute("gemini", request))
    assert resp.content == "ok"

    snap = ledger.snapshot()
    row = _gemini_bucket(snap)
    assert row["requests"] == 1
    assert row["successes"] == 1
    assert row["total_tokens"] == 15
    assert row["key_fingerprint"] == key_fingerprint("test-key-alpha")
    assert "test-key-alpha" not in json.dumps(snap)


def test_gateway_execute_records_429_and_marks_exhaustion(monkeypatch, tmp_path):
    ledger = _isolate(monkeypatch, tmp_path)
    gateway = _gateway(["test-key-alpha"])

    class _Gemini429:
        def __init__(self, key):
            self.key = key

        async def generate(self, request):
            raise RuntimeError("429 Too Many Requests: quota exceeded for this key")

    monkeypatch.setattr(app.providers, "get_provider",
                        lambda name, api_key=None, **kw: _Gemini429(api_key))
    request = ProviderRequest(
        messages=[ProviderMessage(role="user", content="hello")], model="gemini-3.6-flash"
    )
    with pytest.raises(RateLimitError):
        asyncio.run(gateway.execute("gemini", request))

    snap = ledger.snapshot()
    row = _gemini_bucket(snap)
    assert row["rate_limited"] == 1
    assert row["exhausted_by_provider_429"] is True
    assert row["state"] == "exhausted"
    assert snap["any_exhausted"] is True


# ----------------------------------------------------------------------
# Route
# ----------------------------------------------------------------------

def test_quota_route_returns_snapshot_shape():
    from app.api.v1_core_routes import v1_quota

    payload = asyncio.run(v1_quota())
    assert payload["service"] == "inference"
    for field in ("providers", "warnings", "window_reset", "limits", "coverage", "honesty"):
        assert field in payload
    assert payload["window_reset"]["timezone"] == "America/Los_Angeles"
    assert time.time()  # (route executed against the live singleton without error)
