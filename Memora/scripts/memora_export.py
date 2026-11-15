#!/usr/bin/env python3
"""Memora production export — READ-ONLY (TASK-MEM-007).

Dumps the full memory store from the configured DATABASE_URL (Oracle in
production) into a portable export directory:

  agents.jsonl, namespaces.jsonl, access_grants.jsonl, memory_records.jsonl,
  memory_shared_agents.jsonl, memory_relationships.jsonl,
  vectors.bin            float32 little-endian, row order = vectors_index.json
  vectors_index.json     [{id, tenant_id, payload}] aligned with vectors.bin
  manifest.json          per-table counts, per-file sha256, export timestamp

audit_logs / event_log are append-only telemetry: their row counts are
recorded in the manifest (counted_not_exported) so a restore can be
reconciled, but their content is not part of the memory store.

Only SELECT statements are issued. This script never writes to the database.

Environment:
  MEMORA_DIR   Memora service directory (default /opt/friday_universe/Memora)
  MEMORA_EXPORT_DIR  output directory (default /tmp/mem007/export)
Run with the service venv python on the host that runs Memora.
"""
import base64
import hashlib
import json
import os
import struct
import sys
from datetime import datetime, timezone

MEMORA_DIR = os.environ.get("MEMORA_DIR", "/opt/friday_universe/Memora")
OUT = os.environ.get("MEMORA_EXPORT_DIR", "/tmp/mem007/export")
VECTOR_DIM = 384

TABLES = ["agents", "namespaces", "access_grants", "memory_records",
          "memory_shared_agents", "memory_relationships"]
JSON_COLS = {"provenance", "entities", "actions", "details", "payload"}


def _norm(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, (bytes, bytearray)):
        return {"__bytes_b64__": base64.b64encode(bytes(v)).decode()}
    if hasattr(v, "read"):
        try:
            return _norm(v.read())
        except Exception:
            return str(v)
    if isinstance(v, dict):
        return {str(k): _norm(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_norm(x) for x in v]
    return str(v)


def _maybe_json(v):
    if isinstance(v, str) and v[:1] in ("{", "["):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v


def main() -> int:
    os.makedirs(OUT, exist_ok=True)
    os.chdir(MEMORA_DIR)
    sys.path.insert(0, MEMORA_DIR)
    env_path = os.path.join(MEMORA_DIR, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    from sqlalchemy import text
    from storage.relational.session import create_db_engine

    eng = create_db_engine()
    manifest = {"task": "TASK-MEM-007",
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "source": "Memora relational store + native vector table",
                "tables": {}}
    with eng.connect() as conn:
        for tbl in TABLES:
            rows = conn.execute(text(f"SELECT * FROM {tbl}")).mappings().fetchall()
            with open(os.path.join(OUT, f"{tbl}.jsonl"), "w") as fh:
                for r in rows:
                    d = {}
                    for k, v in r.items():
                        nv = _norm(v)
                        if k in JSON_COLS:
                            nv = _maybe_json(nv)
                        d[k] = nv
                    fh.write(json.dumps(d, ensure_ascii=False, default=str) + "\n")
            manifest["tables"][tbl] = len(rows)
            print(f"exported {tbl}: {len(rows)}")

        vrows = conn.execute(text(
            "SELECT id, tenant_id, embedding, payload FROM memora_vector_store ORDER BY id"
        )).fetchall()
        index, blob = [], bytearray()
        for vid, tenant, emb, payload in vrows:
            vals = [float(x) for x in list(emb)]
            assert len(vals) == VECTOR_DIM, f"vector dim {len(vals)} for {vid}"
            blob += struct.pack(f"<{len(vals)}f", *vals)
            index.append({"id": vid, "tenant_id": tenant,
                          "payload": _maybe_json(_norm(payload))})
        with open(os.path.join(OUT, "vectors.bin"), "wb") as fh:
            fh.write(bytes(blob))
        with open(os.path.join(OUT, "vectors_index.json"), "w") as fh:
            json.dump(index, fh, ensure_ascii=False)
        manifest["tables"]["memora_vector_store"] = len(vrows)
        print(f"exported vectors: {len(vrows)}")

        for tbl in ["audit_logs", "event_log"]:
            try:
                n = conn.execute(text(f"SELECT COUNT(*) FROM {tbl}")).scalar()
                manifest.setdefault("counted_not_exported", {})[tbl] = n
            except Exception as exc:  # count is reconciliation metadata only
                manifest.setdefault("counted_not_exported", {})[tbl] = f"ERROR {type(exc).__name__}"

    for fn in sorted(os.listdir(OUT)):
        p = os.path.join(OUT, fn)
        if os.path.isfile(p) and fn != "manifest.json":
            manifest.setdefault("files", {})[fn] = {
                "bytes": os.path.getsize(p),
                "sha256": hashlib.sha256(open(p, "rb").read()).hexdigest(),
            }
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(json.dumps(manifest["tables"]))
    print("MANIFEST_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
