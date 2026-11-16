"""TASK-REL-049: model-level servability tracking in Inference routing.

TASK-INF-005 measured gemini-3.8-flash serving 0 of 20 requests across
a full day on the production gateway — substituted every time, after a
~10–75s cascade — while the Gemini provider stayed healthy. All of the
gateway's outcome recording was provider-granular, so REL-043's
best-suitable selection (which filters on provider health) could not
see the failure and kept the model ranked #1 for chat.

These tests pin the overlay that fixes that:
- a model with 10 consecutive non-serves (substituted or failed, no
  intervening serve) is quarantined for selection — its REL-043 rank
  is untouched, it is simply not picked while it cannot serve;
- quarantine is per-MODEL: a sibling on the same provider still serves;
- a quarantined model gets a half-open probe every probe interval and
  re-enters on a real serve;
- a request naming a quarantined model is redirected through the same
  best-suitable selection, with the state disclosed in provenance;
- quarantine alone never refuses service (the unfiltered pool is the
  fallback when everything is quarantined);
- outcomes are recorded from the live route, and a replay of
  TASK-INF-005's recorded day (tests/fixtures/inf005_replay.json)
  quarantines gemini-3.8-flash and nothing else.
"""

import json
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.providers.model_servability import ModelServabilityTracker, model_servability_tracker

GEMINI_38 = "gemini-3.8-flash"
GEMINI_36 = "gemini-3.6-flash"
GPT_OSS = "openai/gpt-oss-120b"
RETIRED_70B = "llama-3.3-70b-versatile"
FIXTURE = Path(__file__).parent / "fixtures" / "inf005_replay.json"


# ---------------------------------------------------------------------------
# Tracker unit tests (fake clock)
# ---------------------------------------------------------------------------


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _tracker(clock, **kwargs):
    return ModelServabilityTracker(clock=clock, **kwargs)


def test_ten_consecutive_misses_quarantine():
    tracker = _tracker(_Clock())
    for _ in range(9):
        tracker.record_outcome(GEMINI_38, "substituted")
    assert not tracker.is_quarantined(GEMINI_38)
    tracker.record_outcome(GEMINI_38, "substituted")
    assert tracker.is_quarantined(GEMINI_38)
    view = tracker.selection_view(GEMINI_38)
    assert view["attempts"] == 10
    assert view["serves"] == 0
    assert view["consecutive_misses"] == 10
    assert view["quarantined"] is True


def test_failed_and_substituted_misses_both_count():
    tracker = _tracker(_Clock())
    for _ in range(5):
        tracker.record_outcome(GEMINI_38, "failed")
    for _ in range(4):
        tracker.record_outcome(GEMINI_38, "substituted")
    assert not tracker.is_quarantined(GEMINI_38)
    tracker.record_outcome(GEMINI_38, "failed")
    assert tracker.is_quarantined(GEMINI_38)


def test_a_serve_resets_the_streak():
    tracker = _tracker(_Clock())
    for _ in range(9):
        tracker.record_outcome(GEMINI_38, "substituted")
    tracker.record_outcome(GEMINI_38, "served")
    for _ in range(9):
        tracker.record_outcome(GEMINI_38, "substituted")
    # Flaky is not unservable: an intermittent server never quarantines.
    assert not tracker.is_quarantined(GEMINI_38)
    tracker.record_outcome(GEMINI_38, "substituted")
    assert tracker.is_quarantined(GEMINI_38)


def test_probe_cycle_rearms_then_a_serve_clears():
    clock = _Clock(t=1000.0)
    tracker = _tracker(clock, probe_interval_seconds=900.0)
    for _ in range(10):
        tracker.record_outcome(GEMINI_38, "failed")
    assert tracker.is_quarantined(GEMINI_38)
    assert not tracker.probe_due(GEMINI_38)  # just latched
    clock.t = 1000.0 + 899.0
    assert not tracker.probe_due(GEMINI_38)
    clock.t = 1000.0 + 900.0
    assert tracker.probe_due(GEMINI_38)
    # A failed probe re-arms the clock instead of clearing anything.
    tracker.record_outcome(GEMINI_38, "substituted")
    assert tracker.is_quarantined(GEMINI_38)
    assert not tracker.probe_due(GEMINI_38)
    clock.t = 1000.0 + 1800.0
    assert tracker.probe_due(GEMINI_38)
    # A serving probe clears the quarantine immediately.
    tracker.record_outcome(GEMINI_38, "served")
    assert not tracker.is_quarantined(GEMINI_38)
    assert tracker.selection_view(GEMINI_38)["quarantined"] is False


def test_window_prunes_old_events():
    clock = _Clock(t=0.0)
    tracker = _tracker(clock, window_seconds=100.0)
    tracker.record_outcome(GEMINI_38, "served")
    clock.t = 1000.0
    view = tracker.selection_view(GEMINI_38)
    assert view["attempts"] == 0
    assert view["serves"] == 0


