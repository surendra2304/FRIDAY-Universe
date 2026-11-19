"""TASK-INF-015: gemini-3.5-flash-lite joins the Gemini adapter catalogue.

The Flash-Lite line is the fleet's high-quota free tier (15 RPM /
500 RPD, verified from two independent free-project readings, Sep +
Oct 2026), while full Flash sits at 5 RPM / 20 RPD — the wall the
voice key probe hit (TASK-VOI-020). The adapter must therefore accept
the current Flash-Lite id by name.

TASK-INF-017: the legacy gemini-2.5-flash-lite no longer stays listed.
INF-015 kept it because existing callers still named it (the
TASK-VOI-020 probe pin among them); TASK-VOI-021 moved that pin to
the explicit gemini-3.5-flash-lite id, and the owner pinned
gemini-3.5-flash-lite fleet-wide on 2026-11-19. The legacy id is an
access-limited alias Google routes to 3.5-flash-lite from 2026-12-01;
with no production caller left, it is removed so the catalogue names
exactly one Flash-Lite id.

These tests pin the catalogue membership only. Live generation with
this deployment's keys is a post-merge probe and is NOT claimed here.
"""

from app.providers.gemini import GeminiProvider


def test_flash_lite_35_is_supported():
    assert "gemini-3.5-flash-lite" in GeminiProvider.SUPPORTED_MODELS


def test_legacy_flash_lite_25_is_removed():
    # TASK-INF-017: was test_legacy_flash_lite_25_is_kept under
    # TASK-INF-015, when the TASK-VOI-020 probe pin still named the
    # legacy id. VOI-021 moved the pin; the owner pinned the 3.5 id.
    assert "gemini-2.5-flash-lite" not in GeminiProvider.SUPPORTED_MODELS


def test_capabilities_advertise_flash_lite_35():
    provider = GeminiProvider(api_key="<redacted>")
    caps = provider.capabilities()
    assert "gemini-3.5-flash-lite" in caps.supported_models


def test_no_duplicates_in_supported_models():
    models = GeminiProvider.SUPPORTED_MODELS
    assert len(models) == len(set(models))
