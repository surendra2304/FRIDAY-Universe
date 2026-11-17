"""TASK-VOI-005 — Gemini key resolution must survive a bad probe window.

Owner live voice test #2, 2026-11-15 02:30 IST (FRIDAY-Voice journal,
job AJ_kEpwTnRbRaPn, room friday-7947e18b): the owner was served by the
Groq pipeline — Whisper STT + gpt-oss-120b + EdgeTTS — and described it
as "like Google voice search". Gemini was never attempted: the key
resolution round ended "no valid key among 3 candidates" without ONE
probe verdict ever being logged. The pre-fix round gave the first
candidate the whole shared deadline and BROKE on a timeout, so a single
slow/hung probe condemned the job; the same failure had already killed
the boot warm-up three hours earlier (23:43:49, "no valid key among 1
candidates"), and nothing ever re-resolved in the background.

These tests pin the rework:

- each candidate gets its own bounded budget; a timeout marks the
  candidate unjudged and the round CONTINUES;
- a transport failure is inconclusive (the key is unjudged), distinct
  from an auth rejection (the key is dead);
- if nothing verifies but something was unjudged, the first unjudged
  candidate comes back as a TENTATIVE key — never cached as verified,
  never negative-cached — so the Live session (and the TASK-VOI-004
  recovery ladder behind it) judges the key instead of the probe
  window judging the whole call;
- the candidate set is every pool key, healthy first — a key benched
  by the chat path's quota accounting is still a voice candidate;
- the background key keeper resolves while keyless and stands down
  while a verified key is fresh.

TASK-VOI-009 note (2026-11-15): the Groq pipeline that served the
owner on that call has since been deleted by owner directive; the one
test below that pinned its STT language was converted to assert the
pipeline's absence. The key-resolution contract above is unchanged —
with no fallback left, it is now the only thing between a call and
the recorded unavailable notice.
"""

import asyncio
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as worker  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_key_cache():
    saved = dict(worker._KEY_CACHE)
    saved_quota = dict(worker._KEY_QUOTA_COOLDOWN_UNTIL)
    worker._KEY_CACHE.update(
        {
            "key": None,
            "ts": 0.0,
            "failed_ts": 0.0,
            "tentative_key": None,
            "tentative_ts": 0.0,
        }
    )
    worker._KEY_QUOTA_COOLDOWN_UNTIL.clear()
    yield
    worker._KEY_CACHE.clear()
    worker._KEY_CACHE.update(saved)
    worker._KEY_QUOTA_COOLDOWN_UNTIL.clear()
    worker._KEY_QUOTA_COOLDOWN_UNTIL.update(saved_quota)


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# A slow probe can no longer kill the round (the 2026-11-15 defect)
# ---------------------------------------------------------------------------


def test_probe_timeout_moves_to_next_candidate(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["slow-key", "good-key"])
    monkeypatch.setattr(worker, "_KEY_PROBE_PER_CANDIDATE_S", 0.2)
    calls = []

    def fake_probe(key):
        calls.append(key)
        if key == "slow-key":
            time.sleep(2.0)  # outlives its per-candidate budget
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["slow-key", "good-key"]
    assert worker._cached_gemini_key() == "good-key"


def test_inconclusive_probe_moves_to_next_candidate(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["dark-key", "good-key"])
    calls = []

    def fake_probe(key):
        calls.append(key)
        if key == "dark-key":
            raise worker._ProbeInconclusive("connecterror: connection reset")
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["dark-key", "good-key"]
    # a verified key clears any tentative bookkeeping
    assert worker._cached_tentative_key() is None


# ---------------------------------------------------------------------------
# Tentative keys: unjudged is not dead, and not verified either
# ---------------------------------------------------------------------------


