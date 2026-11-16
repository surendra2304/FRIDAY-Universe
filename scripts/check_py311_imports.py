#!/usr/bin/env python3
"""Python 3.11+ production-interpreter import gate.

Successor to the TASK-REL-050 Python 3.10 gate
(``scripts/check_py310_imports.py``, retired by the fleet Python 3.12
upgrade, work item W3). The fleet's production interpreter is CPython
3.12 (manifests floor at >=3.11); before the upgrade, production ran
3.10 and the gate's job was to catch 3.11+-only constructs that would
have failed to boot there. The failure class is now inverted: code
that breaks on the *production* interpreter — stdlib APIs removed in
3.11/3.12 (``imp``, ``asyncore``/``asynchat``, ``distutils``,
``configparser`` legacy helpers, ...), behaviour changes in stdlib
modules the fleet imports at boot, or 3.13+-only syntax creeping in
from a newer development machine — merges green everywhere except
where it matters. This gate makes that class visible before merge:

1. It refuses to run (exit 2) unless the interpreter is Python 3.11
   or 3.12 — below 3.11 is the retired production line (a PASS there
   says nothing about the fleet), and 3.13+ is not the fleet target
   (a PASS there would not prove the fleet interpreter either).
2. It byte-compiles every ``.py`` under the ten agent directories and
   ``mesh/`` with this interpreter, catching syntax the fleet
   interpreter cannot parse (e.g. 3.13+-only constructs).
3. It imports every agent's production entrypoint — the exact
   WorkingDirectory / PYTHONPATH / module from ``deploy/setup_fleet.sh``
   — in a subprocess with dummy credentials and no reachable services.
   VyralX is the one special case: its entrypoint executes
   ``Base.metadata.create_all`` at import time, and outside
   ``APP_ENV=development`` its settings validator requires a real
   Oracle URL — so the gate imports it in its own documented
   development/test configuration (APP_ENV=development + a throwaway
   SQLite file; the same configuration its unit-test suite uses).
   The import graph exercised is identical; only the database target
   differs. Every other agent gets a dummy Oracle URL on a dead port,
   and no other entrypoint touches the database at import time.

If an import fails only because a third-party package is missing from
the gate's minimal environment, the import is retried with that package
stubbed and the stub is reported — the gate never stubs away a
*compatibility* failure: an ImportError naming a stdlib module, a
SyntaxError, or any error raised by repository code fails the gate.
Stdlib modules removed in 3.12 (``imp``, ``distutils``, ``asyncore``,
``asynchat``, ``smtpd``) count as stdlib for this rule: they are absent
from ``sys.stdlib_module_names`` on 3.12, and without the explicit
list the stubber would mistake them for third-party packages and mask
the exact failures this gate exists to catch.
Each subprocess also reports its peak RSS, which the Python 3.12
cutover uses as the MemoryMax budgeting input (plan item W6).

What this gate does NOT cover (by design, stated honestly):
- Runtime-only behaviour differences that execute after import.
  Import smoke is a boot-level proof, not serving traffic; behaviour
  is covered by the agents' own suites and post-flip health checks.
- Test files (production never imports them).

Usage:  python3.12 scripts/check_py311_imports.py [--root DIR]
                [--agents Inference,Memora,...]
Exit:   0 = all ten entrypoints import on 3.11/3.12; 1 = a check
        failed; 2 = wrong interpreter / setup error.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

AGENT_DIRS = ["FRIDAY", "Inference", "Memora", "Stratex", "Futuris",
              "IntelX", "Forge", "Sentinel", "Cortex", "VyralX"]

# Production entrypoints, verbatim from deploy/setup_fleet.sh (systemd
# WorkingDirectory + PYTHONPATH + ExecStart). Every unit's PYTHONPATH
# ends with $REPO_DIR, which is how the shared `mesh` package resolves.
# Fields: name, workdir, pythonpath parts, mode, target.
AGENTS = [
    ("Inference", "Inference", ["Inference", "."], "module", "app.main"),
    ("Memora", "Memora", ["Memora", "."], "module", "app.main"),
    ("Stratex", "Stratex", ["Stratex", "."], "file", "Stratex/dashboard.py"),
    ("Futuris", "Futuris", ["Futuris", "."], "module", "futuris.api.app"),
    ("IntelX", "IntelX", ["IntelX", "."], "module", "intelx.app.main"),
    ("Forge", "Forge", ["Forge", "."], "module", "app.main"),
    ("Sentinel", "Sentinel", ["Sentinel", "."], "module",
     "sentinel.apps.api.main"),
    ("Cortex", "Cortex", ["Cortex", "."], "module",
     "apps.api.src.cortex_api.main"),
    ("VyralX", "VyralX", ["VyralX", "."], "module", "app.main"),
    ("FRIDAY", "FRIDAY", ["FRIDAY/src", "FRIDAY/apps/core/src", "."],
     "module", "friday.api.server"),
]

DUMMY_ORACLE = ("oracle+oracledb://gate_dummy:gate_dummy_pw"
                "@127.0.0.1:1521/?service_name=GATEPDB")

_D = "gate-dummy-0000000000000000000000000000"
BASE_ENV = {
    "ENVIRONMENT": "staging",
    "APP_ENV": "staging",
    "STAGING_MODE": "true",
    "LOG_LEVEL": "INFO",
    "DATABASE_URL": DUMMY_ORACLE,
    "ORACLE_DSN": "127.0.0.1:1521/GATEPDB",
    "PYTHONDONTWRITEBYTECODE": "1",
    # The dummy DB host is 127.0.0.1; make sure no proxy config in the
    # CI environment reroutes loopback (observed locally: an egress
    # proxy turned a clean connection-refused into an HTTP 403 page).
    "NO_PROXY": "localhost,127.0.0.1",
    "no_proxy": "localhost,127.0.0.1",
    # Dummy stand-ins for the keys production provides via agent.env;
    # several agents validate their presence at import time.
    "GEMINI_API_KEY": _D, "GOOGLE_API_KEY": _D, "GROQ_API_KEY": _D,
    "OPENAI_API_KEY": _D, "ANTHROPIC_API_KEY": _D,
    "OPENROUTER_API_KEY": _D,
    "FRIDAY_API_KEY": _D, "INFERENCE_API_KEY": _D,
    "MEMORA_API_KEY": _D, "MEMORA_MASTER_KEY": _D,
    "STRATEX_API_KEY": _D, "FUTURIS_API_KEY": _D,
    "INTELX_API_KEY": _D, "FORGE_API_KEY": _D,
    "SENTINEL_API_KEY": _D, "CORTEX_API_KEY": _D,
    "VYRALX_API_KEY": _D, "AI_UNIVERSE_API_KEY": _D,
    "FRIDAY_URL": "http://127.0.0.1:10000",
    "INFERENCE_URL": "http://127.0.0.1:8001",
    "MEMORA_URL": "http://127.0.0.1:8002",
    "STRATEX_URL": "http://127.0.0.1:8003",
    "FUTURIS_URL": "http://127.0.0.1:8004",
    "INTELX_URL": "http://127.0.0.1:8005",
    "FORGE_URL": "http://127.0.0.1:8006",
    "SENTINEL_URL": "http://127.0.0.1:8008",
    "CORTEX_URL": "http://127.0.0.1:8009",
    "VYRALX_URL": "http://127.0.0.1:8010",
}

AGENT_ENV = {
    "Sentinel": {
        "SENTINEL_JWT_SECRET": "gate-dummy-jwt-secret-not-a-real-one-000",
        "SENTINEL_ADMIN_KEY": "gate-dummy-admin-key",
        "FRIDAY_API_KEY": "gate-dummy-friday-key",
        "INFERENCE_API_KEY": "gate-dummy-inference-key",
        "MEMORA_API_KEY": "gate-dummy-memora-key",
        "STRATEX_API_KEY": "gate-dummy-stratex-key",
        "FUTURIS_API_KEY": "gate-dummy-futuris-key",
        "INTELX_API_KEY": "gate-dummy-intelx-key",
        "FORGE_API_KEY": "gate-dummy-forge-key",
        "CORTEX_API_KEY": "gate-dummy-cortex-key",
        "VYRALX_API_KEY": "gate-dummy-vyralx-key",
        "SENTINEL_GITHUB_TOKEN": "gate-dummy-github-token",
        "SENTINEL_TELEGRAM_BOT_TOKEN": "gate-dummy-telegram-token",
        "SENTINEL_TELEGRAM_CHAT_ID": "0",
        "SENTINEL_DISCORD_WEBHOOK_URL": "",
        "GITHUB_TOKEN": "gate-dummy-github-token",
        "TELEGRAM_BOT_TOKEN": "gate-dummy-telegram-token",
        "TELEGRAM_CHAT_ID": "0",
        # The audit chain refuses to initialise without a signing key
        # (production provides one in Sentinel's agent.env).
        "SENTINEL_AUDIT_SIGNING_KEY":
            "gate-dummy-audit-signing-key-not-a-secret-0000",
        "SENTINEL_AUDIT_HMAC_KEY":
            "gate-dummy-audit-hmac-key-not-a-secret-000000",
    },
    "Forge": {
        "FORGE_JWT_SECRET_KEY": "gate-dummy-forge-jwt-secret-not-real",
        "FORGE_ADMIN_KEY": "gate-dummy-forge-admin-key",
        "FORGE_REDIS_ENABLED": "false",
        "FORGE_SANDBOX_ENABLED": "false",
        "FORGE_ENV": "development",
        "API_KEY_REQUIRED": "false",
    },
    "Stratex": {
        "STRATEX_SKIP_TELEGRAM": "1",
        "STRATEX_SKIP_DISCORD": "1",
        "STRATEX_SKIP_EXCHANGE_INIT": "1",
        "STRATEX_TRADING_ENABLED": "false",
        "TRADING_ENABLED": "false",
        "BINANCE_API_KEY": "gate-dummy",
        "BINANCE_API_SECRET": "gate-dummy",
        "BINANCE_TESTNET_API_KEY": "gate-dummy",
        "BINANCE_TESTNET_API_SECRET": "gate-dummy",
        "STRATEX_DASHBOARD_HOST": "127.0.0.1",
        "STRATEX_DASHBOARD_PORT": "0",
        "STRATEX_DASHBOARD_TOKEN": "gate-dummy",
        "PORT": "8003",
        "FLASK_DEBUG": "0",
    },
    "VyralX": {
        "YOUTUBE_UPLOAD_ENABLED": "false",
        "AUTONOMOUS_PUBLISH_ENABLED": "false",
        # Outside development the settings validator requires a unique
        # API_KEY (production provides a real one in VyralX's agent.env).
        "API_KEY": "gate-dummy-vyralx-api-key-not-a-secret",
        # Filled in by main(): VyralX executes Base.metadata.create_all
        # at import time, so it needs a *working* database URL; its
        # settings accept SQLite, which needs no server.
    },
    "FRIDAY": {
        "FRIDAY_GEMINI_API_KEY": "gate-dummy",
        "GEMINI_API_KEY": "gate-dummy",
    },
}

# Subprocess runner: imports the target, retrying with stubs ONLY for
# missing third-party packages. Prints one RESULT JSON line.
RUNNER = r"""
import importlib, importlib.util, json, resource, sys, traceback, types

