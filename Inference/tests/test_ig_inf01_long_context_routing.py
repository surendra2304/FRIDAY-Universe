"""TASK-IG-INF-01: long-context routing must respect declared context windows.

REL-043 ranks suitable models per task type, but its long_context
ranking alone cannot promise a fit: a request larger than a model's
context window fails at the provider or is silently truncated by it.
The corpus item behind this task (Deov8pzsfin) asks Inference to route
long-document / large-codebase tasks to a ~1M-token-context model.

These tests pin the fit layer added on top of REL-043:
- every catalogue model carries a declared context window;
- when the estimated request size (prompt + reserved output) exceeds
  the standard tier's window, selection keeps only models whose
  window can hold the request, preserving REL-043 ranking order;
- the fit check applies across task types (a huge codebase request is
  "code", and needs a fitting window just as much);
- when NO catalogue window can hold the request, the largest holder
  is still chosen and the overflow is disclosed in the selection
  record and in response provenance — never a silent truncation;
- below the fit floor, REL-043 behaviour is byte-for-byte unchanged
  (no fit fields appear in the selection record).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import v1_core_routes as v1
from app.main import app

RETIRED_MODEL = "llama-3.3-70b-versatile"
BIG_WINDOW_MODELS = {"gemini-3.8-flash", "gemini-3.6-flash"}
STANDARD_WINDOW = 131072


def _req(text: str, model: str = RETIRED_MODEL, max_tokens: int = 1024):
    return v1.ChatCompletionRequest(
        model=model,
        messages=[v1.ChatMessage(role="user", content=text)],
        max_tokens=max_tokens,
    )


@pytest.fixture
def all_providers_available(monkeypatch):
    monkeypatch.setattr(v1, "_provider_available", lambda provider: True)


# ---------------------------------------------------------------------------
# Estimation
# ---------------------------------------------------------------------------


def test_estimate_counts_prompt_plus_reserved_output():
    req = _req("x" * 400, max_tokens=100)
    assert v1._estimate_context_tokens(req) == 400 // 4 + 100


def test_estimate_handles_empty_messages():
    req = v1.ChatCompletionRequest(model="auto", messages=[], max_tokens=50)
    assert v1._estimate_context_tokens(req) == 50


def test_every_catalogue_model_declares_a_window():
    for entry in v1.MODEL_CATALOG:
        assert v1.MODEL_CONTEXT_WINDOWS[entry["id"].lower()] > 0


# ---------------------------------------------------------------------------
# Fit filtering in selection
# ---------------------------------------------------------------------------


def test_huge_document_selects_a_fitting_window(all_providers_available):
    # ~200k estimated tokens: only the 2M-window Gemini pair can hold it.
    sel = v1._select_best_suitable(_req("plain document text " * 40000))
    assert sel is not None
    assert sel["task_type"] == "long_context"
    assert sel["model"] in BIG_WINDOW_MODELS
    assert sel["context_window"] == 2097152
    assert sel["estimated_context_tokens"] > STANDARD_WINDOW
    assert sel["context_overflow"] is False


def test_huge_codebase_request_is_fit_filtered_within_code_ranking(all_providers_available):
    # ~150k estimated tokens with code markers: task type is "code", whose
    # REL-043 ranking leads with 131k-window models. Fit must still win.
    text = "def main():\n    pass\n" + ("# padding line\n" * 40000)
    sel = v1._select_best_suitable(_req(text))
    assert sel is not None
    assert sel["task_type"] == "code"
    assert sel["model"] in BIG_WINDOW_MODELS
    assert sel["context_overflow"] is False


def test_overflow_is_disclosed_when_nothing_fits(all_providers_available):
    # ~3M estimated tokens exceeds even the 2M Gemini windows.
    sel = v1._select_best_suitable(_req("x" * 12000000))
    assert sel is not None
    assert sel["model"] == "gemini-3.8-flash"  # largest holder, ranking order kept
    assert sel["context_window"] == 2097152
    assert sel["estimated_context_tokens"] > sel["context_window"]
    assert sel["context_overflow"] is True


def test_overflow_with_big_windows_unavailable_picks_largest_remaining(monkeypatch):
    monkeypatch.setattr(v1, "_provider_available", lambda provider: provider != "gemini")
    sel = v1._select_best_suitable(_req("plain document text " * 40000))
    assert sel is not None
    # Only 131k-window models remain; the best-ranked of them is chosen
    # and the overflow is disclosed rather than hidden.
    assert sel["model"] == "openai/gpt-oss-120b"
    assert sel["context_window"] == STANDARD_WINDOW
    assert sel["context_overflow"] is True


def test_exclusions_still_apply_under_fit_filtering(all_providers_available):
    sel = v1._select_best_suitable(
        _req("plain document text " * 40000), exclude={"gemini-3.8-flash"}
    )
    assert sel is not None
    assert sel["model"] == "gemini-3.6-flash"
    assert sel["context_overflow"] is False


# ---------------------------------------------------------------------------
# No behaviour change below the fit floor
# ---------------------------------------------------------------------------


def test_normal_chat_request_has_no_fit_fields(all_providers_available):
    sel = v1._select_best_suitable(_req("hello there", model=RETIRED_MODEL))
    assert sel is not None
    assert sel["task_type"] == "chat"
    assert sel["model"] == "gemini-3.8-flash"  # REL-043 chat ranking, unchanged
    assert "context_overflow" not in sel
    assert "context_window" not in sel


def test_ranked_models_without_requirement_match_rel043_ranking(all_providers_available):
    ranked = v1._ranked_suitable_models("long_context")
    assert ranked == v1.MODEL_SUITABILITY["long_context"]


def test_ranked_models_fit_filter_keeps_ranking_order(all_providers_available):
    ranked = v1._ranked_suitable_models("chat", required_tokens=200000)
    assert ranked == ["gemini-3.8-flash", "gemini-3.6-flash"]


# ---------------------------------------------------------------------------
# Route level: provenance carries the fit accounting
# ---------------------------------------------------------------------------


def _stub_execute_success(monkeypatch):
    from app.providers.unified_manager import UnifiedExecutionResponse, unified_provider_manager

    calls = []

    async def stub(req):
        calls.append(req)
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


async def test_route_provenance_discloses_fit_for_huge_document(auth, monkeypatch):
    monkeypatch.setattr(v1, "_provider_available", lambda provider: True)
    calls = _stub_execute_success(monkeypatch)
    payload = {
        "model": RETIRED_MODEL,
        "messages": [{"role": "user", "content": "plain document text " * 40000}],
        "max_tokens": 1024,
    }
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", headers=auth) as client:
        resp = await client.post("/v1/chat/completions", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert calls and calls[0].model in BIG_WINDOW_MODELS
    provenance = body["provenance"]
    assert provenance["selected_as"] == "best_suitable_for_long_context"
    assert provenance["context_window"] == 2097152
    assert provenance["estimated_context_tokens"] > STANDARD_WINDOW
    assert provenance["context_overflow"] is False
