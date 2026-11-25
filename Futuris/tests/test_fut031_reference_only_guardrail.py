"""TASK-FUT-031 reference-only guardrail.

The scouted-repos registry verdicts for the three reference-only repos in
TASK-FUT-031 are "integrate nothing":
  * Polymarket py-sdk (Polymarket/py-sdk, MIT) — the free read-only
    Gamma/Data APIs are a legitimate signal, readable with plain HTTP;
    no SDK adoption, no trading (real-money venue, out of scope).
  * Fincept Terminal (Fincept-Corporation/FinceptTerminal, AGPL-3.0) — a
    Qt6 desktop GUI that cannot run on the headless fleet; AGPL-3.0 bars
    embedding its code into FRIDAY services.
  * Scientific Agent Skills (K-Dense-AI/scientific-agent-skills, MIT) —
    no fleet consumer for the bulk of the library; packaging discipline
    only.

This test is the guardrail proof of absence from every Futuris production
path required by the TASK-FUT-031 acceptance: if any of these repos ever
gets wired into Futuris production code or dependencies, this test fails
and the integration decision has to be made consciously, with a
coordinator ruling — not silently.

Scope is the Futuris production path (Futuris/futuris/ + Futuris/app/).
Stratex-side Polymarket/Fincept modules (Stratex/app/agents/
real_polymarket.py, real_fincept_terminal.py) are pre-existing Stratex-lane
code, out of this task's scope; the Polymarket Gamma live leg there is
covered by TASK-STR-072 evidence. Futuris/scripts/ trial harnesses are
not production paths and are out of scope here.

Collected by the Futuris contracts step in .github/workflows/
owner-workflows.yml (TASK-REL-068: a shipped test must be collected).
"""
import ast
import sys
from pathlib import Path

FUTURIS_ROOT = Path(__file__).resolve().parents[1]
PROD_DIRS = [FUTURIS_ROOT / "futuris", FUTURIS_ROOT / "app"]

# Top-level module names whose import in Futuris production code would be
# an integration of a reference-only repo.
BANNED_MODULES = {
    "polymarket",
    "polymarket_client",
    "py_clob_client",
    "fincept",
    "scientific_agent_skills",
}

# A network call to the venue from production code would be an integration.
BANNED_HOSTS = {"gamma-api.polymarket.com"}

# Dependency names that must never appear in Futuris' install set.
BANNED_DEPS = {"polymarket-client", "polymarket", "fincept", "scientific-agent-skills"}


def _iter_prod_py():
    for d in PROD_DIRS:
        if not d.is_dir():
            continue
        yield from sorted(d.rglob("*.py"))


def test_no_reference_only_imports_in_production_code():
    """No Futuris production module imports a reference-only repo."""
    violations = []
    for path in _iter_prod_py():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module.split(".")[0]] if node.module else []
            else:
                continue
            for name in names:
                if name in BANNED_MODULES:
                    violations.append(f"{path.relative_to(FUTURIS_ROOT)}: imports {name}")
    assert not violations, (
        "reference-only repo imported in Futuris production code:\n" + "\n".join(violations)
    )


def test_no_venue_calls_in_production_code():
    """No Futuris production module calls the Polymarket APIs."""
    violations = []
    for path in _iter_prod_py():
        text = path.read_text(encoding="utf-8")
        for host in BANNED_HOSTS:
            if host in text:
                violations.append(f"{path.relative_to(FUTURIS_ROOT)}: references {host}")
    assert not violations, (
        "venue host referenced in Futuris production code:\n" + "\n".join(violations)
    )


def test_no_reference_only_dependencies():
    """No reference-only repo is a Futuris dependency.

    OpenBB is the exception that proves the rule: it is an ADAPT, declared
    only as the optional `futuris[openbb]` extra in pyproject.toml, never
    in the install set — so it must not appear in requirements.txt,
    requirements.lock, or the main project dependencies.
    """
    for rel in ("requirements.txt", "requirements.lock"):
        text = (FUTURIS_ROOT / rel).read_text(encoding="utf-8")
        for dep in BANNED_DEPS | {"openbb"}:
            assert dep not in text.lower(), f"{rel} must not depend on {dep}"
    if sys.version_info >= (3, 11):
        import tomllib
    else:  # pragma: no cover - CI and local runs are Python 3.12
        import tomli as tomllib
    pyproject = tomllib.loads((FUTURIS_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    main_deps = [d.lower() for d in pyproject.get("project", {}).get("dependencies", [])]
    for dep in BANNED_DEPS | {"openbb"}:
        assert not any(dep in d for d in main_deps), f"pyproject dependencies must not include {dep}"
    optional = pyproject.get("project", {}).get("optional-dependencies", {})
    assert "openbb" in optional, "the openbb optional extra (ARM-gated adapt) must still exist"
    assert not any(
        set(optional.get(k, [])) & BANNED_DEPS for k in optional
    ), "no optional extra may pull in a reference-only repo"


def test_openbb_sdk_probe_never_imports_sdk():
    """The OpenBB adapt stays bounded: probing never imports the SDK.

    TASK-IG-FUT-01 measured the full SDK at 210.9 s import / 995.6 MB RSS
    — it cannot run in-process on the fleet. The provider must therefore
    probe with find_spec only, and the SDK must stay an env flip
    (FUTURIS_OPENBB_PROVIDER), not a hard dependency.
    """
    from futuris.market_data.providers.openbb_sdk import OpenBBSDKProvider, sdk_available

    assert sdk_available() is False, "openbb SDK must be absent in this environment"
    assert "openbb" not in sys.modules, "probing must not import the openbb SDK"
    assert OpenBBSDKProvider.name == "openbb_sdk"


async def test_openbb_sdk_absent_fetch_is_unavailable_not_fabricated():
    """With the SDK absent, a fetch reports unavailable — never fake bars."""
    from datetime import datetime, timezone

    from futuris.market_data.providers.openbb_sdk import OpenBBSDKProvider

    result = await OpenBBSDKProvider().fetch_ohlcv(
        "AAPL", datetime(2026, 1, 1, tzinfo=timezone.utc),
        datetime(2026, 1, 2, tzinfo=timezone.utc), "1d",
    )
    assert result.status == "unavailable"
    assert "not installed" in result.detail
    assert result.bars == []
    assert "openbb" not in sys.modules, "fetching must not import the openbb SDK"