def test_replay_of_inf005_recorded_day_quarantines_only_gemini_38():
    """Replay TASK-INF-005's measured day through the tracker.

    The fixture reduces the benchmark's raw records to per-model
    outcome sequences (S = served as requested, X = substituted) in
    run order, plus the explicit substitute lists for gemini-3.8-flash
    so the serving models are credited too.
    """
    data = json.loads(FIXTURE.read_text())
    tracker = _tracker(_Clock())

    def feed(model, outcomes, served_by=None):
        latched_at = None
        for i, outcome in enumerate(outcomes):
            if outcome == "S":
                tracker.record_outcome(model, "served")
            else:
                tracker.record_outcome(model, "substituted")
                if served_by is not None:
                    tracker.record_serve(served_by[i])
            if latched_at is None and tracker.is_quarantined(model):
                latched_at = i + 1
        return latched_at

    # Only gemini-3.8-flash was ever substituted in the recorded day.
    assert set(data["main_run_outcomes"]) == set(data["latency_pass_outcomes"])
    for model, outcomes in data["main_run_outcomes"].items():
        if model != GEMINI_38:
            assert set(outcomes) == {"S"}, f"fixture: {model} unexpectedly has misses"

    latched = feed(GEMINI_38, data["main_run_outcomes"][GEMINI_38], data["main_run_gemini_3_8_served_by"])
    assert latched == 10, "quarantine must latch on the 10th consecutive non-serve"
    for model, outcomes in data["main_run_outcomes"].items():
        if model != GEMINI_38:
            feed(model, outcomes)

    view = tracker.selection_view(GEMINI_38)
    assert view["attempts"] == 15
    assert view["serves"] == 0
    assert view["quarantined"] is True
    # The substitutes were credited with their serves.
    assert tracker.selection_view(GPT_OSS)["serves"] == 15 + 13
    assert tracker.selection_view(GEMINI_36)["serves"] == 15 + 2
    for model in data["main_run_outcomes"]:
        if model != GEMINI_38:
            assert not tracker.is_quarantined(model), model

    # Second window (latency pass): five more non-serves change nothing.
    feed(GEMINI_38, data["latency_pass_outcomes"][GEMINI_38], data["latency_pass_gemini_3_8_served_by"])
    for model, outcomes in data["latency_pass_outcomes"].items():
        if model != GEMINI_38:
            feed(model, outcomes)
    assert tracker.is_quarantined(GEMINI_38)
    assert tracker.selection_view(GEMINI_38)["attempts"] == 20
    # gpt-oss: 28 serves in the main window + 5 own serves and all 5 of
    # gemini-3.8-flash's substitute serves in the latency window.
    assert tracker.selection_view(GPT_OSS)["serves"] == 38


# ---------------------------------------------------------------------------
# Route-level tests (the REL-043 harness shape)
# ---------------------------------------------------------------------------


async def _post_chat(auth, payload):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        return await client.post("/v1/chat/completions", json=payload)