root, mode, target = sys.argv[1], sys.argv[2], sys.argv[3]
STDLIB = sys.stdlib_module_names
# Stdlib modules removed in Python 3.12. On a 3.12 interpreter they are
# absent from stdlib_module_names, so the stub logic below would
# mistake them for missing third-party packages and stub them away —
# masking exactly the failure class this gate exists to catch. They
# are treated as stdlib: never stubbed, always a hard failure.
REMOVED_STDLIB = {"imp", "distutils", "asyncore", "asynchat", "smtpd"}
REPO_TOP = {"app", "apps", "friday", "futuris", "intelx", "sentinel",
            "mesh", "dashboard"}


class _Stub:
    def __init__(self, *a, **k):
        pass

    def __call__(self, *a, **k):
        return _INST

    def __getattr__(self, name):
        return _INST

    def __getitem__(self, key):
        return _INST

    def __iter__(self):
        return iter(())

    def __contains__(self, item):
        return False

    def __enter__(self):
        return _INST

    def __exit__(self, *a):
        return False

    async def __aenter__(self):
        return _INST

    async def __aexit__(self, *a):
        return False


_INST = _Stub()


def make_stub(name):
    mod = types.ModuleType(name)
    mod.__path__ = []
    mod.__getattr__ = lambda attr, _c=_Stub: _c
    return mod


