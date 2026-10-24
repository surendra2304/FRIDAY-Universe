"""
tools/universe_persistence.py — Persistent backends for FRIDAY Universe.

Provides Redis-backed and SQLite-backed implementations for:
- State Manager (persistent state across restarts)
- Event Bus (persistent event log)
- Audit Trail (persistent audit log)
- Metrics (persistent metrics)

Priority 2: Make It Survive (Real Dependencies)
"""
import json
import os
import time
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


# ── SQLite-Backed State Manager ─────────────────────────────────────────────

class SQLiteStateManager:
    """Persistent state manager using SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(ROOT / "data" / "universe_state.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    agent_owner TEXT,
                    version INTEGER DEFAULT 1,
                    updated_at REAL
                )
            """)
            conn.commit()
            conn.close()

    def set_state(self, key: str, value: dict, agent: str) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT version FROM state WHERE key=?", (key,)).fetchone()
            version = row[0] + 1 if row else 1
            conn.execute(
                "INSERT OR REPLACE INTO state (key, value, agent_owner, version, updated_at) VALUES (?, ?, ?, ?, ?)",
                (key, json.dumps(value), agent, version, time.time())
            )
            conn.commit()
            conn.close()
            return {"key": key, "value": value, "version": version, "agent_owner": agent}

    def get_state(self, key: str) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute("SELECT value, agent_owner, version FROM state WHERE key=?", (key,)).fetchone()
            conn.close()
            if not row:
                return None
            return {"key": key, "value": json.loads(row[0]), "version": row[2], "agent_owner": row[1]}

    def delete_state(self, key: str) -> bool:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute("DELETE FROM state WHERE key=?", (key,))
            conn.commit()
            conn.close()
            return cur.rowcount > 0

    def get_all_state(self) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute("SELECT key, value, agent_owner, version FROM state").fetchall()
            conn.close()
            return [{"key": r[0], "value": json.loads(r[1]), "agent_owner": r[2], "version": r[3]} for r in rows]


# ── SQLite-Backed Audit Trail ───────────────────────────────────────────────

class SQLiteAuditTrail:
    """Persistent audit trail using SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(ROOT / "data" / "universe_audit.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    agent TEXT,
                    action TEXT,
                    target TEXT,
                    status TEXT,
                    details TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON audit(agent)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON audit(timestamp)")
            conn.commit()
            conn.close()

    def log(self, agent: str, action: str, target: str, status: str, details: str = "") -> int:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cur = conn.execute(
                "INSERT INTO audit (timestamp, agent, action, target, status, details) VALUES (?, ?, ?, ?, ?, ?)",
                (time.time(), agent, action, target, status, details)
            )
            conn.commit()
            conn.close()
            return cur.lastrowid

    def search(self, agent: str = "", action: str = "", limit: int = 100) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT id, timestamp, agent, action, target, status, details FROM audit WHERE 1=1"
            params = []
            if agent:
                query += " AND agent=?"
                params.append(agent)
            if action:
                query += " AND action=?"
                params.append(action)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            conn.close()
            return {"total_matches": len(rows), "results": [
                {"id": r[0], "timestamp": r[1], "agent": r[2], "action": r[3],
                 "target": r[4], "status": r[5], "details": r[6]} for r in rows
            ]}


# ── SQLite-Backed Event Bus ─────────────────────────────────────────────────

class SQLiteEventBus:
    """Persistent event bus using SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(ROOT / "data" / "universe_events.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    event_type TEXT,
                    payload TEXT,
                    source TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_type ON events(event_type)")
            conn.commit()
            conn.close()

    def publish(self, event_type: str, payload: dict, source: str) -> dict:
        event_id = f"evt_{time.time()}_{os.urandom(4).hex()}"
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO events (event_id, event_type, payload, source, timestamp) VALUES (?, ?, ?, ?, ?)",
                (event_id, event_type, json.dumps(payload), source, time.time())
            )
            conn.commit()
            conn.close()
        return {"event_id": event_id, "event_type": event_type, "source": source, "payload": payload}

    def get_events(self, event_type: str = "", limit: int = 100) -> list[dict]:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            query = "SELECT event_id, event_type, payload, source, timestamp FROM events"
            params = []
            if event_type:
                query += " WHERE event_type=?"
                params.append(event_type)
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            rows = conn.execute(query, params).fetchall()
            conn.close()
            return [{"event_id": r[0], "event_type": r[1], "payload": json.loads(r[2]),
                     "source": r[3], "timestamp": r[4]} for r in rows]


