#!/usr/bin/env python3
"""TASK-OBS-001 — Fleet health watcher: crash-loop detection and health alerting.

`Restart=always` keeps a crash-looping unit green in `systemctl status`, so a
service that dies every 30 seconds looks "running" all day. This watcher is the
missing sensor: it tracks each unit's **NRestarts counter** and local
`/health` endpoint, converts silent crash loops and outages into explicit
alerts, and keeps a machine-readable state file that survives its own restarts.

Designed for the production hosts (see deploy/fleet-health-watcher.{service,timer}):
    Server 1: FRIDAY:10000 Inference:8001 Memora:8002 Stratex:8003
              Futuris:8004 IntelX:8005 Forge:8006 Stratex-Daemon:-
    Server 2: Sentinel:8008 Cortex:8009 VyralX:8010 VyralX-Daemon:-

Usage:
    python scripts/fleet_health_watcher.py --once                 # one cycle (timer mode)
    python scripts/fleet_health_watcher.py --interval 300         # daemon mode
    python scripts/fleet_health_watcher.py --state /tmp/s.json --alert-command 'curl ...'

Alerting contract:
    * Every alert is written to the log and the state file (auditable).
    * `--alert-command` is invoked once per NEW alert with two env vars:
      FLEET_ALERT_TEXT and FLEET_ALERT_JSON (deduplicated by --cooldown).
    * The watcher itself NEVER fails the whole cycle because one probe failed;
      failures are data, not crashes.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_SERVICES = os.environ.get("FLEET_WATCH_SERVICES", "").strip() or None
STATE_DEFAULT = "/var/lib/friday-universe/fleet-health-state.json"
CRASH_LOOP_DELTA_DEFAULT = 3  # restarts within one window => crash loop
HEALTH_TIMEOUT_S = 10.0


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ServiceSpec:
    name: str
    port: int | None  # None = systemd-only unit (no HTTP health endpoint)


@dataclass
class ServiceSnapshot:
    """One observation of one service."""

    name: str
    active_state: str = "unknown"
    sub_state: str = "unknown"
    n_restarts: int = -1
    health_http: int | None = None
    health_detail: str = ""
    error: str = ""
    observed_at: str = field(default_factory=utcnow)

    @property
    def healthy(self) -> bool:
        systemd_ok = self.active_state == "active"
        health_ok = True if self.health_http is None else self.health_http == 200
        return systemd_ok and health_ok


def parse_services(spec: str | None) -> list[ServiceSpec]:
    """Parse 'FRIDAY:10000,Stratex-Daemon:-' (or the default fleet map)."""
    if spec:
        entries = [e.strip() for e in spec.split(",") if e.strip()]
    else:
        return [
            ServiceSpec(n, p)
            for n, p in [
                ("FRIDAY", 10000), ("Inference", 8001), ("Memora", 8002),
                ("Stratex", 8003), ("Futuris", 8004), ("IntelX", 8005),
                ("Forge", 8006), ("Stratex-Daemon", None),
            ]
        ]
    out: list[ServiceSpec] = []
    for entry in entries:
        name, _, port = entry.partition(":")
        port = port.strip()
        out.append(ServiceSpec(name.strip(), int(port) if port and port != "-" else None))
    return out


def probe_systemd(name: str) -> tuple[str, str, int, str]:
    """Return (active_state, sub_state, n_restarts, error)."""
    try:
        res = subprocess.run(
            ["systemctl", "show", name, "--property", "ActiveState,SubState,NRestarts"],
            capture_output=True, text=True, timeout=15,
        )
    except Exception as exc:  # noqa: BLE001 — a probe must never crash the cycle
        return "unknown", "unknown", -1, f"{type(exc).__name__}: {exc}"
    if res.returncode != 0:
        return "unknown", "unknown", -1, (res.stderr or "systemctl failed").strip()[:200]
    active = sub = "unknown"
    restarts = -1
    for line in res.stdout.splitlines():
        key, _, value = line.partition("=")
        if key == "ActiveState":
            active = value
        elif key == "SubState":
            sub = value
        elif key == "NRestarts":
            try:
                restarts = int(value)
            except ValueError:
                restarts = -1
    return active, sub, restarts, ""


def probe_health(port: int | None) -> tuple[int | None, str, str]:
    """Return (http_status, detail, error) for the local health endpoint."""
    if port is None:
        return None, "no http health endpoint (daemon unit)", ""
    url = f"http://127.0.0.1:{port}/health"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_S) as resp:
            body = resp.read(400).decode("utf-8", "replace")
            return resp.status, body[:200], ""
    except urllib.error.HTTPError as exc:
        return exc.code, (exc.read().decode("utf-8", "replace")[:200] if exc.fp else ""), ""
    except Exception as exc:  # noqa: BLE001
        return None, "", f"{type(exc).__name__}: {exc}"


def observe(spec: ServiceSpec) -> ServiceSnapshot:
    snap = ServiceSnapshot(name=spec.name)
    snap.active_state, snap.sub_state, snap.n_restarts, snap.error = probe_systemd(spec.name)
    snap.health_http, snap.health_detail, health_err = probe_health(spec.port)
    if health_err and not snap.error:
        snap.error = health_err
    return snap


@dataclass
class WatchState:
    """Persistent state: previous NRestarts per service + alert cooldowns."""

    previous_restarts: dict[str, int] = field(default_factory=dict)
    open_alerts: dict[str, str] = field(default_factory=dict)  # alert_key -> raised_at
    last_cycle: str = ""

    @classmethod
    def load(cls, path: str) -> "WatchState":
        p = Path(path)
        if not p.is_file():
            return cls()
        try:
            data = json.loads(p.read_text())
            return cls(
                previous_restarts=data.get("previous_restarts", {}),
                open_alerts=data.get("open_alerts", {}),
                last_cycle=data.get("last_cycle", ""),
            )
        except (json.JSONDecodeError, OSError):
            return cls()

    def save(self, path: str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps({
            "previous_restarts": self.previous_restarts,
            "open_alerts": self.open_alerts,
            "last_cycle": self.last_cycle,
        }, indent=2) + "\n")
        tmp.replace(p)


def evaluate(
    snapshot: ServiceSnapshot,
    state: WatchState,
    *,
    crash_loop_delta: int,
    first_seen: bool,
) -> list[dict]:
    """Pure alert evaluation — unit-tested in tests/test_fleet_health_watcher.py.

    Alert classes:
      CRASH_LOOP   NRestarts increased by >= crash_loop_delta within one window.
      SERVICE_DOWN unit not active (or systemctl unavailable and no data).
      HEALTH_FAIL  HTTP /health answered non-200 or did not answer.
      RECOVERED    was alerted and is now healthy (auto-closes the alert).
    """
    alerts: list[dict] = []
    prev = state.previous_restarts.get(snapshot.name)

    if not first_seen and prev is not None and prev >= 0 and snapshot.n_restarts >= 0:
        delta = snapshot.n_restarts - prev
        if delta >= crash_loop_delta:
            alerts.append({
                "alert": "CRASH_LOOP",
                "service": snapshot.name,
                "detail": f"NRestarts {prev} -> {snapshot.n_restarts} (+{delta}) in one window; unit is crash-looping under Restart=always",
                "severity": "critical",
            })
    if snapshot.active_state != "active":
        alerts.append({
            "alert": "SERVICE_DOWN",
            "service": snapshot.name,
            "detail": f"ActiveState={snapshot.active_state} SubState={snapshot.sub_state}" + (f"; error={snapshot.error}" if snapshot.error else ""),
            "severity": "critical",
        })
    if snapshot.health_http is not None and snapshot.health_http != 200:
        alerts.append({
            "alert": "HEALTH_FAIL",
            "service": snapshot.name,
            "detail": f"/health returned HTTP {snapshot.health_http}: {snapshot.health_detail[:120]}",
            "severity": "warning",
        })
    if snapshot.health_http is None and snapshot.error and snapshot.active_state == "active":
        alerts.append({
            "alert": "HEALTH_UNREACHABLE",
            "service": snapshot.name,
            "detail": f"/health unreachable while unit active: {snapshot.error[:160]}",
            "severity": "warning",
        })

    was_alerted = any(k.startswith(snapshot.name + ":") for k in state.open_alerts)
    if not alerts and was_alerted:
        alerts.append({
            "alert": "RECOVERED",
            "service": snapshot.name,
            "detail": f"service healthy again (active, /health 200); previous alert closed: {state.open_alerts.get(snapshot.name + ':last', '')}",
            "severity": "info",
        })

    if snapshot.n_restarts >= 0:
        state.previous_restarts[snapshot.name] = snapshot.n_restarts
    return alerts


def dispatch_alerts(alerts: list[dict], state: WatchState, *, cooldown_s: int, alert_command: str | None) -> None:
    """Log, persist and forward NEW alerts; honour the cooldown per alert key."""
    now_epoch = time.time()
    for alert in alerts:
        key = f"{alert['service']}:{alert['alert']}"
        last = state.open_alerts.get(key)
        # RECOVERED always fires (it closes an incident) and prunes the family.
        if alert["alert"] == "RECOVERED":
            for stale in [k for k in list(state.open_alerts) if k.startswith(alert["service"] + ":")]:
                del state.open_alerts[stale]
            state.open_alerts[alert["service"] + ":last"] = f"recovered at {utcnow()}"
            print(f"[RECOVERED] {alert['service']} — {alert['detail']}", flush=True)
            continue
        if last and now_epoch - float(last) < cooldown_s:
            print(f"[SUPPRESSED] {key} within {cooldown_s}s cooldown", flush=True)
            continue
        state.open_alerts[key] = str(now_epoch)
        state.open_alerts[alert["service"] + ":last"] = f"{alert['alert']} at {utcnow()}"
        line = f"[{alert['severity'].upper()}] {alert['alert']} {alert['service']}: {alert['detail']}"
        print(line, flush=True)
        if alert_command:
            env = dict(os.environ)
            env["FLEET_ALERT_TEXT"] = line
            env["FLEET_ALERT_JSON"] = json.dumps(alert)
            try:
                subprocess.run(alert_command, shell=True, env=env, timeout=30, check=False)
            except Exception as exc:  # noqa: BLE001 — alerting must never kill the watcher
                print(f"[ALERT-COMMAND-FAILED] {type(exc).__name__}: {exc}", flush=True)


def run_cycle(
    services: list[ServiceSpec],
    state: WatchState,
    *,
    crash_loop_delta: int,
    cooldown_s: int,
    alert_command: str | None,
    first_seen: bool,
) -> list[ServiceSnapshot]:
    snapshots: list[ServiceSnapshot] = []
    for spec in services:
        snap = observe(spec)
        snapshots.append(snap)
        alerts = evaluate(snap, state, crash_loop_delta=crash_loop_delta, first_seen=first_seen)
        dispatch_alerts(alerts, state, cooldown_s=cooldown_s, alert_command=alert_command)
    state.last_cycle = utcnow()
    return snapshots


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--services", default=DEFAULT_SERVICES,
                    help="comma list Name:Port or Name:- (default: full Server-1 fleet map)")
    ap.add_argument("--state", default=STATE_DEFAULT)
    ap.add_argument("--once", action="store_true", help="run a single cycle and exit (timer mode)")
    ap.add_argument("--interval", type=int, default=300, help="daemon mode cycle seconds")
    ap.add_argument("--crash-loop-delta", type=int, default=CRASH_LOOP_DELTA_DEFAULT)
    ap.add_argument("--cooldown", type=int, default=1800, help="seconds before re-alerting the same condition")
    ap.add_argument("--alert-command", default=os.environ.get("FLEET_ALERT_COMMAND"),
                    help="shell command invoked per NEW alert (env: FLEET_ALERT_TEXT, FLEET_ALERT_JSON)")
    args = ap.parse_args()

    services = parse_services(args.services)
    state = WatchState.load(args.state)
    first_seen = not state.previous_restarts

    def cycle() -> None:
        nonlocal first_seen
        snapshots = run_cycle(
            services, state,
            crash_loop_delta=args.crash_loop_delta,
            cooldown_s=args.cooldown,
            alert_command=args.alert_command,
            first_seen=first_seen,
        )
        down = [s.name for s in snapshots if not s.healthy]
        print(f"[CYCLE {utcnow()}] {len(snapshots) - len(down)}/{len(snapshots)} healthy"
              + (f"; unhealthy: {', '.join(down)}" if down else ""), flush=True)
        state.save(args.state)
        first_seen = False

    if args.once:
        cycle()
        return 0
    while True:
        cycle()
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