def install_stub(dotted):
    parts = dotted.split(".")
    for i in range(1, len(parts) + 1):
        sub = ".".join(parts[:i])
        if sub not in sys.modules:
            sys.modules[sub] = make_stub(sub)


def attempt():
    if mode == "module":
        importlib.import_module(target)
    else:
        spec = importlib.util.spec_from_file_location(
            "gate_entry", target)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)


stubbed = []
for _try in range(60):
    before = set(sys.modules)
    try:
        attempt()
        print("RESULT " + json.dumps(
            {"ok": True, "stubbed": stubbed,
             "rss_mb": round(resource.getrusage(
                 resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
        sys.exit(0)
    except ModuleNotFoundError as e:
        missing = (e.name or "").split(".")[0]
        full = e.name or ""
        if (not full or missing in STDLIB or missing in REMOVED_STDLIB
                or missing in REPO_TOP or full in stubbed):
            print("RESULT " + json.dumps({
                "ok": False, "exc": type(e).__name__, "msg": str(e),
                "stubbed": stubbed,
                "rss_mb": round(resource.getrusage(
                    resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
            sys.exit(1)
        for m in set(sys.modules) - before:
            del sys.modules[m]
        install_stub(full)
        stubbed.append(full)
    except BaseException as e:  # noqa: BLE001 - report everything
        frames = [f"{f.filename}:{f.lineno}" for f in
                  traceback.extract_tb(e.__traceback__)
                  if root in f.filename][-4:]
        print("RESULT " + json.dumps({
            "ok": False, "exc": type(e).__name__, "msg": str(e)[:400],
            "frames": frames, "stubbed": stubbed,
            "rss_mb": round(resource.getrusage(
                resource.RUSAGE_SELF).ru_maxrss / 1024, 1)}))
        sys.exit(1)
print("RESULT " + json.dumps(
    {"ok": False, "exc": "StubLoopExhausted", "msg": "",
     "stubbed": stubbed}))
"""


def compile_pass(root: Path) -> list[str]:
    """Byte-compile every .py under the agent dirs + mesh."""
    failures = []
    for top in AGENT_DIRS + ["mesh"]:
        base = root / top
        if not base.is_dir():
            continue
        for py in base.rglob("*.py"):
            try:
                compile(py.read_bytes(), str(py), "exec")
            except (SyntaxError, ValueError) as e:
                failures.append(f"{py.relative_to(root)}: {e}")
    return failures


def run_agent(root: Path, spec, extra_env) -> dict:
    name, workdir, ppaths, mode, target = spec
    env = dict(os.environ)
    env.update(BASE_ENV)
    env.update(AGENT_ENV.get(name, {}))
    env.update(extra_env.get(name, {}))
    env["PYTHONPATH"] = os.pathsep.join(
        str(root) if p == "." else str(root / p) for p in ppaths)
    tgt = target if mode == "module" else str(root / target)
    import time as _time
    _t0 = _time.monotonic()
    try:
        p = subprocess.run(
            [sys.executable, "-c", RUNNER, str(root), mode, tgt],
            capture_output=True, text=True, timeout=180,
            cwd=str(root / workdir), env=env)
    except subprocess.TimeoutExpired:
        return {"ok": False, "exc": "Timeout",
                "msg": "import exceeded 180s"}
    _wall = round(_time.monotonic() - _t0, 2)
    line = next((ln for ln in p.stdout.splitlines()
                 if ln.startswith("RESULT ")), None)
    if line is None:
        return {"ok": False, "exc": "RunnerError",
                "msg": (p.stderr or p.stdout)[-300:]}
    _r = json.loads(line[len("RESULT "):])
    _r["wall_s"] = _wall
    return _r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=None,
                    help="repo root (default: parent of this script)")
    ap.add_argument("--agents", default=None,
                    help="comma-separated subset of agent names")
    args = ap.parse_args()

    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        print(f"REFUSED: this gate is only meaningful under Python "
              f"3.11/3.12, the fleet interpreter line (running "
              f"{sys.version.split()[0]}). Below 3.11 is the retired "
              f"production line; 3.13+ is not the fleet target — a "
              f"PASS under either would not say anything about "
              f"production's interpreter.")
        return 2
    root = (Path(args.root).resolve() if args.root
            else Path(__file__).resolve().parent.parent)

    # Scratch dir for VyralX's throwaway SQLite files. makedirs rather
    # than tempfile.mkdtemp: tempfile's usability probe writes to the
    # candidate file, which some sandboxed environments deny even for
    # otherwise-writable directories.
    tmp = Path(os.environ.get("TMPDIR", "/tmp")) / f"py311-gate-{os.getpid()}"
    tmp.mkdir(parents=True, exist_ok=True)
    extra_env = {
        "VyralX": {
            # See module docstring: development/test configuration is
            # the only mode in which VyralX's entrypoint can be
            # imported without a reachable Oracle database.
            "APP_ENV": "development",
            "ENVIRONMENT": "development",
            "DATABASE_URL": f"sqlite:///{tmp}/vyralx.db",
            "MEDIA_DATABASE_URL": f"sqlite:///{tmp}/vyralx_media.db",
        },
    }

    failures = compile_pass(root)
    if failures:
        print(f"COMPILE FAIL ({len(failures)} files do not compile "
              f"under Python {sys.version.split()[0]}):")
        for f in failures[:20]:
            print(f"  {f}")
    else:
        print(f"compile: all agent + mesh sources compile under "
              f"Python {sys.version.split()[0]}")

    specs = AGENTS
    if args.agents:
        want = {a.strip() for a in args.agents.split(",")}
        specs = [s for s in AGENTS if s[0] in want]
    results = {}
    for spec in specs:
        r = run_agent(root, spec, extra_env)
        results[spec[0]] = r
        if r.get("ok"):
            note = (f" (stubbed third-party: {', '.join(r['stubbed'])})"
                    if r.get("stubbed") else "")
            print(f"{spec[0]:10s} PASS{note} "
                  f"[rss={r.get('rss_mb')}MB wall={r.get('wall_s')}s]")
        else:
            frames = "; ".join(r.get("frames", [])[-2:])
            print(f"{spec[0]:10s} FAIL [{r.get('exc')}] "
                  f"{r.get('msg', '')[:160]} {frames}")

    bad = [n for n, r in results.items() if not r.get("ok")]
    if failures or bad:
        print(f"\nGATE FAIL: compile_failures={len(failures)} "
              f"import_failures={bad}")
        return 1
    print(f"\nGATE PASS: all {len(results)} agent entrypoints import "
          f"under Python {sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
