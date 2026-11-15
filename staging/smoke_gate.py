#!/usr/bin/env python3
"""FRIDAY Universe — staging smoke gate (TASK-REL-046).

THE pre-merge gate for agent changes under the local-first pipeline:

    python3 staging/smoke_gate.py [--boot-timeout 180] [--only NAME] [--keep]

The gate is a self-contained supervisor: it spawns the staging fleet as its
own children (staging_fleet.py recipes + production memory caps from
fleet_manifest.yaml), enforces the caps from a watchdog thread, waits for
each agent's health endpoint, fires one representative read-only probe per
agent, prints a pass/fail table, and tears the fleet down. Agents boot
SEQUENTIALLY (each must answer health before the next spawns) so the
sandbox's small RAM is spent on one import peak at a time; they then run
concurrently for the probes. With --keep it keeps supervising after the
table (Ctrl-C stops the fleet).

Exit code is 0 only if every non-exempt agent passes. Agents declared
staging-exempt in fleet_manifest.yaml are reported as EXEMPT with their
reason — never as passes.

A PASS requires: process alive under its production memory cap, health
endpoint answering HTTP 200, and the probe answered with HTTP < 500 (the
actual status code is printed in the table — nothing is hidden).

The machine-readable report lands in staging/run/smoke_report.json.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import signal
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

STAGING_DIR = Path(__file__).resolve().parent
RUN_DIR = STAGING_DIR / "run"

spec = importlib.util.spec_from_file_location("staging_fleet", STAGING_DIR / "staging_fleet.py")
fleet = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fleet)


def port_in_use(port: int) -> bool:
    import socket
    with socket.socket() as s:
        s.settimeout(1.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_get(url: str, headers: dict | None = None, timeout: float = 10.0):
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(4096)
            return resp.status, (time.time() - started) * 1000
    except urllib.error.HTTPError as e:
        return e.code, (time.time() - started) * 1000
    except Exception:
        return None, (time.time() - started) * 1000


def wait_health(agent: dict, proc, timeout: float) -> tuple[int | None, float]:
    url = f"http://127.0.0.1:{agent['port']}{agent['health_path']}"
    deadline = time.time() + timeout
    started = time.time()
    last = None
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, time.time() - started
        code, _ = http_get(url, timeout=5.0)
        last = code
        if code == 200:
            return code, time.time() - started
        time.sleep(2)
    return last, time.time() - started


def log_tail(proc, name: str, lines: int = 5) -> str:
    tail = getattr(proc, "_staging_tail", None)
    if tail:
        return " | ".join(list(tail)[-lines:])[-400:]
    path = RUN_DIR / "logs" / f"{name}.log"
    try:
        data = path.read_text(errors="replace").splitlines()
        return " | ".join(data[-lines:])[-400:]
    except OSError:
        return "(no log readable)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep", action="store_true", help="keep supervising after the table (Ctrl-C stops)")
    parser.add_argument("--boot-timeout", type=float, default=150.0)
    parser.add_argument("--python", default=None)
    parser.add_argument("--only", default=None)
    args = parser.parse_args()

    manifest = fleet.load_manifest()
    common_env = manifest.get("common_env", {})
    python = fleet.resolve_python(args.python)
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    for flag in RUN_DIR.glob("oom_*.flag"):
        flag.unlink()

    agents = [a for a in manifest["agents"] if not args.only or a["name"].lower() == args.only.lower()]
    # Pre-flight: a staging port that is already bound means a leftover
    # process would answer health checks in the new child's place — a
    # false PASS (observed in practice). Refuse to run; never kill a
    # process this gate did not spawn.
    busy = [f"{a['name']}:{a['port']}" for a in agents
            if not a.get("staging_exempt") and port_in_use(a["port"])]
    if busy:
        print(f"PRE-FLIGHT FAIL: staging port(s) already in use: {', '.join(busy)}. "
              "Stop the leftover process(es) first (staging_fleet.py stop, or kill the pid "
              "shown by `ss -ltnp`). The gate never kills processes it did not spawn.")
        return 2
    procs: dict = {}
    caps: dict = {}
    over: dict = {}
    stop_watch = threading.Event()

    def watchdog():
        while not stop_watch.is_set():
            try:
                fleet.enforce_caps_once(procs, caps, over)
            except Exception as e:  # enforcement must never die silently
                print(f"WATCHDOG PASS ERROR (continuing): {e}", flush=True)
            stop_watch.wait(2)

    wd = threading.Thread(target=watchdog, daemon=True)
    wd.start()

    rows = []
    try:
        # Phase 1 — sequential boot: spawn one agent, wait for its health,
        # then spawn the next (one import peak at a time).
        booted = {}
        for agent in agents:
            name = agent["name"]
            row = {"agent": name, "port": agent["port"], "cap_mb": agent["mem_cap_mb"]}
            rows.append(row)
            if agent.get("staging_exempt"):
                row.update(verdict="EXEMPT", detail=agent["staging_exempt"])
                continue
            proc = fleet.spawn_agent(manifest, agent, python)
            procs[name] = proc
            caps[name] = agent["mem_cap_mb"]
            print(f"spawned {name} pid={proc.pid} port={agent['port']} cap={agent['mem_cap_mb']}MB", flush=True)
            oom_flag = RUN_DIR / f"oom_{name}.flag"
            code, waited = wait_health(agent, proc, args.boot_timeout)
            row["health"] = code
            row["boot_s"] = round(waited, 1)
            if oom_flag.exists():
                row.update(verdict="OOM-KILLED", detail=oom_flag.read_text(errors="replace").strip())
            elif proc.poll() is not None:
                row.update(verdict="BOOT-FAIL", detail=f"exit={proc.returncode}; log tail: {log_tail(proc, name)}")
            elif code != 200:
                row.update(verdict="FAIL", detail=f"health {agent['health_path']} -> {code}; log tail: {log_tail(proc, name)}")
            else:
                booted[name] = row
        # Phase 2 — probes against the concurrently running fleet.
        for agent in agents:
            name = agent["name"]
            if name not in booted:
                continue
            row = booted[name]
            proc = procs[name]
            oom_flag = RUN_DIR / f"oom_{name}.flag"
            if True:
                key_var = f"{name.upper()}_API_KEY"
                dummy = common_env.get(key_var, "staging-dummy-key-not-a-real-secret-000000")
                headers = {"X-Agent-Name": name.lower(), "X-API-Key": dummy, "Authorization": f"Bearer {dummy}"}
                pcode, pms = http_get(f"http://127.0.0.1:{agent['port']}{agent['probe_path']}", headers=headers, timeout=15.0)
                row["probe"] = f"{agent['probe_path']} -> {pcode} ({pms:.0f}ms)"
                row["rss_mb"] = round(fleet.tree_rss_mb(proc.pid), 0) if proc.poll() is None else None
                if oom_flag.exists():
                    row.update(verdict="OOM-KILLED", detail=oom_flag.read_text(errors="replace").strip())
                elif proc.poll() is not None:
                    row.update(verdict="FAIL", detail=f"process died after health (exit={proc.returncode}); answers may have come from a foreign listener")
                elif pcode is not None and pcode < 500:
                    row.update(verdict="PASS", detail="")
                else:
                    row.update(verdict="FAIL", detail=f"probe -> {pcode}")

        print()
        print(f"{'AGENT':<10} {'PORT':>5} {'CAP':>5} {'RSS':>6} {'BOOT':>6} {'HEALTH':>6}  {'PROBE':<38} VERDICT")
        print("-" * 118)
        for r in rows:
            print(
                f"{r['agent']:<10} {r['port']:>5} {r['cap_mb']:>4}M "
                f"{('%dM' % r['rss_mb']) if r.get('rss_mb') is not None else '—':>6} "
                f"{('%ss' % r['boot_s']) if 'boot_s' in r else '—':>6} "
                f"{r.get('health') if r.get('health') is not None else '—':>6}  "
                f"{r.get('probe', ''):<38} {r['verdict']}"
                + (f"  [{r['detail']}]" if r.get("detail") else ""),
                flush=True,
            )
        print("-" * 118)
        passed = sum(1 for r in rows if r["verdict"] == "PASS")
        exempt = sum(1 for r in rows if r["verdict"] == "EXEMPT")
        failed = len(rows) - passed - exempt
        print(f"SMOKE GATE: {passed} PASS, {failed} FAIL, {exempt} EXEMPT of {len(rows)} agents", flush=True)

        fleet._append_retry(RUN_DIR / "smoke_report.json", json.dumps(
            {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "rows": rows}, indent=1))

        if args.keep:
            print("Supervising (Ctrl-C to stop the fleet)…", flush=True)
            try:
                while any(p.poll() is None for p in procs.values()):
                    time.sleep(5)
            except KeyboardInterrupt:
                pass
        return 0 if failed == 0 else 1
    finally:
        stop_watch.set()
        for name, proc in procs.items():
            if proc.poll() is None:
                fleet.kill_tree(proc.pid, signal.SIGTERM)
        deadline = time.time() + 8
        while time.time() < deadline and any(p.poll() is None for p in procs.values()):
            time.sleep(0.5)
        for name, proc in procs.items():
            if proc.poll() is None:
                fleet.kill_tree(proc.pid, signal.SIGKILL)
        time.sleep(1)
        leftovers = [f"{a['name']}:{a['port']}" for a in agents
                     if not a.get("staging_exempt") and port_in_use(a["port"])]
        if leftovers:
            print(f"WARNING: teardown incomplete — port(s) still bound: {', '.join(leftovers)}")


if __name__ == "__main__":
    raise SystemExit(main())
