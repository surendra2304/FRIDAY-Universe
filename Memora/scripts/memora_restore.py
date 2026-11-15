#!/usr/bin/env python3
"""Memora restore from a TASK-MEM-007 export directory (throwaway targets).

Restores an export produced by scripts/memora_export.py into the store
configured by DATABASE_URL:

  * relational rows are re-inserted with their ORIGINAL ids, timestamps,
    lifecycle states and provenance (direct ORM inserts — the write pipeline
    is deliberately bypassed so a restore is a copy, not a re-ingestion);
  * vectors are written to the native vector table via the Oracle vector
    adapter (its SQLite emulation path on a local target) AND can be loaded
    into the in-process vector adapter with --load-search-vectors so a local
    instance answers hybrid search immediately;
  * verification compares restored counts and per-record content hashes
    against the export and prints a JSON report.

SAFETY: the drill target is a throwaway store. This script REFUSES to run
against an Oracle DSN unless --i-understand-this-is-a-live-target is passed,
and refuses outright when MEMORA_ENV/ENVIRONMENT is production without that
flag. Restoring over a live store is a coordinator-run operation, never a
default.

Environment:
  MEMORA_ENV=testing            required for SQLite targets (test backend gate)
  DATABASE_URL=sqlite:////abs/path/restored.db
  MEMORA_EXPORT_DIR             export directory (default /tmp/mem007/export)
  MEMORA_DIR                    Memora service directory (for sys.path)
Usage:
  python3 memora_restore.py [--verify-only] [--load-search-vectors]
"""
import argparse
import hashlib
import json
import os
import struct
import sys
from datetime import datetime

VECTOR_DIM = 384
JSON_COLS = {"provenance", "entities", "actions", "details", "payload"}


