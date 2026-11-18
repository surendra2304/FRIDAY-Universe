"""TASK-INF-015: gemini-3.5-flash-lite joins the Gemini adapter catalogue.

The Flash-Lite line is the fleet's high-quota free tier (15 RPM /
500 RPD, verified from two independent free-project readings, Sep +
Oct 2026), while full Flash sits at 5 RPM / 20 RPD — the wall the
voice key probe hit (TASK-VOI-020). The adapter must therefore accept
the current Flash-Lite id by name. The legacy gemini-2.5-flash-lite
stays listed: Google routes it to 3.5-flash-lite from 2026-12-01 and
existing callers still name it.

These tests pin the catalogue membership only. Live generation with
this deployment's keys is a post-merge probe and is NOT claimed here.
"""

from app.providers.gemini import GeminiProvider


def test_flash_lite_35_is_supported():
    assert "gemini-3.5-flash-lite" in GeminiProvider.SUPPORTED_MODELS


def test_legacy_flash_lite_25_is_kept():
    assert "gemini-2.5-flash-lite" in GeminiProvider.SUPPORTED_MODELS


def test_capabilities_advertise_flash_lite_35():
    provider = GeminiProvider(api_key="<redacted>")
    caps = provider.capabilities()
    assert "gemini-3.5-flash-lite" in caps.supported_models


def test_no_duplicates_in_supported_models():
    models = GeminiProvider.SUPPORTED_MODELS
    assert len(models) == len(set(models))