def test_all_inconclusive_returns_tentative_not_verified(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2"])
    calls = []

    def inconclusive(key):
        calls.append(key)
        raise worker._ProbeInconclusive("readtimeout")

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", inconclusive)
    assert _run(worker._gemini_best_key()) == "k1"
    # offered, but NOT as a verified key, and NOT negative-cached
    assert worker._cached_gemini_key() is None
    assert worker._cached_tentative_key() == "k1"
    assert worker._KEY_CACHE["failed_ts"] == 0.0
    # a second job inside the tentative window reuses it without probing
    calls.clear()
    assert _run(worker._gemini_best_key()) == "k1"
    assert calls == []


def test_all_auth_rejected_is_a_hard_failure(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2"])
    monkeypatch.setattr(worker, "_probe_gemini_key_sync", lambda k: False)
    assert _run(worker._gemini_best_key()) is None
    assert worker._cached_tentative_key() is None
    assert worker._KEY_CACHE["failed_ts"] != 0.0  # negative cache earned


class _FakeLiveCM:
    """Async context manager standing in for a Gemini Live connect."""

    def __init__(self, exc=None):
        self._exc = exc

    async def __aenter__(self):
        if self._exc is not None:
            raise self._exc
        return SimpleNamespace()

    async def __aexit__(self, *args):
        return False


class _FakeGenaiClient:
    """Stands in for google.genai.Client: the probe's text stage
    fails via .models, its Live stage via .aio.live.connect — each
    stage's failure is set independently. Every stage invocation is
    recorded in .calls as (stage, model) so tests can assert which
    stage ran and which model it judged."""

    def __init__(self, models_exc=None, live_exc=None):
        self._models_exc = models_exc
        self._live_exc = live_exc
        self.calls = []

    @property
    def models(self):
        if self._models_exc is not None:
            raise self._models_exc

        def _generate_content(**kwargs):
            self.calls.append(("text", kwargs.get("model")))
            return SimpleNamespace()

        return SimpleNamespace(generate_content=_generate_content)

    @property
    def aio(self):
        def _connect(model=None, config=None):
            self.calls.append(("live", model))
            return _FakeLiveCM(self._live_exc)

        live = SimpleNamespace(connect=_connect)
        return SimpleNamespace(live=live)


def _patch_genai_client(monkeypatch, **kwargs):
    import google.genai as genai

    created = []

    def _factory(api_key):
        client = _FakeGenaiClient(**kwargs)
        created.append(client)
        return client

    monkeypatch.setattr(genai, "Client", _factory)
    return created


def test_probe_classifies_transport_errors_as_inconclusive(monkeypatch):
    """The probe itself: a connection-class failure raises
    _ProbeInconclusive; an auth failure counts as key-dead; a
    text-stage API answer that is neither auth, quota nor transport
    (a 503) falls through to the Live stage, whose connect decides —
    2026-11-17 key-probe fix: the pre-fix probe counted any such
    answer, a 429 included, as key-valid without ever judging Live
    availability."""
    _patch_genai_client(
        monkeypatch, models_exc=ConnectionError("connection reset by peer")
    )
    with pytest.raises(worker._ProbeInconclusive):
        worker._probe_gemini_key_sync("k")

    _patch_genai_client(monkeypatch, models_exc=RuntimeError("API_KEY_INVALID"))
    assert worker._probe_gemini_key_sync("k") is False

    # text stage answers 503 (the key authenticated); Live connects
    _patch_genai_client(
        monkeypatch, models_exc=RuntimeError("503 UNAVAILABLE: high demand")
    )
    assert worker._probe_gemini_key_sync("k") is True

    # text stage answers 503; the Live stage refuses for quota
    _patch_genai_client(
        monkeypatch,
        models_exc=RuntimeError("503 UNAVAILABLE: high demand"),
        live_exc=RuntimeError("429 RESOURCE_EXHAUSTED: you exceeded your current quota"),
    )
    with pytest.raises(worker._ProbeQuotaExhausted):
        worker._probe_gemini_key_sync("k")


def test_probe_text_quota_falls_through_to_live_stage(monkeypatch):
    """TASK-VOI-020: a 429 RESOURCE_EXHAUSTED from the probe's TEXT
    stage judges the TEXT bucket only — Gemini Live is metered
    separately (no daily cap), and the text bucket is a per-model
    daily allowance the keeper's own probing can drain. The probe
    now falls through to the Live stage, whose verdict governs.

    The TASK-VOI-018 invariant is preserved: the 429 itself certifies
    NOTHING — a key is valid here only because the Live connect
    actually succeeded. (This replaces the VOI-018 pin "a text-stage
    429 condemns the key and the Live stage is not consulted": that
    premise is the defect that killed re-acceptance #12, where all 5
    keys were condemned on the text bucket's exhaustion and no Live
    session was ever attempted.)"""
    # text quota-dead, Live connects -> certified BY THE LIVE STAGE
    created = _patch_genai_client(
        monkeypatch,
        models_exc=RuntimeError(
            "429 RESOURCE_EXHAUSTED: you exceeded your current quota"
        ),
    )
    assert worker._probe_gemini_key_sync("k") is True
    assert [stage for stage, _model in created[0].calls] == ["live"]

    # text quota-dead, Live also quota-dead -> condemned, as before
    _patch_genai_client(
        monkeypatch,
        models_exc=RuntimeError("429 RESOURCE_EXHAUSTED: quota"),
        live_exc=RuntimeError("429 RESOURCE_EXHAUSTED: quota"),
    )
    with pytest.raises(worker._ProbeQuotaExhausted):
        worker._probe_gemini_key_sync("k")

    # text quota-dead, Live auth-rejects -> the key is dead
    _patch_genai_client(
        monkeypatch,
        models_exc=RuntimeError("429 RESOURCE_EXHAUSTED: quota"),
        live_exc=RuntimeError("API_KEY_INVALID"),
    )
    assert worker._probe_gemini_key_sync("k") is False


def test_probe_auth_rejection_never_reaches_live_stage(monkeypatch):
    """Auth is a property of the key, not of a bucket: a stage-1 auth
    rejection condemns the key immediately — exactly as before
    TASK-VOI-020, the Live stage is not consulted."""
    created = _patch_genai_client(
        monkeypatch, models_exc=RuntimeError("API_KEY_INVALID")
    )
    assert worker._probe_gemini_key_sync("k") is False
    assert created[0].calls == []


def test_probe_stage1_pings_the_flash_lite_catalogue_model(monkeypatch):
    """TASK-VOI-020 (a): stage 1 draws on the Flash-Lite model's
    bucket (documented free tier ~500 requests/day), not the voice
    Flash model's (~20/day) — routine probing must not drain the
    scarce bucket. The id is the fleet catalogue's Flash-Lite
    (Inference SUPPORTED_MODELS)."""
    created = _patch_genai_client(monkeypatch)
    assert worker._probe_gemini_key_sync("k") is True
    assert created[0].calls[0] == ("text", "gemini-2.5-flash-lite")
    assert worker._PROBE_TEXT_MODEL == "gemini-2.5-flash-lite"


def test_verified_key_cache_ttl_is_thirty_minutes():
    """TASK-VOI-020 (c): the verified-key TTL is 1800 s (~7x fewer
    keeper probe rounds than the old 240 s), and the cache honours
    it — a key verified 5 minutes ago (dead under the old TTL) is
    still trusted; one verified 31 minutes ago is not."""
    assert worker._KEY_CACHE_TTL_S == 1800.0
    worker._KEY_CACHE.update({"key": "k1", "ts": time.time() - 300.0})
    assert worker._cached_gemini_key() == "k1"
    worker._KEY_CACHE.update({"key": "k1", "ts": time.time() - 1801.0})
    assert worker._cached_gemini_key() is None


def test_probe_live_stage_verdicts(monkeypatch):
    """With a clean text stage, the Live stage alone decides:
    connect -> valid; auth -> dead; transport -> unjudged."""
    _patch_genai_client(monkeypatch)
    assert worker._probe_gemini_key_sync("k") is True

    _patch_genai_client(monkeypatch, live_exc=RuntimeError("API_KEY_INVALID"))
    assert worker._probe_gemini_key_sync("k") is False

    _patch_genai_client(
        monkeypatch, live_exc=ConnectionError("connection reset by peer")
    )
    with pytest.raises(worker._ProbeInconclusive):
        worker._probe_gemini_key_sync("k")


# ---------------------------------------------------------------------------
# Candidate set: every pool key, healthy first
# ---------------------------------------------------------------------------


def test_pool_keys_include_benched_keys_healthy_first(monkeypatch):
    try:
        import importlib

        # importlib, not `from friday.auth import credential_pool`: the
        # package __init__ re-exports the singleton under the same name,
        # shadowing the submodule.
        pool_mod = importlib.import_module("friday.auth.credential_pool")
    except Exception:
        pytest.skip("credential pool not importable in this environment")

    class _Cred:
        def __init__(self, key, healthy):
            self.api_key = key
            self._healthy = healthy

        def is_healthy(self, *args):
            return self._healthy

    fake_pool = SimpleNamespace(
        credentials=[
            _Cred("benched-1", False),
            _Cred("healthy-1", True),
            _Cred("benched-2", False),
        ]
    )
    monkeypatch.setattr(pool_mod, "credential_pool", fake_pool)
    assert worker._gemini_pool_keys() == ["healthy-1", "benched-1", "benched-2"]


# ---------------------------------------------------------------------------
# Fallback pipeline STT: no per-utterance language re-detection
# ---------------------------------------------------------------------------


def test_groq_pipeline_is_gone_not_merely_pinned():
    """TASK-VOI-009 conversion of the VOI-005 STT-language pin.

    The test this replaces pinned the Groq pipeline's Whisper STT to
    English (detect_language=True had turned the owner's 'Hello' into
    Italian and his Telugu into Tamil script). The owner then ordered
    the pipeline itself removed — Gemini Live hears languages natively
    and is the only voice AI — so the pin's subject no longer exists.
    The converted assertion is the stronger one: the pipeline's whole
    surface (builder, key reader, plugin handle) is absent from the
    worker, so the garbling path can never run again. The full
    Gemini-only contract lives in test_voice_gemini_only.py."""
    for name in ("_try_groq_pipeline", "_groq_key", "_lk_groq", "GROQ_PLUGIN_AVAILABLE"):
        assert not hasattr(worker, name), f"worker still exposes {name}"


# ---------------------------------------------------------------------------
# The background key keeper
# ---------------------------------------------------------------------------


def test_keeper_step_resolves_when_keyless_then_stands_down(monkeypatch):
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1"])
    probes = []
    monkeypatch.setattr(worker, "_probe_gemini_key_sync", lambda k: probes.append(k) or True)
    assert worker._key_keeper_step() == "resolved"
    assert worker._cached_gemini_key() == "k1"
    assert worker._key_keeper_step() == "fresh"
    assert probes == ["k1"]  # the second step probed nothing


def test_keeper_step_reports_cooling_and_tentative(monkeypatch):
    worker._KEY_CACHE.update({"failed_ts": time.time()})
    assert worker._key_keeper_step() == "cooling"

    worker._KEY_CACHE.update({"failed_ts": 0.0})
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1"])

    def inconclusive(key):
        raise worker._ProbeInconclusive("connecterror")

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", inconclusive)
    assert worker._key_keeper_step() == "tentative"
    assert worker._cached_gemini_key() is None


# ---------------------------------------------------------------------------
# Quota verdicts: never valid, never tentative — cooled down (2026-11-17)
# ---------------------------------------------------------------------------


def test_quota_candidate_cooled_and_next_candidate_selected(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["quota-key", "good-key"])
    calls = []

    def fake_probe(key):
        calls.append(key)
        if key == "quota-key":
            raise worker._ProbeQuotaExhausted("429 resource_exhausted")
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", fake_probe)
    assert _run(worker._gemini_best_key()) == "good-key"
    assert calls == ["quota-key", "good-key"]
    # the verified key is the good one; the quota key is cooled, not cached
    assert worker._cached_gemini_key() == "good-key"
    assert worker._key_quota_cooling("quota-key")
    assert not worker._key_quota_cooling("good-key")


def test_all_quota_round_fails_and_cooldown_prevents_reprobing(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["q1", "q2"])
    calls = []

    def quota_probe(key):
        calls.append(key)
        raise worker._ProbeQuotaExhausted("429 resource_exhausted")

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", quota_probe)
    assert _run(worker._gemini_best_key()) is None
    # quota is a judgement: nothing verified, nothing tentative
    assert worker._cached_gemini_key() is None
    assert worker._cached_tentative_key() is None
    assert calls == ["q1", "q2"]
    # past the negative-cache window, cooled keys are skipped, not re-probed
    worker._KEY_CACHE["failed_ts"] = 0.0
    calls.clear()
    assert worker._resolve_gemini_key_sync() is None
    assert calls == []


def test_rotation_order_preserved_for_healthy_keys(monkeypatch):
    monkeypatch.setattr(worker, "GOOGLE_PLUGIN_AVAILABLE", True)
    monkeypatch.setattr(worker, "_gemini_pool_keys", lambda: ["k1", "k2", "k3"])
    calls = []

    def ok_probe(key):
        calls.append(key)
        return True

    monkeypatch.setattr(worker, "_probe_gemini_key_sync", ok_probe)
    assert _run(worker._gemini_best_key()) == "k1"
    assert calls == ["k1"]  # first healthy key wins; the rest are not probed
