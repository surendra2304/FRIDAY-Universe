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
