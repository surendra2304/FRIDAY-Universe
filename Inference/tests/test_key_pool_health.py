"""TASK-INF-003: per-key pool health monitor.

Covers the three guarantees the monitor exists for:
(1) third-party keys are collected/reported as their own pool and are
    never merged into the primary counts;
(2) reports contain fingerprints/counts only — a raw key value can
    never appear in text, JSON, or a report object;
(3) dead vs exhausted vs transient classification matches what the
    providers actually return (401/403/invalid -> dead, 429/402 ->
    exhausted, 5xx/timeout -> transient).
"""

import asyncio
import json

import pytest

from app.core import key_pool_health as kph


class FakeSettings:
    GEMINI_API_KEY = "gemini-primary-a"
    GEMINI_API_KEYS = "gemini-primary-b, gemini-primary-a"  # dup within bucket
    GROQ_API_KEY = "groq-primary-a"
    GROQ_API_KEYS = None
    OPENROUTER_API_KEY = None
    OPENROUTER_API_KEYS = "or-primary-a,or-primary-b"
    THIRD_PARTY_GEMINI_KEY = "tp-gemini-a"
    THIRD_PARTY_GEMINI_KEYS = "tp-gemini-b"
    THIRD_PARTY_GROQ_KEY = "tp-groq-a"
    THIRD_PARTY_GROQ_KEYS = None
    THIRD_PARTY_OPENROUTER_KEY = None
    THIRD_PARTY_OPENROUTER_KEYS = None
    GEMINI_FALLBACK_KEY = "gemini-fallback-a"
    GEMINI_FALLBACK_KEYS = None
    GROQ_FALLBACK_KEY = None
    GROQ_FALLBACK_KEYS = None
    OPENROUTER_FALLBACK_KEY = None
    OPENROUTER_FALLBACK_KEYS = None
    THIRD_PARTY_FALLBACK_API_KEY = "tp-gemini-legacy"

    # The routing view merges buckets; the monitor must not use it.
    def get_provider_keys(self, provider):  # pragma: no cover - tripwire
        raise AssertionError("monitor must not use the merged routing view")


ALL_FAKE_KEYS = [
    "gemini-primary-a",
    "gemini-primary-b",
    "groq-primary-a",
    "or-primary-a",
    "or-primary-b",
    "tp-gemini-a",
    "tp-gemini-b",
    "tp-groq-a",
    "gemini-fallback-a",
    "tp-gemini-legacy",
]


def _entries():
    return kph.collect_key_pools(FakeSettings())


def test_collect_keeps_third_party_separate_and_dedupes_within_bucket():
    entries = _entries()
    by_pool = {}
    for e in entries:
        by_pool.setdefault((e.provider, e.pool), []).append(e)

    # gemini primary: plural (b, a) + singular (a, already seen) -> 2
    assert len(by_pool[("gemini", "primary")]) == 2
    # gemini third_party: singular + plural + legacy fallback var -> 3
    assert len(by_pool[("gemini", "third_party")]) == 3
    assert {e.source for e in by_pool[("gemini", "third_party")]} == {
        "THIRD_PARTY_GEMINI_KEY",
        "THIRD_PARTY_GEMINI_KEYS",
        "THIRD_PARTY_FALLBACK_API_KEY",
    }
    assert len(by_pool[("gemini", "fallback")]) == 1
    assert len(by_pool[("groq", "primary")]) == 1
    assert len(by_pool[("groq", "third_party")]) == 1
    assert len(by_pool[("openrouter", "primary")]) == 2
    assert ("openrouter", "third_party") not in by_pool
    assert len(entries) == 10


def test_fingerprint_is_truncated_hash_not_the_key():
    fp = kph.fingerprint_key("gemini-primary-a")
    assert fp.startswith("sha256:") and len(fp) == len("sha256:") + 12
    assert "gemini" not in fp and "primary" not in fp
    assert fp == kph.fingerprint_key("gemini-primary-a")
    assert fp != kph.fingerprint_key("gemini-primary-b")


