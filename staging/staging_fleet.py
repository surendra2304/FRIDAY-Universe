#!/usr/bin/env python3
"""FRIDAY Universe — local staging fleet manager (TASK-REL-046).

Starts/stops the 10-agent fleet locally from this repo checkout, mirroring
the production boot recipes (deploy/setup_fleet.sh) with three staging
differences:

  1. Agents bind to 127.0.0.1 on their production ports.
  2. Credentials are the dummy values from fleet_manifest.yaml — production
     secrets are NEVER read or copied into staging.
  3. Each agent runs under a memory cap equal to its production
     memory_limit in AGENTS.yaml. A watchdog polls every agent's process
     tree RSS every 2 seconds; a tree over its cap on two consecutive polls
     is killed and recorded in run/events.log as OOM-KILLED. This is a
     watchdog approximation of systemd's MemoryMax (which production uses):
     it cannot catch sub-2-second spikes, and it measures RSS rather than
     cgroup charge — documented limits, not hidden ones.

Usage:
  staging_fleet.py start [--only NAME] [--python PATH]
  staging_fleet.py stop
  staging_fleet.py status
  staging_fleet.py watchdog        (internal; spawned by start)

State lives in staging/run/ (gitignored): pidfiles, per-agent logs,
events.log, fleet_state.json.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

STAGING_DIR = Path(__file__).resolve().parent
REPO_ROOT = STAGING_DIR.parent
RUN_DIR = STAGING_DIR / "run"
STATE_FILE = RUN_DIR / "fleet_state.json"
EVENTS_LOG = RUN_DIR / "events.log"


# --------------------------------------------------------------------------
# Manifest loading (PyYAML if available, else a small fallback parser for
# the restricted two-level schema used by fleet_manifest.yaml).
# --------------------------------------------------------------------------
def load_manifest() -> dict:
    text = (STAGING_DIR / "fleet_manifest.yaml").read_text()
    try:
        import yaml  # type: ignore

        return yaml.safe_load(text)
    except ImportError:
        return _fallback_parse(text)


def _fallback_parse(text: str) -> dict:
    """Parse the restricted YAML subset used in fleet_manifest.yaml.

    Supports: top-level maps, one level of nested maps, lists of maps with
    scalar values, flow lists ["a", "b"], quoted scalars, ints, booleans.
    It is deliberately small — if the manifest grows beyond this subset,
    install PyYAML (it is in requirements-staging.txt).
    """
    import ast
    import re

    root: dict = {}
    section = None          # current top-level key
    current_agent = None    # current dict inside agents list
    in_env = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip() if not raw.lstrip().startswith("#") else ""
        if not line.strip():
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = line.strip()
        if indent == 0:
            key, _, _ = stripped.partition(":")
            section = key.strip()
            if section == "agents":
                root["agents"] = []
            else:
                root[section] = {}
            current_agent = None
            in_env = False
            continue
        if section == "common_env":
            k, _, v = stripped.partition(":")
            root["common_env"][k.strip()] = _scalar(v.strip())
            continue
        if section == "agents":
            if stripped.startswith("- "):
                current_agent = {}
                root["agents"].append(current_agent)
                in_env = False
                stripped = stripped[2:]
                if not stripped:
                    continue
            if current_agent is None:
                continue
            if stripped == "env:":
                current_agent["env"] = {}
                in_env = True
                continue
            k, _, v = stripped.partition(":")
            if in_env and indent >= 6:
                current_agent["env"][k.strip()] = _scalar(v.strip())
            else:
                in_env = False
                current_agent[k.strip()] = _scalar(v.strip())
    return root


def _scalar(v: str):
    import ast

    v = v.strip()
    if v.startswith("["):
        return [str(x) for x in ast.literal_eval(v)]
    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
        return v[1:-1]
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        return int(v)
    except ValueError:
        return v


# --------------------------------------------------------------------------
# Process-tree RSS via /proc (Linux; the staging sandbox and the Oracle
# VMs are both Linux).
# --------------------------------------------------------------------------
def tree_rss_mb(root_pid: int) -> float:
    ppid: dict[int, int] = {}
    rss: dict[int, int] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        try:
            with open(f"/proc/{pid}/stat", "rb") as fh:
                parts = fh.read().rsplit(b")", 1)[1].split()
            ppid[pid] = int(parts[1])
            with open(f"/proc/{pid}/status") as fh:
                for line in fh:
                    if line.startswith("VmRSS:"):
                        rss[pid] = int(line.split()[1])  # kB
                        break
        except (FileNotFoundError, PermissionError, IndexError, ValueError):
            continue
    total_kb = 0
    stack = [root_pid]
    seen = set()
    children: dict[int, list[int]] = {}
    for pid, parent in ppid.items():
        children.setdefault(parent, []).append(pid)
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        total_kb += rss.get(pid, 0)
        stack.extend(children.get(pid, []))
    return total_kb / 1024.0


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"agents": {}, "watchdog_pid": None}


def _append_retry(path: Path, data: str) -> None:
    """Append with retries: the sandbox overlay FS intermittently returns
    EPERM on writes under load. State files are reconstructible, so after
    3 attempts we warn instead of crashing the fleet operation."""
    for attempt in range(3):
        try:
            with open(path, "a") as fh:
                fh.write(data)
            return
        except PermissionError:
            if attempt == 2:
                print(f"WARNING: could not write {path} (FS EPERM)", file=sys.stderr)
            time.sleep(0.3)


def save_state(state: dict) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state, indent=1)
    tmp = STATE_FILE.with_suffix(".tmp")
    delay = 0.3
    for _ in range(8):
        try:
            tmp.write_text(data)
            tmp.replace(STATE_FILE)
            return
        except PermissionError:
            try:
                STATE_FILE.write_text(data)
                return
            except PermissionError:
                pass
            time.sleep(delay)
            delay = min(delay * 1.6, 2.0)
    print(f"WARNING: could not write {STATE_FILE} (FS EPERM)", file=sys.stderr)


def log_event(msg: str) -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    _append_retry(EVENTS_LOG, f"{ts} {msg}\n")


def resolve_python(cli_python: str | None) -> str:
    if cli_python:
        return cli_python
    env_python = os.environ.get("STAGING_PYTHON")
    if env_python:
        return env_python
    local_venv = STAGING_DIR / ".venv" / "bin" / "python"
    if local_venv.exists():
        return str(local_venv)
    return sys.executable


# --------------------------------------------------------------------------
# In-process supervision (used by smoke_gate.py): the gate owns the agent
# processes as direct children for its whole lifetime — no detached
# processes, no dependence on the state file for correctness.
# --------------------------------------------------------------------------
def spawn_agent(manifest: dict, agent: dict, python: str, detached: bool = False) -> subprocess.Popen:
    """Spawn one agent with output captured through a PIPE.

    A drainer thread copies the output to run/logs/<name>.log (best effort)
    and keeps the last 50 lines in memory on proc._staging_tail. Rationale:
    on the loaded Muse sandbox the overlay FS intermittently drops file
    writes (EPERM / silent 0-byte files), which hid a child's startup
    traceback entirely when output went straight to a file. The in-memory
    tail is the gate's reliable evidence; the log file is the durable copy.
    """
    import collections
    import threading

    (RUN_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "tmp").mkdir(parents=True, exist_ok=True)
    log_path = RUN_DIR / "logs" / f"{agent['name']}.log"
    proc = subprocess.Popen(
        [python, *[str(a) for a in agent["argv"]]],
        cwd=str(REPO_ROOT / agent["dir"]),
        env=agent_env(manifest, agent),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=detached,
    )
    tail: collections.deque = collections.deque(maxlen=50)
    proc._staging_tail = tail

    def drain():
        try:
            log = open(log_path, "ab")
        except OSError:
            log = None
        try:
            for line in proc.stdout:  # type: ignore[union-attr]
                tail.append(line.rstrip())
                if log is not None:
                    try:
                        log.write(line.encode())
                        log.flush()
                    except OSError:
                        pass
        except Exception:
            pass
        finally:
            if log is not None:
                try:
                    log.close()
                except OSError:
                    pass  # sandbox FS EPERM on close; the in-memory tail is the evidence

    threading.Thread(target=drain, daemon=True).start()
    return proc


def kill_tree(pid: int, sig: int) -> None:
    """Signal a process and all its descendants (bottom-up order)."""
    children: dict[int, list[int]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat", "rb") as fh:
                parts = fh.read().rsplit(b")", 1)[1].split()
            children.setdefault(int(parts[1]), []).append(int(entry))
        except (FileNotFoundError, PermissionError, IndexError, ValueError):
            continue
    order = []
    stack = [pid]
    while stack:
        cur = stack.pop()
        order.append(cur)
        stack.extend(children.get(cur, []))
    for target in reversed(order):
        try:
            os.kill(target, sig)
        except (ProcessLookupError, PermissionError):
            pass


def enforce_caps_once(procs: dict, caps: dict, over: dict) -> list[str]:
    """One watchdog pass over {name: Popen}; kills trees over cap twice in
    a row (caller polls every 2s). Returns names killed this pass."""
    killed = []
    for name, proc in list(procs.items()):  # snapshot: the owner thread may add entries mid-pass
        if proc.poll() is not None:
            over.pop(name, None)
            continue
        rss = tree_rss_mb(proc.pid)
        if rss > caps[name]:
            over[name] = over.get(name, 0) + 1
            if over[name] >= 2:
                log_event(f"OOM-KILLED {name} pid={proc.pid} rss={rss:.0f}MB cap={caps[name]}MB")
                _append_retry(RUN_DIR / f"oom_{name}.flag", f"rss={rss:.0f}MB cap={caps[name]}MB\n")
                kill_tree(proc.pid, signal.SIGTERM)
                killed.append(name)
                over.pop(name, None)
        else:
            over.pop(name, None)
    return killed


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def agent_env(manifest: dict, agent: dict) -> dict:
    env = dict(os.environ)
    env.update({k: str(v) for k, v in manifest.get("common_env", {}).items()})
    env.update({k: str(v) for k, v in agent.get("env", {}).items()})
    env["PORT"] = str(agent["port"])
    pp = env.get("PYTHONPATH", "")
    # Mirror deploy/setup_fleet.sh exactly: PYTHONPATH=<agent path(s)>:$REPO_DIR
    # (the repo root carries the shared `mesh` package several agents import).
    # The manifest pythonpath field may hold several colon-separated entries.
    parts = [str(REPO_ROOT / p) for p in agent["pythonpath"].split(":") if p]
    parts.append(str(REPO_ROOT))
    if pp:
        parts.append(pp)
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env.setdefault("TMPDIR", str(RUN_DIR / "tmp"))
    return env


def cmd_start(args) -> int:
    manifest = load_manifest()
    state = load_state()
    python = resolve_python(args.python)
    (RUN_DIR / "logs").mkdir(parents=True, exist_ok=True)
    (RUN_DIR / "tmp").mkdir(parents=True, exist_ok=True)
    started = []
    for agent in manifest["agents"]:
        name = agent["name"]
        if args.only and name.lower() != args.only.lower():
            continue
        if agent.get("staging_exempt"):
            print(f"SKIP {name}: staging-exempt — {agent['staging_exempt']}")
            continue
        existing = state["agents"].get(name)
        if existing and pid_alive(existing["pid"]):
            print(f"ALREADY RUNNING {name} pid={existing['pid']}")
            continue
        log_path = RUN_DIR / "logs" / f"{name}.log"
        proc = spawn_agent(manifest, agent, python, detached=True)
        state["agents"][name] = {
            "pid": proc.pid,
            "port": agent["port"],
            "mem_cap_mb": agent["mem_cap_mb"],
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }
        started.append(name)
        log_event(f"START {name} pid={proc.pid} port={agent['port']} cap={agent['mem_cap_mb']}MB")
        print(f"STARTED {name} pid={proc.pid} port={agent['port']} cap={agent['mem_cap_mb']}MB log={log_path}")
    save_state(state)
    # Watchdog (one per fleet).
    if state.get("watchdog_pid") and pid_alive(state["watchdog_pid"]):
        pass
    elif started or state["agents"]:
        wd = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "watchdog"],
            stdout=open(RUN_DIR / "logs" / "watchdog.log", "ab"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        state["watchdog_pid"] = wd.pid
        save_state(state)
        print(f"WATCHDOG pid={wd.pid}")
    return 0


def _kill_tree(pid: int, sig: int) -> None:
    try:
        os.killpg(os.getpgid(pid), sig)
    except (ProcessLookupError, PermissionError):
        try:
            os.kill(pid, sig)
        except (ProcessLookupError, PermissionError):
            pass


def cmd_stop(args) -> int:
    state = load_state()
    wd = state.get("watchdog_pid")
    if wd and pid_alive(wd):
        _kill_tree(wd, signal.SIGTERM)
    for name, info in list(state["agents"].items()):
        pid = info["pid"]
        if pid_alive(pid):
            _kill_tree(pid, signal.SIGTERM)
            print(f"STOP sent to {name} pid={pid}")
    deadline = time.time() + 10
    while time.time() < deadline:
        if not any(pid_alive(i["pid"]) for i in state["agents"].values()):
            break
        time.sleep(0.5)
    for name, info in list(state["agents"].items()):
        if pid_alive(info["pid"]):
            _kill_tree(info["pid"], signal.SIGKILL)
            print(f"KILLED (SIGKILL) {name} pid={info['pid']}")
    log_event("STOP fleet")
    save_state({"agents": {}, "watchdog_pid": None})
    return 0


def cmd_status(args) -> int:
    manifest = load_manifest()
    state = load_state()
    by_name = {a["name"]: a for a in manifest["agents"]}
    for name, agent in by_name.items():
        info = state["agents"].get(name)
        if agent.get("staging_exempt"):
            print(f"{name:<10} EXEMPT  {agent['staging_exempt']}")
        elif not info:
            print(f"{name:<10} DOWN    (not started)")
        elif pid_alive(info["pid"]):
            rss = tree_rss_mb(info["pid"])
            print(f"{name:<10} UP      pid={info['pid']} port={info['port']} rss={rss:.0f}MB cap={info['mem_cap_mb']}MB")
        else:
            print(f"{name:<10} DEAD    pid={info['pid']} (see run/logs/{name}.log, run/events.log)")
    return 0


def cmd_watchdog(args) -> int:
    over: dict[str, int] = {}
    known: dict = {}
    while True:
        # A missing/unreadable state file means "unknown", not "empty":
        # keep enforcing the last known state. Exit only on an explicitly
        # emptied state (cmd_stop) — or when killed by cmd_stop.
        if STATE_FILE.exists():
            state = load_state()
            if not state["agents"]:
                return 0
            known = state["agents"]
        state = {"agents": known}
        for name, info in list(state["agents"].items()):
            pid = info["pid"]
            if not pid_alive(pid):
                continue
            rss = tree_rss_mb(pid)
            if rss > info["mem_cap_mb"]:
                over[name] = over.get(name, 0) + 1
                if over[name] >= 2:
                    log_event(
                        f"OOM-KILLED {name} pid={pid} rss={rss:.0f}MB cap={info['mem_cap_mb']}MB"
                    )
                    _append_retry(
                        RUN_DIR / f"oom_{name}.flag",
                        f"rss={rss:.0f}MB cap={info['mem_cap_mb']}MB\n",
                    )
                    _kill_tree(pid, signal.SIGTERM)
                    over.pop(name, None)
            else:
                over.pop(name, None)
        time.sleep(2)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["start", "stop", "status", "watchdog"])
    parser.add_argument("--only", default=None)
    parser.add_argument("--python", default=None)
    args = parser.parse_args()
    return {
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
        "watchdog": cmd_watchdog,
    }[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
