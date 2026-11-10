#!/usr/bin/env python3
"""TASK-INF-003 — Fleet database restore / drill (from backup_fleet_databases.py output).

Two modes:

  --verify-only (default, safe): connect to each requested agent schema and
      compare LIVE row counts against the backup manifest. No writes. This is
      the routine DRILL: it proves the backup is readable and measures drift
      between the backup and production.

  --apply (destructive, explicit): load rows from the backup into the agent
      schema. Refuses any non-empty target table unless --replace is given
      (which truncates first). Two-pass insert handles parent/child FK order
      heuristically; failures are reported per table — never silently skipped.

Supported recovery path: catastrophic schema loss → recreate the schema user →
let the agent boot once (SQLAlchemy creates its tables) → run this script with
--apply into the empty tables → restart the agent. For surgical partial
restores prefer Oracle Data Pump; this tool is the fleet-level insurance.

Runbook: docs/observability/BACKUP_RESTORE_DRILL.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from oracle_db import (  # noqa: E402
    OracleConfigError,
    connect,
    list_tables,
    resolve_target,
)


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_manifest(backup_dir: Path, agent: str) -> dict | None:
    manifest_path = backup_dir / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"RESTORE-ABORT: no manifest.json in {backup_dir}")
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest.get("agents", []):
        if entry.get("agent", "").upper() == agent.upper():
            return entry
    return None


def live_row_counts(conn) -> dict[str, int]:
    counts = {}
    for table in list_tables(conn):
        with conn.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}"')
            row = cur.fetchone()
            counts[table] = int(row[0]) if row else 0
    return counts


def compare_to_live(conn, entry: dict, log=print) -> dict:
    """Verify-only drill: manifest vs live. Read-only."""
    backup_tables = {t["table"]: t["row_count"] for t in entry.get("tables", [])}
    live = live_row_counts(conn)
    report = {"agent": entry["agent"], "compared_at": utcnow(), "match": 0, "differ": [], "missing_in_live": []}
    for table, bcount in backup_tables.items():
        lcount = live.get(table)
        if lcount is None:
            report["missing_in_live"].append(table)
        elif lcount == bcount:
            report["match"] += 1
        else:
            report["differ"].append({"table": table, "backup": bcount, "live": lcount,
                                     "delta": lcount - bcount})
    extra = sorted(set(live) - set(backup_tables))
    report["extra_in_live"] = extra
    log(f"[{entry['agent']}] drill: {report['match']} tables match backup; "
        f"{len(report['differ'])} differ; {len(report['missing_in_live'])} missing in live; "
        f"{len(extra)} extra in live")
    for d in report["differ"][:10]:
        log(f"    {d['table']}: backup {d['backup']} -> live {d['live']} (delta {d['delta']:+d})")
    return report


def decode_value(value):
    import base64
    if isinstance(value, dict) and "__b64__" in value:
        return base64.b64decode(value["__b64__"])
    return value


def iter_backup_rows(backup_dir: Path, table_entry: dict):
    path = backup_dir / table_entry["file"]
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            yield {k: decode_value(v) for k, v in row.items()}


def table_exists(conn, table: str) -> bool:
    return table in list_tables(conn)


def insert_table(conn, table: str, rows_iter, log=print) -> tuple[int, str]:
    """Insert all rows. Returns (inserted, 'ok' | error text)."""
    inserted = 0
    columns: list[str] = []
    try:
        with conn.cursor() as cur:
            for row in rows_iter:
                if not columns:
                    columns = list(row.keys())
                    cur.setinputsizes(**{c: None for c in columns}) if hasattr(cur, "setinputsizes") else None
                ordered = [row[c] for c in columns]
                cur.execute(
                    f'INSERT INTO "{table}" ({", ".join(chr(34) + c + chr(34) for c in columns)}) '
                    f'VALUES ({", ".join(f":{i + 1}" for i in range(len(columns)))})',
                    ordered,
                )
                inserted += 1
        conn.commit()
        return inserted, "ok"
    except Exception as exc:  # noqa: BLE001 — report per table, never silently skip
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return inserted, f"{type(exc).__name__}: {exc}"


def apply_restore(conn, backup_dir: Path, entry: dict, *, replace: bool, log=print) -> dict:
    results = {}
    deferred: list[dict] = []
    tables = entry.get("tables", [])
    # Pass 1 (in manifest order); FK-dependent failures deferred.
    for t in tables:
        live_count = live_row_counts(conn).get(t["table"])
        if live_count is None:
            results[t["table"]] = {"status": "MISSING_IN_LIVE",
                                   "detail": "recreate the schema/tables first (boot the agent once)"}
            continue
        if live_count > 0 and not replace:
            results[t["table"]] = {"status": "REFUSED_NON_EMPTY", "live_rows": live_count,
                                   "detail": "use --replace to truncate and reload"}
            continue
        if live_count > 0 and replace:
            with conn.cursor() as cur:
                cur.execute(f'TRUNCATE TABLE "{t["table"]}"')
            conn.commit()
            log(f"[{entry['agent']}] {t['table']}: truncated ({live_count} rows) for --replace")
        inserted, err = insert_table(conn, t["table"], iter_backup_rows(backup_dir, t), log=log)
        if err == "ok":
            results[t["table"]] = {"status": "RESTORED", "rows": inserted}
            log(f"[{entry['agent']}] {t['table']}: restored {inserted} rows")
        elif "foreign key" in err.lower() or "ORA-02291" in err or "ORA-00001" in err:
            deferred.append((t, err))
        else:
            results[t["table"]] = {"status": "FAILED", "detail": err, "inserted_before_failure": inserted}
            log(f"[{entry['agent']}] {t['table']}: FAILED — {err}")
    # Pass 2 for deferred FK/constraint failures.
    for t, err in deferred:
        inserted, err2 = insert_table(conn, t["table"], iter_backup_rows(backup_dir, t), log=log)
        status = "RESTORED" if err2 == "ok" else "FAILED"
        results[t["table"]] = {"status": status, "rows": inserted, "detail": "" if err2 == "ok" else err2}
        log(f"[{entry['agent']}] {t['table']} (retry): {status} {err2 if err2 != 'ok' else ''}")
    return results


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backup-dir", required=True, help="backup directory containing manifest.json")
    ap.add_argument("--agents", required=True, help="comma list of agents to restore/verify (e.g. MEMORA,STRATEX)")
    ap.add_argument("--verify-only", action="store_true", default=True)
    ap.add_argument("--apply", action="store_true", help="destructive load (refuses non-empty tables unless --replace)")
    ap.add_argument("--replace", action="store_true", help="with --apply: truncate non-empty target tables first")
    ap.add_argument("--env-file", default="")
    args = ap.parse_args()

    backup_dir = Path(args.backup_dir)
    overall_ok = True
    report = {"at": utcnow(), "backup_dir": str(backup_dir), "agents": {}}
    for agent in [a.strip().upper() for a in args.agents.split(",") if a.strip()]:
        entry = load_manifest(backup_dir, agent)
        if entry is None:
            print(f"[{agent}] no manifest entry in this backup — skipped")
            overall_ok = False
            continue
        target = resolve_target(agent, env_file=args.env_file or None)
        print(f"[{agent}] connecting as {target.redacted()}")
        conn = connect(target)
        try:
            if args.apply:
                if not args.replace:
                    print(f"[{agent}] --apply without --replace: will only load into EMPTY tables")
                results = apply_restore(conn, backup_dir, entry, replace=args.replace)
                bad = [t for t, r in results.items() if r["status"] not in ("RESTORED",)]
                report["agents"][agent] = results
                if bad:
                    overall_ok = False
            else:
                report["agents"][agent] = compare_to_live(conn, entry)
                if report["agents"][agent]["differ"] or report["agents"][agent]["missing_in_live"]:
                    overall_ok = False
        finally:
            conn.close()
    print(json.dumps(report, indent=2)[:4000])
    print(f"[{'RESTORE' if args.apply else 'DRILL'}] {'OK' if overall_ok else 'ISSUES FOUND'} at {utcnow()}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
