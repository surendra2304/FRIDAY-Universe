"""
tests/conftest.py — Central pytest configuration.

Sets up sys.path for all test modules and provides shared fixtures.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Add all agent package paths to sys.path
PATHS = [
    ROOT,  # repo root for mesh package
    ROOT + "/FRIDAY/apps/core/src",
    ROOT + "/Cortex/apps/api/src",
    ROOT + "/Inference",
    ROOT + "/Memora/apps/api",
    ROOT + "/Memora/apps",
    ROOT + "/Memora",
    ROOT + "/Forge",
    ROOT + "/VyralX",
    ROOT + "/IntelX",
    ROOT + "/Sentinel/sentinel/apps/api/src",
    ROOT + "/Sentinel",
    ROOT + "/Stratex",
    ROOT + "/Futuris",
]

for p in PATHS:
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# DATABASE_URL isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="module")
def _restore_database_url_after_module():
    """Some modules swap DATABASE_URL for their own backend. Restore the value that was in
    place before each module so later modules (for example the Inference app import) see
    the CI or runtime setting instead of a missing variable."""
    sentinel = object()
    original = os.environ.get("DATABASE_URL", sentinel)
    yield
    if original is sentinel:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = original


# ---------------------------------------------------------------------------
# Fleet for dispatch tests (see tests/stub_fleet.py)
# ---------------------------------------------------------------------------
import stub_fleet  # noqa: E402  (tests/ is on sys.path through this conftest)

try:
    FLEET_MODE, _STUB_FLEET = stub_fleet.configure_fleet(os.environ)
except ValueError as exc:  # misconfiguration should stop the run, not be silently ignored
    raise pytest.UsageError(str(exc)) from exc


def pytest_report_header(config):
    if FLEET_MODE == "stub":
        return "fleet: STUB test double (not a real-fleet verification); set FRIDAY_TEST_FLEET=live to test real agents"
    return "fleet: LIVE agents from FRIDAY_DISPATCH_<NAME>_URL"


# ---------------------------------------------------------------------------
# TASK-REL-121: flaky-test quarantine — skip in PR CI, run on nightly
# ---------------------------------------------------------------------------
def _load_flaky_quarantine():
    """Load scripts/flaky_quarantine.py without requiring a package."""
    import importlib.util

    path = os.path.join(ROOT, "scripts", "flaky_quarantine.py")
    spec = importlib.util.spec_from_file_location("flaky_quarantine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pytest_collection_modifyitems(config, items):
    """Skip quarantined tests in PR CI; nightly/local runs execute them.

    The list is docs/collaboration/FLAKY_TEST_QUARANTINE.yaml (readable
    form: FLAKY_TEST_QUARANTINE.md). Mode comes from
    FRIDAY_FLAKY_QUARANTINE_MODE or the GitHub event: pull_request skips,
    schedule/workflow_dispatch (the nightly workflow) runs. An expired
    quarantine fails CI collection — expiry forces the owner's
    fix-or-remove decision instead of silently extending.
    """
    quarantine = _load_flaky_quarantine()
    entries = quarantine.load_entries()
    if os.environ.get("GITHUB_ACTIONS") == "true":
        errors = quarantine.validate_entries(entries)
        if errors:
            raise pytest.UsageError(
                "TASK-REL-121 flaky quarantine invalid: " + "; ".join(errors)
            )
    if quarantine.current_mode() != "pr":
        return
    for item in items:
        entry = quarantine.matching_entry(item.nodeid, entries)
        if entry is not None:
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "TASK-REL-121 quarantine: %s (owner %s, expiry %s); "
                        "runs on the nightly gate"
                        % (entry.get("test"), entry.get("owner"), entry.get("expiry"))
                    )
                )
            )


# ---------------------------------------------------------------------------
# TASK-REL-070: join Stratex supervision daemon threads at session end
# ---------------------------------------------------------------------------
def pytest_sessionfinish(session, exitstatus):
    """Stop the Stratex supervision keeper before interpreter shutdown.

    Importing the Stratex dashboard (tests/test_e2e_real_repo_integration.py)
    starts an infinite-loop daemon keeper thread at import time, and each
    keeper pass can spawn a long-running market-analysis refresh thread that
    logs while it runs. If either thread is alive when CPython finalizes,
    the interpreter aborts (Fatal Python error: _enter_buffered_busy ...
    at interpreter shutdown, possibly due to daemon threads -> SIGABRT ->
    exit 134) after every test passed — that abort failed the fleet-layout
    gate on board-only diffs 10 times in the 2026-11-21/22 window,
    green on re-run every time. Joining them here makes the exit clean.
    Only touches the module if the suite already imported it; never fails
    the session from teardown.
    """
    # TASK-REL-070 follow-up: stop EVERY supervision module object, not
    # just the first found. The suite can hold the module under both
    # spellings (``api.friday_supervision`` via the dashboard import and
    # ``Stratex.api.friday_supervision`` via a direct import) as two
    # distinct objects with two keepers; returning after the first would
    # leave the second keeper running into interpreter shutdown.
    stopped_any = False
    for mod_name in ("api.friday_supervision", "Stratex.api.friday_supervision"):
        module = sys.modules.get(mod_name)
        if module is None:
            continue
        stop = getattr(module, "stop_status_summary_keeper", None)
        if stop is None:
            continue
        try:
            stopped = stop()
        except Exception as exc:  # noqa: BLE001 - teardown must not fail the run
            print(f"TASK-REL-070: stop_status_summary_keeper raised: {exc}")
            continue
        stopped_any = True
        if not stopped:
            print(
                "TASK-REL-070: WARNING supervision threads still alive after stop; "
                "interpreter-shutdown abort (exit 134) remains possible"
            )
    return
