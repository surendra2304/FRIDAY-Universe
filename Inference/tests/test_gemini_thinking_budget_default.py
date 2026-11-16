"""TASK-INF-011 — Gemini Flash thinking is disabled by default.

Measured basis (gemini-egress-diag, S1, 2026-11-17): a tiny prompt to
gemini-3.6-flash took 45.3s to first byte with the model's default
thinking and 22.6s with thinkingBudget=0 — the default reasoning burn
adds ~13-23s before any visible token, which is most of why Gemini
blew the gateway's primary slice and failed over to Groq. (A ~22s
Google-side floor remains even with thinking off; this is a
mitigation, not a cure.)

These are request-construction tests against GeminiProvider's payload
builder — the native adapter is the only generateContent builder on
Inference's live serving path (providers registry maps "gemini" to
GeminiProvider; the OpenAI-compatible transport serves custom-*
endpoints only).

The default is the named setting GEMINI_FLASH_THINKING_BUDGET
(app.core.config.Settings, default 0). Scope guards matter as much as
the headline behaviour: thinkingBudget=0 must reach ONLY models that
accept it —

  * Flash thinking models (3.x/2.5 Flash, gemini-flash-latest): get
    thinkingConfig.thinkingBudget == the setting (0 by default);
  * Pro models: a 0 budget is unsupported (Gemini 2.5 Pro cannot
    think below 128 tokens, per the adapter's own clamp), so they
    keep the TASK-INF-009 allowance instead of risking a 400;
  * Flash-Lite: does not think by default and its payload has never
    carried a thinkingConfig — unchanged;
  * non-thinking / unknown models: no thinkingConfig at all, so an
    unsupported field can never 400 a model that lacks the knob.
"""

import pytest

from app.core.config import settings
from app.providers.base import ProviderMessage, ProviderRequest
from app.providers.gemini import GeminiProvider


def _provider():
    return GeminiProvider(api_key="test-key")


def _payload(model, **overrides):
    base = dict(
        messages=[ProviderMessage(role="user", content="Say ok.")],
        model=model,
        temperature=0.0,
        max_tokens=200,
    )
    base.update(overrides)
    return _provider()._build_payload(ProviderRequest(**base))


def _gen(model, **overrides):
    return _payload(model, **overrides)["generationConfig"]


@pytest.fixture(autouse=True)
def _default_setting(monkeypatch):
    """Pin the setting to its measured default regardless of the
    environment the suite runs in."""
    monkeypatch.setattr(settings, "GEMINI_FLASH_THINKING_BUDGET", 0)


# --- the headline behaviour: Flash defaults to thinkingBudget=0 ---

@pytest.mark.parametrize(
    "model",
    ["gemini-3.6-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemini-2.5-flash"],
)
def test_flash_models_default_to_zero_thinking_budget(model):
    gen = _gen(model)
    assert gen["thinkingConfig"] == {"thinkingBudget": 0}
    # No allowance is added on top: the declared budget is entirely
    # visible output again.
    assert gen["maxOutputTokens"] == 200


def test_flash_thinking_budget_sent_without_max_tokens():
    """The disable must also reach unbounded requests: with no
    declared max_tokens there is no maxOutputTokens, but the
    thinkingConfig still goes out — otherwise the slowest requests
    would keep the default thinking burn."""
    gen = _gen("gemini-3.6-flash", max_tokens=None)
    assert "maxOutputTokens" not in gen
    assert gen["thinkingConfig"] == {"thinkingBudget": 0}


def test_setting_is_tunable(monkeypatch):
    """GEMINI_FLASH_THINKING_BUDGET is the operator knob: raising it
    restores a bounded thinking allowance for Flash models."""
    monkeypatch.setattr(settings, "GEMINI_FLASH_THINKING_BUDGET", 256)
    gen = _gen("gemini-3.6-flash")
    assert gen["thinkingConfig"] == {"thinkingBudget": 256}
    assert gen["maxOutputTokens"] == 200 + 256


def test_explicit_caller_budget_still_wins():
    """A caller's explicit extra_params thinking_budget overrides the
    Flash default in both directions."""
    gen = _gen("gemini-3.6-flash", extra_params={"thinking_budget": 512})
    assert gen["thinkingConfig"] == {"thinkingBudget": 512}
    assert gen["maxOutputTokens"] == 200 + 512


# --- scope guards: models that must NOT receive the 0 default ---

def test_pro_model_keeps_allowance_not_zero():
    """gemini-2.5-pro cannot think below a 128-token budget (the
    adapter clamps explicit budgets to that floor), so a default of 0
    would be an unsupported value. Pro keeps the TASK-INF-009
    allowance exactly as before."""
    gen = _gen("gemini-2.5-pro")
    assert gen["thinkingConfig"] == {
        "thinkingBudget": GeminiProvider.DEFAULT_THINKING_TOKEN_ALLOWANCE
    }
    assert gen["maxOutputTokens"] == 200 + GeminiProvider.DEFAULT_THINKING_TOKEN_ALLOWANCE


def test_pro_latest_alias_keeps_allowance_not_zero():
    gen = _gen("gemini-pro-latest")
    assert gen["thinkingConfig"]["thinkingBudget"] == (
        GeminiProvider.DEFAULT_THINKING_TOKEN_ALLOWANCE
    )


def test_flash_lite_payload_unchanged():
    """Flash-Lite does not think by default; its payload has never
    carried a thinkingConfig and must not gain one."""
    gen = _gen("gemini-2.5-flash-lite")
    assert "thinkingConfig" not in gen
    assert gen["maxOutputTokens"] == 200


@pytest.mark.parametrize("model", ["gemini-1.5-flash", "some-unknown-model"])
def test_non_thinking_models_get_no_thinking_config(model):
    """Models outside the thinking families receive no thinkingConfig
    at all — an unsupported field must never be sent (a 400 would be
    worse than the status quo). Note gemini-1.5-flash: a Flash name
    alone is not enough; the model must be a thinking-family model."""
    gen = _gen(model)
    assert "thinkingConfig" not in gen
    assert gen["maxOutputTokens"] == 200


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
