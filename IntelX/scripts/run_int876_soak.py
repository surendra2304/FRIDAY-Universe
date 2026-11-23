#!/usr/bin/env python3
"""INT-876 soak runner (TASK-INT-032).

Runs ONE grounded live-research run against the local IntelX service and
writes the day record. Triggered once daily at 09:30 IST by
deploy/intelx-soak-runner.timer; never run by hand except as a proving run
with --force (which still writes the same day record, so the day is never
counted twice).

Trigger (the same path FRIDAY dispatch uses for research_live):
    POST {INTELX_BASE_URL}/v1/task/execute
    {"task_id": "soak-876-YYYY-MM-DD", "action": "research_live",
     "payload": {"query": SOAK_QUERY}}
authenticated with the fleet key from the environment (FRIDAY_API_KEY).
The key is never printed or logged; a missing key fails before any call.

Records (two places, both durable):
  1. The IntelX live research archive (Oracle-backed) — the run itself,
     recallable at GET /v1/research/live/{run_id}.
  2. The day record JSON at {SOAK_RECORD_DIR}/YYYY-MM-DD.json on S2
     (default /var/lib/friday-universe/intelx-soak) — run time, run id,
     outcome, counts, delivery path.

A day PASSES iff the envelope status is SUCCESS (synthesised brief).
DEGRADED is recorded honestly and does not count as a pass; it also does
not retry — the timer fires once per day and this script refuses a second
run for the same date unless --force is given, so the 09:30 silent run
can never be duplicated by the runner.

Exit codes: 0 = a run was observed and recorded (even DEGRADED);
2 = no run could be triggered/observed; 3 = the day record could not
be written. Exit 0 on DEGRADED is deliberate: a degraded day is data
for the D4 judgement, not a runner failure.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python < 3.9
    ZoneInfo = None  # type: ignore

IST = ZoneInfo("Asia/Kolkata") if ZoneInfo is not None else timezone.utc
INTELX_BASE_URL = os.environ.get("INTELX_BASE_URL", "http://127.0.0.1:8005").rstrip("/")
# Standing soak query. No authoritative soak query exists in any readable
# source (see TASK-INT-032-SOAK-RUNNER.md §5); the default mirrors the
# query of the last observed live runs (2026-11-23 09:00 IST) and the
# coordinator may override it with one line (SOAK_QUERY env or --query).
DEFAULT_QUERY = "latest AI model releases"
RECORD_DIR = Path(os.environ.get(
    "SOAK_RECORD_DIR", "/var/lib/friday-universe/intelx-soak"))
TRIGGER_TIMEOUT_S = 300
HEALTH_TIMEOUT_S = 10


def _now_ist() -> datetime:
    return datetime.now(IST)


def _get_json(url: str, timeout: int) -> tuple[int, dict]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        return e.code, body if isinstance(body, dict) else {}
    except (urllib.error.URLError, OSError, TimeoutError):
        # Unreachable / refused / timed out: not an HTTP status. Callers
        # treat 0 as "no response" and record it, never crash.
        return 0, {}


def _post_json(url: str, payload: dict, api_key: str, timeout: int) -> tuple[int, dict]:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode() or "{}")
        except Exception:
            body = {}
        return e.code, body if isinstance(body, dict) else {}
    except (urllib.error.URLError, OSError, TimeoutError):
        # Unreachable / refused / timed out: not an HTTP status.
        return 0, {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", default=os.environ.get("SOAK_QUERY", DEFAULT_QUERY),
                        help="Research query for this soak run")
    parser.add_argument("--force", action="store_true",
                        help="Run even if today's day record already exists")
    parser.add_argument("--record-dir", default=str(RECORD_DIR),
                        help="Directory for the per-day JSON record")
    args = parser.parse_args(argv)

    api_key = os.environ.get("FRIDAY_API_KEY", "")
    if not api_key:
        print("run_int876_soak: FRIDAY_API_KEY is not set; refusing to call IntelX",
              file=sys.stderr)
        return 2

    today = _now_ist().date().isoformat()
    task_id = f"soak-876-{today}"
    record_path = Path(args.record_dir) / f"{today}.json"
    if record_path.exists() and not args.force:
        print(f"run_int876_soak: day record already exists ({record_path}); "
              "not running again (use --force for a proving run)")
        return 0

    started = _now_ist()
    record: dict = {
        "date_ist": today,
        "task_id": task_id,
        "query": args.query,
        "triggered_by": "timer" if os.environ.get("INVOCATION_ID") else "manual",
        "started_at_ist": started.isoformat(),
        "started_at_utc": started.astimezone(timezone.utc).isoformat(),
        "intelx_base_url": INTELX_BASE_URL,
        "record_path": str(record_path),
        "archive_recall": f"{INTELX_BASE_URL}/v1/research/live/{{run_id}}",
    }

    # Liveness first: /healthz is 200 when the service is up (the /health
    # endpoint is 503-by-design when degraded, so it is not a liveness
    # signal). A down service is recorded, not silently skipped.
    health_status, _ = _get_json(f"{INTELX_BASE_URL}/healthz", HEALTH_TIMEOUT_S)
    if health_status != 200:
        record.update({
            "outcome": "trigger_failed",
            "reason": "intelx_unreachable",
            "healthz_status": health_status,
            "pass": False,
        })
        return _write_record(record_path, record, exit_code=2)

    http_status, envelope = _post_json(
        f"{INTELX_BASE_URL}/v1/task/execute",
        {"task_id": task_id, "action": "research_live",
         "payload": {"query": args.query}},
        api_key, TRIGGER_TIMEOUT_S)
    finished = _now_ist()
    record["finished_at_ist"] = finished.isoformat()
    record["finished_at_utc"] = finished.astimezone(timezone.utc).isoformat()
    record["duration_s"] = round((finished - started).total_seconds(), 1)
    record["http_status"] = http_status

    if http_status != 200 or not isinstance(envelope, dict):
        record.update({
            "outcome": "trigger_failed",
            "reason": f"http_{http_status}",
            "detail": str(envelope.get("detail", ""))[:200]
            if isinstance(envelope, dict) else "",
            "pass": False,
        })
        return _write_record(record_path, record, exit_code=2)

    result = envelope.get("result") if isinstance(envelope.get("result"), dict) else {}
    synthesis = result.get("synthesis_status") or result.get("synthesis") or {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    record.update({
        "outcome": "observed",
        "envelope_status": str(envelope.get("status", "")).upper(),
        "run_id": result.get("run_id"),
        "durable_run": bool(result.get("durable_run")),
        "synthesis_status": synthesis.get("status") if isinstance(synthesis, dict)
        else str(synthesis),
        "synthesis_error": (synthesis.get("error") if isinstance(synthesis, dict)
                            else None),
        "sources_count": len(sources),
        "findings_count": len(findings),
        "summary": str(envelope.get("summary", ""))[:500],
        # A day passes iff IntelX returned a synthesised brief.
        "pass": str(envelope.get("status", "")).upper() == "SUCCESS",
    })
    print(f"run_int876_soak: {today} task={task_id} "
          f"status={record['envelope_status']} run_id={record['run_id']} "
          f"pass={record['pass']}")
    return _write_record(record_path, record, exit_code=0)


def _write_record(record_path: Path, record: dict, exit_code: int) -> int:
    try:
        record_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = record_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
        tmp.replace(record_path)
    except OSError as e:
        print(f"run_int876_soak: cannot write day record {record_path}: {e}",
              file=sys.stderr)
        return 3
    print(f"run_int876_soak: day record written to {record_path}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