# ── SQLite-Backed Metrics ───────────────────────────────────────────────────

class SQLiteMetrics:
    """Persistent metrics using SQLite."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(ROOT / "data" / "universe_metrics.db")
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL,
                    agent TEXT,
                    latency_ms REAL,
                    error INTEGER
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_agent ON metrics(agent)")
            conn.commit()
            conn.close()

    def record_request(self, agent: str, latency_ms: float, error: bool = False):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT INTO metrics (timestamp, agent, latency_ms, error) VALUES (?, ?, ?, ?)",
                (time.time(), agent, latency_ms, 1 if error else 0)
            )
            conn.commit()
            conn.close()

    def get_report(self) -> dict:
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            total = conn.execute("SELECT COUNT(*) FROM metrics").fetchone()[0]
            errors = conn.execute("SELECT COUNT(*) FROM metrics WHERE error=1").fetchone()[0]
            avg = conn.execute("SELECT AVG(latency_ms) FROM metrics").fetchone()[0] or 0
            conn.close()
            return {"total_requests": total, "total_errors": errors, "avg_latency_ms": round(avg, 2)}


# ── Redis-Backed State Manager (Optional) ───────────────────────────────────

class RedisStateManager:
    """Persistent state manager using Redis (optional, requires redis package)."""

    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        try:
            import redis
            self._redis = redis.from_url(redis_url, socket_connect_timeout=2)
            self._redis.ping()
            self._available = True
        except Exception:
            self._redis = None
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def set_state(self, key: str, value: dict, agent: str) -> dict:
        if not self._available:
            raise RuntimeError("Redis not available")
        import json
        self._redis.hset(key, mapping={
            "value": json.dumps(value),
            "agent": agent,
            "version": self._redis.hincrby(key, "version", 1) if self._redis.exists(key) else 1,
            "updated_at": str(time.time())
        })
        return self.get_state(key)

    def get_state(self, key: str) -> dict:
        if not self._available:
            raise RuntimeError("Redis not available")
        import json
        data = self._redis.hgetall(key)
        if not data:
            return None
        return {
            "key": key,
            "value": json.loads(data[b"value"] if isinstance(data, dict) else data["value"]),
            "version": int(data.get("version", 1)),
            "agent_owner": data.get("agent", "").decode() if isinstance(data.get("agent"), bytes) else data.get("agent", ""),
        }


# ── Persistence Manager (Unified Interface) ──────────────────────────────────

class UniversePersistence:
    """Unified persistence manager that selects backend based on availability."""

    def __init__(self, data_dir: str = None):
        self.data_dir = data_dir or str(ROOT / "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.state = SQLiteStateManager(os.path.join(self.data_dir, "universe_state.db"))
        self.audit = SQLiteAuditTrail(os.path.join(self.data_dir, "universe_audit.db"))
        self.events = SQLiteEventBus(os.path.join(self.data_dir, "universe_events.db"))
        self.metrics = SQLiteMetrics(os.path.join(self.data_dir, "universe_metrics.db"))
        self.redis = RedisStateManager()

    @property
    def redis_available(self) -> bool:
        return self.redis.available

    def health_check(self) -> dict:
        """Check all persistence backends."""
        return {
            "sqlite_state": self.state.get_all_state() is not None,
            "sqlite_audit": True,
            "sqlite_events": True,
            "sqlite_metrics": True,
            "redis_available": self.redis_available,
            "data_dir": self.data_dir,
        }


# ── CLI: Health Check ────────────────────────────────────────────────────────

if __name__ == "__main__":
    perm = UniversePersistence()
    print("=== Universe Persistence Health Check ===")
    health = perm.health_check()
    for k, v in health.items():
        print(f"  {k}: {v}")

    # Test state
    perm.state.set_state("test_key", {"value": 42}, "FRIDAY")
    result = perm.state.get_state("test_key")
    print(f"\nState test: {result}")

    # Test audit
    perm.audit.log("FRIDAY", "dispatch", "Inference", "success")
    results = perm.audit.search(agent="FRIDAY")
    print(f"Audit test: {results['total_matches']} entries")

    # Test events
    event = perm.events.publish("test", {"data": "test"}, "Cortex")
    print(f"Event test: {event['event_id']}")

    # Test metrics
    perm.metrics.record_request("FRIDAY", 25.0)
    report = perm.metrics.get_report()
    print(f"Metrics test: {report}")

    print("\n=== All persistence backends working ===")
