"""TASK-MEM-009: deploy-path migration step + post-deploy smoke probe.

On 2026-11-17 a merged Alembic migration never ran on production
because nothing in Memora's deploy/start path ran Alembic, and the
memory paths failed for ~1.5h while /health stayed green. These tests
pin the systemic fix:

- ``Memora/scripts/run_migrations.py`` (the ExecStartPre runner):
  upgrades a fresh database to head, is idempotent at head (it runs on
  EVERY service start), repairs the exact production drift shape
  (schema objects ahead of the alembic version row), and exits
  non-zero when a migration fails so systemd fails the start loudly.
- The wiring: ``deploy/setup_fleet.sh`` carries the ExecStartPre and
  the Fleet CD workflow runs the smoke probe after the health gate.
- ``Memora/scripts/smoke_memory_path.py``: passes a healthy fake
  Memora and fails the 2026-11-17 outage shape — HTTP 200 with
  ``stored: false`` (``pipeline_refused: DatabaseError``) — plus the
  search-miss and cleanup-failure shapes; and, against the real app,
  passes at head and fails against a schema-behind database whose
  ``memory_records`` lacks ``dedupe_key`` (the ORA-00904 analogue).
- The f8a2d6c14b93 case-safety cleanup: Oracle's inspector returns
  UPPERCASE identifiers; the migration must see its own already
  created table/columns as present instead of re-adding them.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]  # Memora/
REPO_ROOT = ROOT.parent
HEAD = "c9d4e7a1b5f2"
DRIFTED_REVISION = "a1d4c7e9f2b3"  # where production sat during the outage


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runner = _load_module("mem009_run_migrations", ROOT / "scripts" / "run_migrations.py")
smoke = _load_module("mem009_smoke_memory_path", ROOT / "scripts" / "smoke_memory_path.py")


def _engine(tmp_path: Path, name: str = "mem009.db"):
    return sa.create_engine(f"sqlite:///{tmp_path / name}")


def _head() -> str:
    config = Config(str(runner.DEFAULT_CONFIG_PATH))
    return ScriptDirectory.from_config(config).get_current_head()


# ---------------------------------------------------------------------------
# Migration runner
# ---------------------------------------------------------------------------


def test_runner_upgrades_fresh_database_to_head(tmp_path):
    assert _head() == HEAD  # pin: the drift assertions below depend on it
    engine = _engine(tmp_path)
    before, after = runner.upgrade_to_head(engine)
    assert before is None
    assert after == HEAD
    tables = set(sa.inspect(engine).get_table_names())
    assert "memory_records" in tables
    assert "context_snapshots" in tables


def test_runner_is_idempotent_at_head(tmp_path):
    """ExecStartPre runs on every start; a second run must be a no-op."""
    engine = _engine(tmp_path)
    runner.upgrade_to_head(engine)
    before, after = runner.upgrade_to_head(engine)
    assert (before, after) == (HEAD, HEAD)


def test_runner_repairs_production_drift_shape(tmp_path):
    """The 2026-11-17 state: create_all-shaped schema, version row 3 behind.

    Boot-path convergence had already created the head-shape objects
    (incl. memory_records.dedupe_key and its unique index) while
    alembic_version sat at a1d4c7e9f2b3. The runner must converge the
    version row to head without trying to recreate anything.
    """
    from storage.relational.base import Base
    import storage.relational.models  # noqa: F401 - registers the models

    engine = _engine(tmp_path)
    Base.metadata.create_all(engine)
    config = Config(str(runner.DEFAULT_CONFIG_PATH))
    config.attributes["connection"] = engine
    command.stamp(config, DRIFTED_REVISION)

    before, after = runner.upgrade_to_head(engine)
    assert (before, after) == (DRIFTED_REVISION, HEAD)

    columns = {c["name"] for c in sa.inspect(engine).get_columns("memory_records")}
    assert "dedupe_key" in columns
    indexes = {ix["name"] for ix in sa.inspect(engine).get_indexes("memory_records")}
    assert "uq_memory_dedupe_key" in indexes


def _poisoned_tree(tmp_path: Path) -> Path:
    """A minimal migrations tree whose only revision raises on upgrade."""
    mig = tmp_path / "poison_migrations"
    (mig / "versions").mkdir(parents=True)
    (mig / "env.py").write_text(
        "from alembic import context\n"
        "config = context.config\n"
        "connectable = config.attributes.get('connection')\n"
        "with connectable.connect() as connection:\n"
        "    context.configure(connection=connection)\n"
        "    with context.begin_transaction():\n"
        "        context.run_migrations()\n",
        encoding="utf-8",
    )
    (mig / "versions" / "0001_poison.py").write_text(
        'revision = "poison0001"\n'
        "down_revision = None\n"
        "def upgrade():\n"
        "    raise RuntimeError('poisoned migration')\n"
        "def downgrade():\n"
        "    pass\n",
        encoding="utf-8",
    )
    ini = tmp_path / "poison_alembic.ini"
    ini.write_text(
        "[alembic]\n"
        f"script_location = {mig}\n"
        "sqlalchemy.url = sqlite:///unused.db\n",
        encoding="utf-8",
    )
    return ini


def test_runner_raises_when_migration_fails(tmp_path):
    engine = _engine(tmp_path)
    with pytest.raises(Exception):
        runner.upgrade_to_head(engine, _poisoned_tree(tmp_path))


def _run_cli(tmp_path: Path, ini: Path, db_name: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(
        {
            "DATABASE_URL": f"sqlite:///{tmp_path / db_name}",
            "MEMORA_ENV": "testing",
            "ENVIRONMENT": "testing",
            "MEMORA_EMBEDDING_MODE": "hashing",
            "MEMORA_VECTOR_ENABLED": "false",
            "MEMORA_ALLOW_INMEMORY_FALLBACK": "true",
            "MEMORA_ALLOW_ANONYMOUS_DEV": "true",
            "MEMORA_ALEMBIC_INI": str(ini),
            "MEMORA_MIGRATION_LOCK_FILE": str(tmp_path / "alembic-upgrade.lock"),
            # Append, never replace: a harness-provided PYTHONPATH
            # (e.g. a shared site-packages) must survive into the child.
            "PYTHONPATH": str(ROOT) + os.pathsep + env.get("PYTHONPATH", ""),
        }
    )
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_migrations.py")],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )


def test_runner_cli_fails_loudly_on_broken_migration(tmp_path):
    """The ExecStartPre contract: non-zero exit => systemd fails the start."""
    result = _run_cli(tmp_path, _poisoned_tree(tmp_path), "cli-fail.db")
    assert result.returncode == 1
    assert "MEMORA-MIGRATION FAILED" in result.stderr


def test_runner_cli_succeeds_and_logs_revisions_on_fresh_db(tmp_path):
    result = _run_cli(tmp_path, runner.DEFAULT_CONFIG_PATH, "cli-ok.db")
    assert result.returncode == 0, result.stderr[-2000:]
    assert f"before=none after={HEAD}" in result.stdout


# ---------------------------------------------------------------------------
# Deploy/start-path wiring
# ---------------------------------------------------------------------------


def test_setup_fleet_memora_unit_runs_migrations_before_start():
    text = (REPO_ROOT / "deploy" / "setup_fleet.sh").read_text(encoding="utf-8")
    block = text.split("sudo tee /etc/systemd/system/Memora.service", 1)[1].split("\nEOF", 1)[0]
    assert "ExecStartPre=" in block
    assert "scripts/run_migrations.py" in block
    assert block.index("ExecStartPre=") < block.index("\nExecStart=")


def test_fleet_cd_runs_smoke_probe_after_health_gate_when_memora_restarted():
    text = (REPO_ROOT / ".github" / "workflows" / "deploy-monorepo.yml").read_text(encoding="utf-8")
    assert "RESTARTED_AGENTS" in text
    assert "scripts/smoke_memory_path.py" in text
    assert text.index("Health gate passed on Server 1") < text.index("scripts/smoke_memory_path.py")


def test_fleet_cd_applies_migrations_before_any_restart():
    """The live unit gains ExecStartPre only when setup re-runs (or the
    post-merge drop-in lands), so Fleet CD must ALSO run the migration
    step itself — before the restart loop, so a failure aborts the
    deploy with the previous code still running in memory."""
    text = (REPO_ROOT / ".github" / "workflows" / "deploy-monorepo.yml").read_text(encoding="utf-8")
    assert "scripts/run_migrations.py" in text
    assert text.index("scripts/run_migrations.py") < text.index(
        'sudo systemctl restart "${AGENT}.service"'
    )


# ---------------------------------------------------------------------------
# Smoke probe (fake transports — no live server needed)
# ---------------------------------------------------------------------------


def _fake_transport(capture=None, search=None, delete=None, get_after=None):
    state = {"marker": None}

    def transport(method, url, headers, body, timeout):
        if url.endswith("/v1/capture/events"):
            state["marker"] = body["content"].split("marker ", 1)[1].split(":", 1)[0]
            return capture or (200, {"stored": True, "id": "rec-probe-1"})
        if "/v1/memories/search" in url:
            if search is not None:
                return search
            return 200, [{"id": "rec-probe-1", "content_text": f"found: {state['marker']}"}]
        if method == "DELETE":
            return delete or (200, {"deleted": True})
        if "/v1/memories/" in url:
            return get_after or (404, {"detail": "Memory not found"})
        raise AssertionError(f"unexpected probe call: {method} {url}")

    return transport


def _run_probe(**overrides) -> bool:
    logs: list[str] = []
    return smoke.run_smoke(
        "http://127.0.0.1:8002",
        "memora",
        "test-key",
        transport=_fake_transport(**overrides),
        search_attempts=3,
        search_delay=0,
        log=logs.append,
    )


def test_probe_passes_on_healthy_memora():
    assert _run_probe() is True


def test_probe_catches_the_outage_shape_stored_false_with_http_200():
    """2026-11-17: capture answered 200 + stored:false while broken."""
    assert _run_probe(capture=(200, {"stored": False, "reason": "pipeline_refused: DatabaseError"})) is False


def test_probe_catches_http_500_on_capture():
    assert _run_probe(capture=(500, {"detail": "Internal Server Error"})) is False


def test_probe_catches_search_miss():
    assert _run_probe(search=(200, [])) is False


def test_probe_catches_search_http_500():
    """The schema-behind search shape: hybrid search 500s on the
    missing ORM column — an HTTP error must fail immediately."""
    assert _run_probe(search=(500, {"detail": "Internal Server Error"})) is False


def test_probe_fails_when_cleanup_delete_fails():
    assert _run_probe(delete=(500, {"detail": "delete failed"})) is False


def test_probe_key_loading_never_needs_the_value_printed(tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("OTHER=1\nMEMORA_API_KEY=sekrit-value\n", encoding="utf-8")
    value, source = smoke.load_key("MEMORA_API_KEY", [env_file])
    assert value == "sekrit-value"
    assert source == str(env_file)
    assert smoke.load_key("MISSING_VAR", [env_file]) == (None, None)


# ---------------------------------------------------------------------------
# f8a2d6c14b93 case safety (Oracle inspector returns UPPERCASE names)
# ---------------------------------------------------------------------------


def test_f8a2_sees_its_own_table_as_present_under_uppercase_inspector(monkeypatch):
    mod = _load_module(
        "mem009_f8a2",
        ROOT / "migrations" / "versions" / "f8a2d6c14b93_add_context_snapshots.py",
    )
    all_columns_upper = [name.upper() for name, _ in mod._COLUMNS] + ["TENANT_ID"]
    inspector = SimpleNamespace(
        get_table_names=lambda: ["CONTEXT_SNAPSHOTS"],
        get_columns=lambda table: [{"name": name} for name in all_columns_upper],
        get_indexes=lambda table: [],
    )
    monkeypatch.setattr(mod.sa, "inspect", lambda bind: inspector)

    calls: list[str] = []
    recording_op = SimpleNamespace(
        get_bind=lambda: None,
        create_table=lambda *a, **k: calls.append("create_table"),
        add_column=lambda *a, **k: calls.append("add_column"),
    )
    monkeypatch.setattr(mod, "op", recording_op)

    assert mod._existing() == {name.lower() for name in all_columns_upper}
    mod.upgrade()
    assert calls == []  # nothing re-created, nothing re-added


# ---------------------------------------------------------------------------
# Smoke probe against the REAL app (schema-behind fixture)
# ---------------------------------------------------------------------------

import importlib  # noqa: E402

from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from apps.api.main import app  # noqa: E402
from core.identity.service import IdentityService  # noqa: E402
from storage.relational.base import Base  # noqa: E402
from storage.relational.session import get_db  # noqa: E402

_oracle_module = importlib.import_module("storage.vector.oracle_vector_adapter")


class _StubOracleAdapter:
    """No semantic hits: recall is the keyword leg — deterministic."""

    def is_oracle_backend(self):
        return True

    def search_similarity(self, query_vector, limit, tenant_id, score_threshold, db=None):
        return []


@pytest.fixture(autouse=True)
def _no_vector(monkeypatch):
    monkeypatch.setattr(_oracle_module, "oracle_vector_adapter", _StubOracleAdapter())


def _client_transport(client):
    def transport(method, url, headers, body, timeout):
        parts = url.split("/", 3)
        path = "/" + parts[3] if len(parts) > 3 else "/"
        clean_headers = {k: v for k, v in headers.items() if v}
        try:
            resp = client.request(method, path, headers=clean_headers, json=body)
        except Exception as exc:  # a server 500 can surface as a raise under TestClient
            return 599, {"error": f"{type(exc).__name__}: {exc}"}
        try:
            parsed = resp.json()
        except Exception:
            parsed = resp.text[:300]
        return resp.status_code, parsed

    return transport


def _run_probe_against(client) -> tuple[bool, list[str]]:
    logs: list[str] = []
    ok = smoke.run_smoke(
        "http://testserver",
        "memora",
        "",  # test env: anonymous-dev auth resolves the named actor
        transport=_client_transport(client),
        search_attempts=3,
        search_delay=0,
        log=logs.append,
    )
    return ok, logs


def test_probe_passes_against_real_app_at_head(client, test_db):
    IdentityService.register_agent(test_db, "memora")
    ok, logs = _run_probe_against(client)
    assert ok, "\n".join(logs)
    assert any("MEMORA-SMOKE RESULT: PASS" in line for line in logs)


def test_probe_fails_against_real_app_schema_behind():
    """memory_records without dedupe_key — the ORA-00904 analogue.

    This is the exact state /health called healthy for ~1.5h on
    2026-11-17; the probe must fail, starting at the capture step
    (the write pipeline refuses with a DatabaseError)."""
    engine = sa.create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP INDEX IF EXISTS uq_memory_dedupe_key")
        ops = Operations(MigrationContext.configure(conn))
        with ops.batch_alter_table("memory_records") as batch:
            batch.drop_column("dedupe_key")
    assert "dedupe_key" not in {
        c["name"] for c in sa.inspect(engine).get_columns("memory_records")
    }

    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSession()

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app, raise_server_exceptions=False) as behind_client:
            IdentityService.register_agent(db, "memora")
            ok, logs = _run_probe_against(behind_client)
    finally:
        app.dependency_overrides.clear()
        db.close()

    assert not ok, "\n".join(logs)
    assert any("MEMORA-SMOKE RESULT: FAIL" in line for line in logs)
    assert any("capture: FAIL" in line for line in logs)
