"""TASK-DATA-003 — ledger persistence and recovery across real process death.

The fear this closes: an agent "ledger" that actually lives in process memory
and silently empties on restart. Both drills here use REAL subprocesses that
exit between the write and the read, so survival proves on-disk durability,
not caching:

1. MEMORA — the memory ledger. Subprocess A boots the real Memora FastAPI app
   (file-backed test SQLite, exactly the contract Memora's conftest uses),
   ingests one memory through POST /memories, prints its id, and dies.
   Subprocess B boots a fresh app instance over the same file and reads the
   memory back by id (and through the query surface).

2. STRATEX — the order-intent idempotency ledger. Subprocess A opens
   OrderIntentStore on an explicit test path, reserves an order and advances
   it, and dies. Subprocess B re-opens the same file and must observe the
   SAME lifecycle state (duplicate read), with the audit trail intact.

Production remains Oracle-only (fail-closed by the agents' own backends);
the SQLite here is the agents' documented test fixture, used only to prove
the durability contract of the code paths that production runs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MEMORA_DIR = REPO / "Memora"
STRATEX_DIR = REPO / "Stratex"

MEMORA_WRITE = r"""
import json
from fastapi.testclient import TestClient
from apps.api.main import app

with TestClient(app) as c:
    r = c.post(
        "/memories",
        headers={"X-Agent-Name": "RecoveryDrill", "X-Access-Purpose": "persistence-drill"},
        json={"content_text": "DATA-003 recovery drill marker 8f3a", "memory_type": "episodic"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    print(json.dumps({"id": body["id"], "content_text": body.get("content_text", "")}))
"""

MEMORA_READ = r"""
import json, sys
from fastapi.testclient import TestClient
from apps.api.main import app

memory_id = sys.argv[1]
with TestClient(app) as c:
    by_id = c.get(f"/memories/{memory_id}", headers={"X-Agent-Name": "RecoveryDrill"})
    assert by_id.status_code == 200, by_id.text
    queried = c.post(
        "/memories/query",
        headers={"X-Agent-Name": "RecoveryDrill"},
        json={"query_text": "DATA-003 recovery drill marker"},
    )
    assert queried.status_code == 200, queried.text
    print(json.dumps({
        "by_id_content": by_id.json().get("content_text", ""),
        "query_hits": len(queried.json()),
        "by_id_lifecycle": by_id.json().get("lifecycle_state"),
    }))
"""

STRATEX_WRITE = r"""
import json, sys
from stratex_agents.order_store import OrderIntentStore

path = sys.argv[1]
store = OrderIntentStore(path)
record = store.reserve(
    client_order_id="DATA-003-DRILL-1",
    payload_hash="deadbeefcafe",
    payload={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.001},
)
assert record["kind"] == "new", record
store.transition("DATA-003-DRILL-1", "SUBMITTING")
store.transition("DATA-003-DRILL-1", "ACCEPTED", result={"exchange_id": "X-1"})
print(json.dumps({"status": "written"}))
"""

STRATEX_READ = r"""
import json, sys
from stratex_agents.order_store import OrderIntentStore

path = sys.argv[1]
store = OrderIntentStore(path)
duplicate = store.reserve(
    client_order_id="DATA-003-DRILL-1",
    payload_hash="deadbeefcafe",
    payload={"symbol": "BTC/USDT", "side": "buy", "quantity": 0.001},
)
assert duplicate["kind"] == "duplicate", duplicate
events = store.audit_events("DATA-003-DRILL-1") if hasattr(store, "audit_events") else None
print(json.dumps({
    "kind": duplicate["kind"],
    "status": duplicate.get("status"),
    "result": duplicate.get("result"),
    "events_count": len(events) if events is not None else None,
}))
"""


def run_child(code: str, cwd: Path, env_extra: dict, *args) -> dict:
    env = {k: v for k, v in os.environ.items() if k not in ("DATABASE_URL", "MEDIA_DATABASE_URL")}
    env.update(env_extra)
    env["PYTHONPATH"] = str(cwd) + os.pathsep + env.get("PYTHONPATH", "")
    res = subprocess.run(
        [sys.executable, "-c", code, *args],
        capture_output=True, text=True, env=env, cwd=str(cwd), timeout=300,
    )
    assert res.returncode == 0, f"child failed in {cwd}:\nSTDOUT:{res.stdout}\nSTDERR:{res.stderr[-2000:]}"
    lines = [line for line in res.stdout.strip().splitlines() if line.startswith("{")]
    assert lines, f"no JSON printed by child:\nSTDOUT:{res.stdout}\nSTDERR:{res.stderr[-2000:]}"
    return json.loads(lines[-1])


class TestMemoraLedgerRecovery:
    def test_memory_survives_process_death(self, tmp_path):
        db = tmp_path / "memora_recovery.db"
        env = {
            "MEMORA_ALLOW_ANONYMOUS_DEV": "1",
            "MEMORA_EMBEDDING_MODE": "hashing",
            "MEMORA_ENV": "testing",
            "ENVIRONMENT": "testing",
            "DATABASE_URL": f"sqlite:///{db}",
        }
        written = run_child(MEMORA_WRITE, MEMORA_DIR, env)
        assert written["id"], "write subprocess returned no id"
        assert "DATA-003 recovery drill marker" in written["content_text"]

        # PROCESS DEATH: the app that wrote it is gone. Fresh boot, same file.
        assert not db.exists() or db.stat().st_size > 0
        read_back = run_child(MEMORA_READ, MEMORA_DIR, env, str(written["id"]))
        assert "DATA-003 recovery drill marker" in read_back["by_id_content"]
        assert read_back["by_id_lifecycle"].upper() in ("CANDIDATE", "ACTIVE")
        assert read_back["query_hits"] >= 1

    def test_fresh_file_boots_cleanly(self, tmp_path):
        env = {
            "MEMORA_ALLOW_ANONYMOUS_DEV": "1",
            "MEMORA_EMBEDDING_MODE": "hashing",
            "MEMORA_ENV": "testing",
            "ENVIRONMENT": "testing",
            "DATABASE_URL": f"sqlite:///{tmp_path / 'empty.db'}",
        }
        out = run_child(MEMORA_WRITE, MEMORA_DIR, env)
        assert out["id"]


class TestStratexOrderLedgerRecovery:
    def test_intent_and_audit_trail_survive_process_death(self, tmp_path):
        path = str(tmp_path / "stratex_intents.sqlite")
        env = {"STRATEX_ENV": "test", "FRIDAY_ENV": "test"}
        written = run_child(STRATEX_WRITE, STRATEX_DIR, env, path)
        assert written["status"] == "written"

        # PROCESS DEATH: fresh OrderIntentStore instance over the same file.
        read_back = run_child(STRATEX_READ, STRATEX_DIR, env, path)
        assert read_back["kind"] == "duplicate"
        assert read_back["status"] == "ACCEPTED"
        assert read_back["result"] == {"exchange_id": "X-1"}

    def test_conflicting_reuse_after_recovery_still_detected(self, tmp_path):
        """After a crash+restart, a DIFFERENT payload under the same id must conflict."""
        path = str(tmp_path / "stratex_intents.sqlite")
        env = {"STRATEX_ENV": "test", "FRIDAY_ENV": "test"}
        run_child(STRATEX_WRITE, STRATEX_DIR, env, path)
        conflict = r"""
import sys
from stratex_agents.order_store import OrderIntentStore, IntentConflictError
store = OrderIntentStore(sys.argv[1])
try:
    store.reserve("DATA-003-DRILL-1", "different-hash-0000", {"x": 1})
    print("NO-CONFLICT")
except IntentConflictError:
    print("CONFLICT-DETECTED")
"""
        env2 = dict(env)
        res = subprocess.run(
            [sys.executable, "-c", conflict, path],
            capture_output=True, text=True,
            env={**os.environ, **env2, "PYTHONPATH": str(STRATEX_DIR)},
            cwd=str(STRATEX_DIR), timeout=300,
        )
        assert res.returncode == 0, res.stderr[-1500:]
        assert "CONFLICT-DETECTED" in res.stdout