def _parse_dt(v):
    if v is None or isinstance(v, datetime):
        return v
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def _content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--load-search-vectors", action="store_true")
    ap.add_argument("--i-understand-this-is-a-live-target", action="store_true")
    args = ap.parse_args()

    memora_dir = os.environ.get("MEMORA_DIR", os.getcwd())
    export_dir = os.environ.get("MEMORA_EXPORT_DIR", "/tmp/mem007/export")
    os.chdir(memora_dir)
    sys.path.insert(0, memora_dir)

    db_url = os.environ.get("DATABASE_URL", "")
    is_oracle = db_url.lower().startswith(("oracle",))
    env = (os.environ.get("ENVIRONMENT") or os.environ.get("MEMORA_ENV") or "").lower()
    if (is_oracle or env == "production") and not args.i_understand_this_is_a_live_target:
        print("REFUSED: target looks live (Oracle DSN or production env). "
              "The drill restores into a throwaway store; pass "
              "--i-understand-this-is-a-live-target only for a coordinated "
              "production restore.", file=sys.stderr)
        return 2

    manifest = json.load(open(os.path.join(export_dir, "manifest.json")))

    def read_jsonl(name):
        path = os.path.join(export_dir, name)
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(ln) for ln in fh if ln.strip()]

    export = {
        "agents": read_jsonl("agents.jsonl"),
        "namespaces": read_jsonl("namespaces.jsonl"),
        "access_grants": read_jsonl("access_grants.jsonl"),
        "memory_records": read_jsonl("memory_records.jsonl"),
        "memory_shared_agents": read_jsonl("memory_shared_agents.jsonl"),
        "memory_relationships": read_jsonl("memory_relationships.jsonl"),
    }
    vec_index = json.load(open(os.path.join(export_dir, "vectors_index.json")))
    vec_blob = open(os.path.join(export_dir, "vectors.bin"), "rb").read()
    assert len(vec_blob) == len(vec_index) * VECTOR_DIM * 4, "vectors.bin size mismatch"
    vectors = {}
    for i, meta in enumerate(vec_index):
        vals = struct.unpack_from(f"<{VECTOR_DIM}f", vec_blob, i * VECTOR_DIM * 4)
        vectors[meta["id"]] = (meta.get("tenant_id") or "default", list(vals), meta.get("payload"))

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from storage.relational.base import Base
    import storage.relational.models as M  # noqa: F401  (registers tables)

    engine = create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    report = {"export_dir": export_dir, "target": db_url.split("@")[-1] if "@" in db_url else db_url,
              "manifest_tables": manifest.get("tables", {})}

    if not args.verify_only:
        def conv(row, dt_fields, enum_fields):
            out = {}
            for k, v in row.items():
                if k in dt_fields:
                    out[k] = _parse_dt(v)
                elif k in enum_fields:
                    out[k] = enum_fields[k](v) if v is not None else None
                else:
                    out[k] = v
            return out

        dt_agent = {"created_at"}
        for r in export["agents"]:
            db.merge(M.Agent(**conv(r, dt_agent, {})))
        db.commit()
        for r in export["namespaces"]:
            db.merge(M.Namespace(**conv(r, dt_agent,
                                         {"type": M.NamespaceType})))
        db.commit()
        for r in export["access_grants"]:
            db.merge(M.AccessGrant(**conv(r, {"created_at", "expires_at"}, {})))
        db.commit()

        dt_rec = {"observed_at", "valid_from", "valid_until", "expires_at",
                  "created_at", "last_verified_at"}
        enum_rec = {"memory_type": M.MemoryType, "lifecycle_state": M.LifecycleState,
                    "scope": M.MemoryScopeType}
        # superseded_by_id is a self-FK: insert without it, then patch.
        deferred = {}
        for r in export["memory_records"]:
            row = conv(r, dt_rec, enum_rec)
            if row.get("superseded_by_id"):
                deferred[row["id"]] = row.pop("superseded_by_id")
            db.merge(M.MemoryRecord(**row))
        db.commit()
        for rid, sup in deferred.items():
            rec = db.get(M.MemoryRecord, rid)
            if rec is not None:
                rec.superseded_by_id = sup
        db.commit()

        for r in export["memory_shared_agents"]:
            db.merge(M.MemorySharedAgent(**conv(r, dt_agent, {})))
        for r in export["memory_relationships"]:
            db.merge(M.MemoryRelationship(**conv(r, dt_agent, {})))
        db.commit()

        # Vectors into the persistent vector table (adapter emulation on
        # non-Oracle targets; native VECTOR on Oracle targets).
        try:
            from storage.vector.oracle_vector_adapter import oracle_vector_adapter
            ok = 0
            for vid, (tenant, vals, payload) in vectors.items():
                if oracle_vector_adapter.upsert_embedding(
                        vid, vals, payload=payload if isinstance(payload, dict) else {},
                        tenant_id=tenant, db=db):
                    ok += 1
            db.commit()
            report["vectors_written"] = ok
        except Exception as exc:
            db.rollback()
            report["vectors_written"] = f"ERROR {type(exc).__name__}: {exc}"

    # ---- verification: counts + content hashes, export vs restored ----
    from sqlalchemy import func
    counts = {
        "agents": db.query(func.count(M.Agent.id)).scalar(),
        "namespaces": db.query(func.count(M.Namespace.id)).scalar(),
        "access_grants": db.query(func.count(M.AccessGrant.id)).scalar(),
        "memory_records": db.query(func.count(M.MemoryRecord.id)).scalar(),
        "memory_shared_agents": db.query(func.count(M.MemorySharedAgent.id)).scalar(),
        "memory_relationships": db.query(func.count(M.MemoryRelationship.id)).scalar(),
    }
    exp_hashes = {r["id"]: _content_hash(r.get("content_text") or "")
                  for r in export["memory_records"]}
    got = db.query(M.MemoryRecord.id, M.MemoryRecord.content_text).all()
    got_hashes = {rid: _content_hash(txt or "") for rid, txt in got}
    matched = sum(1 for rid, h in exp_hashes.items() if got_hashes.get(rid) == h)
    report["restored_counts"] = counts
    report["records_expected"] = len(exp_hashes)
    report["records_present"] = len(got_hashes)
    report["content_hash_matched"] = matched
    report["content_hash_match_rate"] = (matched / len(exp_hashes)) if exp_hashes else 1.0
    report["vectors_in_export"] = len(vectors)
    report["counts_match_manifest"] = all(
        counts[k] == manifest.get("tables", {}).get(k, counts[k])
        for k in counts)

    if args.load_search_vectors:
        from storage.vector.qdrant_adapter import vector_adapter
        loaded = 0
        for vid, (tenant, vals, payload) in vectors.items():
            if vector_adapter.upsert_embedding(vid, vals, tenant_id=tenant):
                loaded += 1
        report["search_vectors_loaded"] = loaded

    print(json.dumps(report, indent=1, default=str))
    ok_all = (report["counts_match_manifest"]
              and report["content_hash_match_rate"] == 1.0
              and report["records_present"] == report["records_expected"])
    print("RESTORE_VERIFY_OK" if ok_all else "RESTORE_VERIFY_MISMATCH")
    return 0 if ok_all else 1


if __name__ == "__main__":
    raise SystemExit(main())
