"""TASK-SEN-028 checkpoint 2 — footprint-cleanup walkthrough tests.

Hermetic: no network, no server, no owner data. The HIBP paths are
tested through the injectable checker seam and through the real
no-key / no-import unavailable paths; the live v3 call is never made
here (it needs the owner's key and a live run, which waits on
clearance).
"""

from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from sentinel.apps.cli.footprint_cleanup import (
    STEP_IDS,
    STEPS,
    FootprintState,
    exiftool_available,
    exiftool_dry_run,
    footprint_app,
    get_step,
    hibp_email_status,
    hibp_password_status,
)

runner = CliRunner()


# Step registry -------------------------------------------------------------

def test_seven_steps_in_board_order():
    assert STEP_IDS == (
        "hibp",
        "justdeleteme",
        "aliases",
        "my-activity",
        "digital-rights",
        "exiftool",
        "cover-tracks",
    )
    assert len(STEPS) == 7


def test_every_step_has_title_summary_and_owner_action():
    for step in STEPS:
        assert step["title"] and step["summary"] and step["owner_action"]
        assert step["kind"] in ("live", "guidance", "local-binary")


def test_get_step_rejects_unknown_id():
    with pytest.raises(KeyError):
        get_step("bogus")


# Status store --------------------------------------------------------------

def test_state_starts_all_pending(tmp_path):
    state = FootprintState.load(tmp_path / "state.json")
    assert [state.status(step_id) for step_id in STEP_IDS] == ["pending"] * 7


def test_mark_persists_across_reload(tmp_path):
    path = tmp_path / "state.json"
    state = FootprintState.load(path)
    state.mark("hibp", "done", "owner ran HIBP, no breaches reported by owner")
    reloaded = FootprintState.load(path)
    assert reloaded.status("hibp") == "done"
    assert reloaded._data["steps"]["hibp"]["evidence"].startswith("owner ran HIBP")
    assert reloaded._data["steps"]["hibp"]["updated_at"]


def test_mark_rejects_bad_status_and_unknown_step(tmp_path):
    state = FootprintState.load(tmp_path / "state.json")
    with pytest.raises(ValueError):
        state.mark("hibp", "clean")
    with pytest.raises(KeyError):
        state.mark("bogus", "done")


def test_reset_returns_all_steps_to_pending(tmp_path):
    path = tmp_path / "state.json"
    state = FootprintState.load(path)
    state.mark("aliases", "done", "inventory recorded")
    state.reset()
    assert [FootprintState.load(path).status(s) for s in STEP_IDS] == ["pending"] * 7


# HIBP reuse seam -----------------------------------------------------------

def test_hibp_email_without_key_is_unavailable_never_clean():
    # No IntelX on the import path here and no key: both real-world
    # unavailable paths must report unavailable, never "no breaches".
    status, detail = hibp_email_status("owner@example.com")
    assert status == "unavailable"
    assert detail


async def _fake_email_breaches(email, api_key=None):
    return SimpleNamespace(
        status="breaches_found",
        checked=True,
        breaches=({"Name": "ExampleBreach", "Domain": "example.com"},),
        reason="",
    )


async def _fake_email_clean(email, api_key=None):
    return SimpleNamespace(status="no_breaches", checked=True, breaches=(), reason="")


def test_hibp_email_stubbed_breaches_found():
    status, detail = hibp_email_status("owner@example.com", _checker=_fake_email_breaches)
    assert status == "breaches_found"
    assert "ExampleBreach" in detail


def test_hibp_email_stubbed_no_breaches():
    status, detail = hibp_email_status("owner@example.com", _checker=_fake_email_clean)
    assert status == "no_breaches"


def test_hibp_email_invalid_address_raises():
    async def _raises(email, api_key=None):
        raise ValueError("invalid email 'x'")
    with pytest.raises(ValueError):
        hibp_email_status("x", _checker=_raises)


async def _fake_password_found(password):
    return SimpleNamespace(found=True, occurrences=3, sha1_prefix="ABCDE")


async def _fake_password_clean(password):
    return SimpleNamespace(found=False, occurrences=0, sha1_prefix="ABCDE")


def test_hibp_password_stubbed_found_and_clean():
    found, count, _ = hibp_password_status("hunter2", _checker=_fake_password_found)
    assert found is True and count == 3
    found, count, _ = hibp_password_status("hunter2", _checker=_fake_password_clean)
    assert found is False and count == 0


# ExifTool ------------------------------------------------------------------

def test_exiftool_available_returns_bool():
    assert isinstance(exiftool_available(), bool)


def test_exiftool_dry_run_lists_only_existing_files(tmp_path):
    real = tmp_path / "photo.jpg"
    real.write_bytes(b"fake")
    assert exiftool_dry_run([str(real), str(tmp_path / "missing.jpg")]) == [str(real)]


# CLI -----------------------------------------------------------------------

def test_cli_status_lists_all_seven_steps(tmp_path):
    result = runner.invoke(footprint_app, ["status", "--state-file", str(tmp_path / "s.json")])
    assert result.exit_code == 0, result.output
    for step_id in STEP_IDS:
        assert step_id in result.output


def test_cli_mark_then_status_shows_it(tmp_path):
    state_file = str(tmp_path / "s.json")
    marked = runner.invoke(
        footprint_app,
        ["mark", "aliases", "done", "--evidence", "inventory recorded",
         "--state-file", state_file],
    )
    assert marked.exit_code == 0, marked.output
    shown = runner.invoke(footprint_app, ["status", "--state-file", state_file])
    assert "aliases" in shown.output and "done" in shown.output


def test_cli_unknown_step_and_bad_status_fail(tmp_path):
    state_file = str(tmp_path / "s.json")
    assert runner.invoke(footprint_app, ["step", "bogus"]).exit_code != 0
    marked = runner.invoke(
        footprint_app, ["mark", "hibp", "clean", "--state-file", state_file]
    )
    assert marked.exit_code != 0


def test_cli_hibp_without_key_reports_unavailable():
    result = runner.invoke(footprint_app, ["hibp", "owner@example.com"])
    assert result.exit_code == 0, result.output
    assert "unavailable" in result.output
    assert "no breaches" not in result.output
