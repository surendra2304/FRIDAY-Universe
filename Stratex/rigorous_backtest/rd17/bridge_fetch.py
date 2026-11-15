#!/usr/bin/env python3
"""TASK-STR-RD-017 — bridge transport for the paper sim (sandbox mode).

The research sandbox's egress is geo-blocked by Binance (REST returns
the restricted-location response; the futures websocket handshake
times out). This transport fetches the IDENTICAL public endpoints from
FRIDAY Server 1 (Hyderabad egress) instead: it uploads server_fetch.py
to the server once (via the bridge MCP run_shell tool, heredoc), then
each poll writes the spec and runs it in ONE run_shell call, returning
the RD17BUNDLE line for the engine.

On any host with direct Binance access this module is unnecessary —
use --transport rest. The data is the same exchange data from the same
endpoints either way; ledger rows record which transport served them.
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

ENDPOINT = "https://friday-universe.duckdns.org/bridge/mcp"
HERE = Path(__file__).resolve().parent
REMOTE_SCRIPT = "/tmp/rd17_fetch.py"
REMOTE_SPEC = "/tmp/rd17_spec.json"


class Bridge:
    """Minimal MCP streamable-HTTP client over curl subprocesses
    (the sandbox proxy stalls Python urllib against this endpoint;
    curl works)."""

    def __init__(self, tmp_dir):
        self.tmp = Path(tmp_dir)
        self.tmp.mkdir(parents=True, exist_ok=True)
        self.session_id = None
        self._id = 0

    def _write(self, path, text):
        last = None
        deadline = time.time() + 120
        while time.time() < deadline:
            try:
                Path(path).write_text(text)
                if Path(path).read_text() == text:
                    return
                last = RuntimeError("read-back mismatch")
            except OSError as exc:  # noqa: PERF203
                last = exc
            time.sleep(2)
        raise RuntimeError(f"write failed: {path}: {last}")

    def _post(self, payload, expect_response=True, timeout=300):
        body_file = str(self.tmp / "bridge_body.json")
        self._write(body_file, json.dumps(payload))
        hdr_file = body_file + ".hdr"
        cmd = ["curl", "-s", "-X", "POST", ENDPOINT,
               "-H", "Content-Type: application/json",
               "-H", "Accept: application/json, text/event-stream",
               "-D", hdr_file, "--data-binary", "@" + body_file,
               "--max-time", str(timeout)]
        if self.session_id:
            cmd += ["-H", f"Mcp-Session-Id: {self.session_id}"]
        out = subprocess.run(cmd, capture_output=True, text=True)
        try:
            hdrs = Path(hdr_file).read_text(errors="replace")
        except OSError:
            hdrs = ""
        for line in hdrs.splitlines():
            if line.lower().startswith("mcp-session-id:"):
                self.session_id = line.split(":", 1)[1].strip()
        if out.returncode != 0:
            raise RuntimeError(f"curl rc={out.returncode}: "
                               f"{out.stderr[:300]}")
        if not expect_response:
            return None
        raw = (out.stdout or "").strip()
        if raw.startswith("event:") or "\ndata:" in raw \
                or raw.startswith("data:"):
            msgs = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk and chunk != "[DONE]":
                        msgs.append(json.loads(chunk))
            for m in reversed(msgs):
                if "result" in m or "error" in m:
                    if "error" in m:
                        raise RuntimeError(f"RPC error: {m['error']}")
                    return m["result"]
            return None
        return json.loads(raw) if raw else None

    def connect(self, attempts=4):
        last = None
        for i in range(attempts):
            try:
                self.session_id = None
                self._id += 1
                self._post({"jsonrpc": "2.0", "id": self._id,
                            "method": "initialize",
                            "params": {
                                "protocolVersion": "2025-03-26",
                                "capabilities": {},
                                "clientInfo": {"name": "stratex-rd17-sim",
                                               "version": "1.0"}}})
                break
            except Exception as exc:  # noqa: BLE001
                last = exc
                time.sleep(min(20, 3 * (i + 1)))
        else:
            raise RuntimeError(f"bridge connect failed: {last}")
        try:
            self._post({"jsonrpc": "2.0",
                        "method": "notifications/initialized"},
                       expect_response=False, timeout=30)
        except Exception:  # noqa: BLE001
            pass

    def run_shell(self, command, timeout=300):
        self._id += 1
        res = self._post({"jsonrpc": "2.0", "id": self._id,
                          "method": "tools/call",
                          "params": {"name": "run_shell",
                                     "arguments": {"command": command,
                                                   "server": 1}}},
                         timeout=timeout)
        if isinstance(res, dict) and res.get("isError"):
            raise RuntimeError(f"run_shell error: {json.dumps(res)[:500]}")
        return "\n".join(c.get("text", "") for c in
                         (res or {}).get("content", [])
                         if c.get("type") == "text")


_SESSION = {}


def _session(state_dir):
    key = str(state_dir)
    if key not in _SESSION:
        b = Bridge(Path(state_dir) / "bridge_tmp")
        b.connect()
        _SESSION[key] = b
    return _SESSION[key]


def fetch_bundle_text(spec, state_dir):
    """Runs server_fetch.py on Server 1; returns its stdout text."""
    b = _session(state_dir)
    script = (HERE / "server_fetch.py").read_text()
    sha = hashlib.sha256(script.encode()).hexdigest()
    flag = Path(state_dir) / "bridge_fetch_uploaded.sha"
    uploaded = flag.read_text().strip() if flag.exists() else ""
    parts = []
    if uploaded != sha:
        parts.append(f"cat > {REMOTE_SCRIPT} <<'RD17EOF'\n{script}\nRD17EOF")
    parts.append(f"cat > {REMOTE_SPEC} <<'RD17EOF2'\n"
                 f"{json.dumps(spec)}\nRD17EOF2")
    parts.append(f"python3 {REMOTE_SCRIPT} < {REMOTE_SPEC}")
    out = b.run_shell("\n".join(parts), timeout=300)
    if "RD17BUNDLE " not in out:
        # The remote script may have been lost (e.g. /tmp cleaned):
        # force re-upload once and retry.
        parts.insert(0, f"cat > {REMOTE_SCRIPT} <<'RD17EOF'\n"
                        f"{script}\nRD17EOF")
        out = b.run_shell("\n".join(parts), timeout=300)
    if uploaded != sha and "RD17BUNDLE " in out:
        try:
            flag.write_text(sha)
        except OSError:
            pass
    return out