def _stub_execute(monkeypatch, degraded_models=()):
    """Recording double for the unified manager (as in REL-043's tests)."""
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append(req)
        if req.model in degraded_models:
            return UnifiedExecutionResponse(
                provider_used=req.provider,
                model_used=req.model or "none",
                agent_role=req.agent_role or "system_architect",
                content="",
                latency_ms=1.0,
                timestamp=1729000000.0,
                token_usage={},
                status="degraded",
                degraded=True,
                error=f"{req.provider}: provider unavailable (test double)",
            )
        return UnifiedExecutionResponse(
            provider_used=req.provider,
            model_used=req.model,
            agent_role=req.agent_role or "system_architect",
            content="OK",
            latency_ms=1.0,
            timestamp=1729000000.0,
            token_usage={"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
            finish_reason="stop",
        )

    monkeypatch.setattr(unified_provider_manager, "execute", stub)
    return calls


@pytest.fixture
def servability():
    """Isolate tests that seed the shared servability singleton."""
    model_servability_tracker.reset()
    yield model_servability_tracker
    model_servability_tracker.reset()


@pytest.fixture
def healthy_tracker():
    from app.providers.health import provider_health_tracker

    provider_health_tracker.reset()
    yield provider_health_tracker
    provider_health_tracker.reset()


def _quarantine(model, misses=10):
    for _ in range(misses):
        model_servability_tracker.record_outcome(model, "substituted")


def _kill_provider(tracker, provider):
    for _ in range(4):
        tracker.record_failure(provider, "quota exhausted (test double)", is_429=True)


@pytest.mark.asyncio
async def test_quarantined_top_pick_is_skipped_and_disclosed(auth, monkeypatch, servability, healthy_tracker):
    _quarantine(GEMINI_38)
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # The quarantined chat #1 is not attempted; the next-best serves.
    assert [c.model for c in calls] == [GPT_OSS]
    provenance = res.json()["provenance"]
    assert provenance["selected_model"] == GPT_OSS
    assert provenance["servability"]["probe"] is False
    assert provenance["servability"]["chosen"]["model"] == GPT_OSS
    alternates = provenance["servability"]["quarantined_alternates"]
    assert [a["model"] for a in alternates] == [GEMINI_38]
    assert alternates[0]["attempts"] == 10
    assert alternates[0]["serves"] == 0
    assert alternates[0]["quarantined"] is True


@pytest.mark.asyncio
async def test_sibling_on_the_same_provider_is_unaffected(auth, monkeypatch, servability, healthy_tracker):
    _quarantine(GEMINI_38)
    _kill_provider(healthy_tracker, "groq")
    _kill_provider(healthy_tracker, "openrouter")
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # Quarantine is per-MODEL: with Groq and OpenRouter health-dead, the
    # chat ranking falls to the Gemini sibling — gemini-3.6-flash serves
    # on the very provider whose other model is quarantined.
    assert [c.model for c in calls] == [GEMINI_36]
    assert res.json()["model"] == GEMINI_36


@pytest.mark.asyncio
async def test_named_quarantined_model_is_redirected_with_disclosure(
    auth, monkeypatch, servability, healthy_tracker
):
    _quarantine(GEMINI_38)
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": GEMINI_38, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # No wasted cascade into the quarantined model: the best suitable
    # available model answers directly, and provenance says why.
    assert [c.model for c in calls] == [GPT_OSS]
    provenance = res.json()["provenance"]
    assert provenance["requested_model"] == GEMINI_38
    assert provenance["selected_as"] == "best_suitable_for_chat"
    redirected = provenance["servability"]["redirected_from_quarantined"]
    assert redirected["model"] == GEMINI_38
    assert redirected["quarantined"] is True
    assert redirected["serves"] == 0


@pytest.mark.asyncio
async def test_probe_due_named_model_executes_and_reenters_on_serve(
    auth, monkeypatch, servability, healthy_tracker
):
    clock = _Clock(t=5000.0)
    monkeypatch.setattr(model_servability_tracker, "_clock", clock)
    for _ in range(10):
        model_servability_tracker.record_outcome(GEMINI_38, "failed", now=clock.t)
    assert model_servability_tracker.is_quarantined(GEMINI_38)
    clock.t += model_servability_tracker.probe_interval_seconds + 1.0
    assert model_servability_tracker.probe_due(GEMINI_38)

    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": GEMINI_38, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16},
    )
    assert res.status_code == 200, res.text
    # The request IS the probe: it executes under its own name, serves,
    # and the quarantine clears — the model resumes its REL-043 rank.
    assert [c.model for c in calls] == [GEMINI_38]
    assert res.json()["model"] == GEMINI_38
    assert not model_servability_tracker.is_quarantined(GEMINI_38)


@pytest.mark.asyncio
async def test_quarantine_of_everything_still_serves(auth, monkeypatch, servability, healthy_tracker):
    from app.api.v1_core_routes import MODEL_CATALOG

    for entry in MODEL_CATALOG:
        _quarantine(entry["id"])
    calls = _stub_execute(monkeypatch)
    res = await _post_chat(
        auth,
        {"model": RETIRED_70B, "messages": [{"role": "user", "content": "hello there"}], "max_tokens": 16},
    )
    # Servability never refuses service by itself: with every model
    # quarantined and no probe due, selection falls back to the
    # unfiltered ranking and the top pick serves (clearing itself).
    assert res.status_code == 200, res.text
    assert [c.model for c in calls] == [GEMINI_38]
    assert res.json()["model"] == GEMINI_38
    assert not model_servability_tracker.is_quarantined(GEMINI_38)


@pytest.mark.asyncio
async def test_route_outcomes_latch_quarantine_and_stop_the_cascade(
    auth, monkeypatch, servability, healthy_tracker
):
    calls = _stub_execute(monkeypatch, degraded_models={GEMINI_38})
    payload = {"model": GEMINI_38, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 16}
    for _ in range(10):
        res = await _post_chat(auth, payload)
        assert res.status_code == 200, res.text
    # Ten degraded attempts were recorded from the live route...
    assert model_servability_tracker.is_quarantined(GEMINI_38)
    assert model_servability_tracker.selection_view(GEMINI_38)["consecutive_misses"] == 10
    # ...so the eleventh request never attempts the dead model at all.
    before = len(calls)
    res = await _post_chat(auth, payload)
    assert res.status_code == 200, res.text
    assert [c.model for c in calls[before:]] == [GPT_OSS]