def test_cross_pool_duplicate_is_flagged_by_fingerprint():
    class DupSettings(FakeSettings):
        THIRD_PARTY_GROQ_KEY = "groq-primary-a"  # same key, second pool

    dups = kph.find_cross_pool_duplicates(kph.collect_key_pools(DupSettings()))
    assert len(dups) == 1
    assert dups[0]["pools"] == ["groq:primary", "groq:third_party"]
    assert "groq-primary-a" not in json.dumps(dups)


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (200, "{}", kph.KeyStatus.LIVE),
        (401, "{}", kph.KeyStatus.DEAD),
        (403, "{}", kph.KeyStatus.DEAD),
        (400, '{"error":{"status":"INVALID_ARGUMENT","message":"API key not valid"}}', kph.KeyStatus.DEAD),
        (400, '{"error":{"code":400}}', kph.KeyStatus.UNKNOWN),
        (429, '{"error":{"status":"RESOURCE_EXHAUSTED"}}', kph.KeyStatus.EXHAUSTED),
        (402, "{}", kph.KeyStatus.EXHAUSTED),
        (503, "{}", kph.KeyStatus.TRANSIENT),
        (500, "{}", kph.KeyStatus.TRANSIENT),
        (None, None, kph.KeyStatus.TRANSIENT),
        (418, "{}", kph.KeyStatus.UNKNOWN),
    ],
)
def test_classify_response(status, body, expected):
    got, detail = kph.classify_response("gemini", status, body)
    assert got == expected
    assert "gemini-primary" not in detail


class FakeTransport:
    """Answers by the credential presented, like the real providers."""

    RESPONSES = {
        "gemini-primary-a": (200, '{"models":[]}'),
        "gemini-primary-b": (400, '{"error":{"message":"API key not valid. Please pass a valid API key.","status":"INVALID_ARGUMENT"}}'),
        "groq-primary-a": (429, '{"error":{"code":"rate_limit_exceeded"}}'),
        "or-primary-a": (200, '{"data":{"limit":null}}'),
        "or-primary-b": (401, '{"error":{"message":"User not found."}}'),
        "tp-gemini-a": (200, '{"models":[]}'),
        "tp-gemini-b": (503, '{"error":{"status":"UNAVAILABLE"}}'),
        "tp-groq-a": (200, '{"data":[]}'),
        "gemini-fallback-a": (403, '{"error":{"status":"PERMISSION_DENIED"}}'),
        "tp-gemini-legacy": (200, '{"models":[]}'),
    }

    async def get(self, url, headers):
        presented = next(iter(headers.values())).removeprefix("Bearer ")
        if presented == "or-primary-b":
            raise TimeoutError("simulated timeout is exercised elsewhere")
        return self.RESPONSES[presented]


def test_probe_report_counts_statuses_and_never_leaks_keys():
    report = asyncio.run(kph.probe_entries(_entries(), FakeTransport()))
    totals = report.totals()
    assert totals["total"] == 10
    assert totals["live"] == 5  # gemini-a, tp-gemini-a, tp-groq, or-a, tp-legacy
    assert totals["dead"] == 2  # gemini-b (400 invalid), gemini-fallback (403)
    assert totals["exhausted"] == 1  # groq-primary (429)
    assert totals["transient"] == 2  # tp-gemini-b (503), or-b (timeout)

    pools = {(p.provider, p.pool): p for p in report.pools}
    assert pools[("gemini", "primary")].live == 1
    assert pools[("gemini", "primary")].dead == 1
    assert pools[("gemini", "third_party")].live == 2
    assert pools[("gemini", "third_party")].transient == 1
    assert pools[("groq", "primary")].exhausted == 1

    rendered = kph.render_text(report) + json.dumps(report.to_dict())
    for raw in ALL_FAKE_KEYS:
        assert raw not in rendered
    assert "sha256:" in rendered


def test_inventory_report_marks_everything_not_probed():
    report = kph.inventory_report(_entries())
    assert report.probed is False
    assert report.totals()["not_probed"] == 10
    assert "INVENTORY ONLY" in kph.render_text(report)


def test_cli_inventory_only_exit_zero_and_no_key_values(monkeypatch, capsys):
    monkeypatch.setattr(kph, "settings", FakeSettings())
    assert kph.main(["--inventory-only"]) == 0
    out = capsys.readouterr().out
    assert "GEMINI primary: total=2" in out
    assert "GEMINI third_party: total=3" in out
    for raw in ALL_FAKE_KEYS:
        assert raw not in out


def test_empty_config_reports_zero_pools():
    class Empty:
        pass

    assert kph.collect_key_pools(Empty()) == []
    report = kph.inventory_report([])
    assert report.totals()["total"] == 0
    assert report.pools == []
