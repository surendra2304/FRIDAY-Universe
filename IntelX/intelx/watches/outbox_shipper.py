"""TASK-INT-040: S2 -> S1 envelope shipper for the IntelX watch outbox.

The defect (TASK-INT-036 finding, reproduced first-hand by TASK-INT-038,
docs/collaboration/TASK-INT-038-FAST-LANE-PROOF-RUN-2.md): IntelX runs on
Server 2 and appends fired alert envelopes to its local outbox
(``data/watches/outbox.jsonl``, instant-class also to the sibling
``instant_outbox.jsonl``), but FRIDAY's drainer on Server 1
(``FRIDAY/src/friday/proactive/intelx_watch.py``) tails S1-local sibling
paths only. No component moved bytes between the servers, so the RBI
"Stop Switch" digest envelope fired on S2 at 2026-11-23 22:03 IST never
reached S1 — it is absent from the S1 outbox and from the drainer's
``delivered_keys``. It vanished silently: nothing recorded the loss.

This module is the minimal repair, repo-side only:

* Tail the S2 outbox files by byte offset (same model as the drainer:
  complete newline-terminated lines only; a trailing partial line waits
  for the next run; a file that shrank below the offset restarts at 0).
* Ship only NEW lines and APPEND them to the S1 outbox. Never a
  whole-file copy: S1's outbox and S2's outbox hold disjoint line sets
  (the two servers polled independently with separate seen-stores —
  S1 has 4 lines, S2 has 2, none shared), so overwriting S1's file
  would destroy its delivered record. Append-only on both ends keeps
  the drainer's byte offsets and ``delivered_keys`` dedupe valid.
* Record every hop. Each shipped / skipped / failed envelope gets one
  JSON line in the shipper log, and each run writes a summary with the
  source/destination line counts. A lost envelope is therefore
  detectable: ``audit()`` compares source envelope_ids against
  destination envelope_ids and reports MISSING explicitly instead of
  staying silent.

Transports
----------
* ``LocalAppendTransport`` — appends lines to a destination path. Used
  by the unit tests and the staged (local) proof. It is also the
  transport when source and destination are on one filesystem.
* ``SshAppendTransport`` — pipes lines over the existing S2 -> S1 SSH
  path (``ssh <host> "cat >> <dest>"``). This is the live mechanism:
  no new endpoint, no change to the S1 drainer, no new credential
  beyond the inter-server SSH key deploys already use. It runs nothing
  on S1 except ``cat >>`` against the outbox path.

The module is standard-library only and imports nothing from IntelX,
so it can run as a standalone timer job on S2. Envelope shape is the
``intelx.watch_alert/1`` schema from ``intelx.watches.engine``
(``build_envelope``): ``schema``, ``envelope_id`` (sha256 of
``watch.id:fingerprint``), ``dedupe_key``, ``watch_id``, ``alert_class``
(``digest`` | ``instant``), ``title``, ``url``, ``fired_at``, ``score``.

Live end-to-end verification (a real envelope produced on S2 observed
arriving in S1's outbox and delivered by the drainer) is OWED after the
owner's server-move freeze lifts; this task proves the shipper only
with unit tests and a staged local simulation. See
docs/collaboration/TASK-INT-040-ENVELOPE-SHIPPER.md.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

ENVELOPE_SCHEMA = "intelx.watch_alert/1"

#: Default outbox filenames, mirroring ``intelx.watches.engine``.
OUTBOX_NAME = "outbox.jsonl"
INSTANT_OUTBOX_NAME = "instant_outbox.jsonl"

#: Env names, mirroring the producer (engine) and consumer (drainer).
ENV_OUTBOX_PATH = "INTELX_WATCH_OUTBOX_PATH"
ENV_INSTANT_OUTBOX_PATH = "INTELX_WATCH_INSTANT_OUTBOX_PATH"
ENV_SHIPPER_STATE_PATH = "INTELX_OUTBOX_SHIPPER_STATE_PATH"
ENV_SHIPPER_LOG_PATH = "INTELX_OUTBOX_SHIPPER_LOG_PATH"
ENV_SHIPPER_DEST_HOST = "INTELX_OUTBOX_SHIPPER_DEST_HOST"
ENV_SHIPPER_DEST_DIR = "INTELX_OUTBOX_SHIPPER_DEST_DIR"

#: Required envelope fields. ``envelope_id`` is the shipper's identity
#: for an envelope; ``dedupe_key`` is the drainer's.
REQUIRED_FIELDS = ("schema", "envelope_id", "dedupe_key", "watch_id", "alert_class")


class ShipperError(Exception):
    """A shipper run failed in a way the caller must see (never silent)."""


def validate_envelope(envelope: dict[str, Any]) -> tuple[bool, str]:
    """Validate one parsed outbox line. Returns (ok, reason)."""
    for key in REQUIRED_FIELDS:
        if not envelope.get(key):
            return False, f"missing required field: {key}"
    if envelope.get("schema") != ENVELOPE_SCHEMA:
        return False, f"unsupported schema: {envelope.get('schema')!r}"
    if envelope.get("alert_class") not in ("digest", "instant"):
        return False, f"unknown alert_class: {envelope.get('alert_class')!r}"
    return True, ""


def envelope_id_of(envelope: dict[str, Any]) -> str:
    return str(envelope.get("envelope_id") or "")


def read_complete_lines(path: Path, offset: int) -> tuple[list[bytes], int]:
    """Complete newline-terminated lines past ``offset`` in ``path``.

    Returns (lines, new_offset). A trailing partial line is NOT
    returned and the offset does not advance past it — the writer may
    still be mid-append. A file that shrank below the offset was
    replaced: restart from 0 and let the caller's shipped-set dedupe
    do its job (same rule as the S1 drainer).
    """
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return [], offset
    if size < offset:
        offset = 0
    if size == offset:
        return [], offset
    with path.open("rb") as fh:
        fh.seek(offset)
        chunk = fh.read()
    last_nl = chunk.rfind(b"\n")
    if last_nl < 0:
        return [], offset
    complete = chunk[: last_nl + 1]
    return complete.split(b"\n")[:-1], offset + len(complete)


def read_envelope_ids(path: Path) -> set[str]:
    """Envelope ids of every complete, parseable line in ``path``."""
    ids: set[str] = set()
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return ids
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            env = json.loads(line.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(env, dict) and env.get("envelope_id"):
            ids.add(str(env["envelope_id"]))
    return ids


class Transport(Protocol):
    """Appends raw outbox lines to the destination outbox."""

    def append_lines(self, dest_name: str, lines: list[bytes]) -> None:
        """Append ``lines`` (without trailing newlines) to ``dest_name``."""
        ...


@dataclass
class LocalAppendTransport:
    """Append lines to a destination directory on this filesystem.

    Used by tests and the staged proof. ``dest_dir`` is the directory
    holding the destination outbox files.
    """

    dest_dir: Path

    def append_lines(self, dest_name: str, lines: list[bytes]) -> None:
        dest = self.dest_dir / dest_name
        dest.parent.mkdir(parents=True, exist_ok=True)
        with dest.open("ab") as fh:
            for line in lines:
                fh.write(line + b"\n")


@dataclass
class SshAppendTransport:
    """Append lines to the destination outbox over SSH.

    Runs ``ssh <host> "cat >> <dest>"`` and pipes the lines on stdin —
    the only command executed on the destination host. Any non-zero
    exit, timeout, or ssh error raises :class:`ShipperError` with the
    stderr attached, so a failed ship is recorded, never silent.
    ``key_path`` / ``user`` are optional; when omitted the ambient
    ssh config (the same key deploys already use) applies.
    """

    host: str
    dest_dir: str
    key_path: str | None = None
    user: str | None = None
    timeout_sec: float = 60.0

    def _ssh_cmd(self, dest_name: str) -> list[str]:
        target = f"{self.user}@{self.host}" if self.user else self.host
        cmd = ["ssh"]
        if self.key_path:
            cmd += ["-i", self.key_path]
        cmd += [target, f"cat >> {self.dest_dir.rstrip('/')}/{dest_name}"]
        return cmd

    def append_lines(self, dest_name: str, lines: list[bytes]) -> None:
        payload = b"\n".join(lines) + b"\n"
        try:
            proc = subprocess.run(
                self._ssh_cmd(dest_name),
                input=payload,
                capture_output=True,
                timeout=self.timeout_sec,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ShipperError(f"ssh append to {self.host}:{dest_name} failed: {exc}") from exc
        if proc.returncode != 0:
            raise ShipperError(
                f"ssh append to {self.host}:{dest_name} exited {proc.returncode}: "
                f"{proc.stderr.decode('utf-8', 'replace').strip()}"
            )


@dataclass
class LaneResult:
    """Per-file outcome of one shipper run."""

    name: str
    shipped: int = 0
    skipped_duplicate: int = 0
    malformed: int = 0
    failed: int = 0
    source_lines: int = 0
    dest_lines_before: int = 0


@dataclass
class ShipResult:
    """Outcome of one :meth:`OutboxShipper.run` call."""

    lanes: list[LaneResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def shipped(self) -> int:
        return sum(lane.shipped for lane in self.lanes)

    @property
    def ok(self) -> bool:
        return not self.errors


def _default_outbox_dir() -> Path:
    override = (os.environ.get(ENV_OUTBOX_PATH) or "").strip()
    if override:
        return Path(override).parent
    return Path("./data/watches")


def default_state_path() -> Path:
    override = (os.environ.get(ENV_SHIPPER_STATE_PATH) or "").strip()
    if override:
        return Path(override)
    return _default_outbox_dir() / "shipper_state.json"


def default_log_path() -> Path:
    override = (os.environ.get(ENV_SHIPPER_LOG_PATH) or "").strip()
    if override:
        return Path(override)
    return _default_outbox_dir() / "shipper.log.jsonl"


class OutboxShipper:
    """Tails the S2 watch outboxes and appends new envelopes to S1.

    State (``state_path``, JSON): per-lane byte offsets plus the set of
    shipped ``envelope_id`` values, so a restart never reships and a
    replaced source file is re-audited instead of silently skipped.
    Log (``log_path``, JSONL): one record per envelope hop plus one
    per-run summary — the audit trail that makes a lost envelope
    detectable.
    """

    def __init__(
        self,
        source_dir: Path | None = None,
        transport: Transport | None = None,
        state_path: Path | None = None,
        log_path: Path | None = None,
    ) -> None:
        self.source_dir = source_dir or _default_outbox_dir()
        if transport is None:
            raise ShipperError(
                "no transport: pass LocalAppendTransport (staged/test) or "
                "SshAppendTransport (live S2 -> S1)"
            )
        self.transport = transport
        self.state_path = state_path or default_state_path()
        self.log_path = log_path or default_log_path()
        self.state: dict[str, Any] = self._load_state()

    # -- state / log ------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError, OSError):
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("offsets", {})
        data.setdefault("shipped_ids", [])
        return data

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.state, indent=1), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def _log(self, record: dict[str, Any]) -> None:
        record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **record}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # -- shipping ---------------------------------------------------------

    def _ship_lane(self, name: str) -> LaneResult:
        result = LaneResult(name=name)
        source = self.source_dir / name
        shipped_ids: set[str] = set(self.state.get("shipped_ids") or [])
        offset = int((self.state.get("offsets") or {}).get(name, 0) or 0)
        lines, new_offset = read_complete_lines(source, offset)
        result.source_lines = len(lines)

        to_ship: list[bytes] = []
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            try:
                envelope = json.loads(line.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                result.malformed += 1
                self._log({"event": "malformed", "lane": name,
                           "line": line[:200].decode("utf-8", "replace")})
                continue
            if not isinstance(envelope, dict):
                result.malformed += 1
                continue
            ok, reason = validate_envelope(envelope)
            if not ok:
                result.malformed += 1
                self._log({"event": "malformed", "lane": name, "reason": reason,
                           "envelope_id": envelope.get("envelope_id")})
                continue
            env_id = envelope_id_of(envelope)
            if env_id in shipped_ids:
                result.skipped_duplicate += 1
                self._log({"event": "skipped_duplicate", "lane": name, "envelope_id": env_id,
                           "dedupe_key": envelope.get("dedupe_key")})
                continue
            to_ship.append(line)
            shipped_ids.add(env_id)

        if to_ship:
            try:
                self.transport.append_lines(name, to_ship)
            except ShipperError as exc:
                result.failed = len(to_ship)
                self.state["offsets"][name] = offset  # retry from here
                for raw in to_ship:
                    try:
                        env = json.loads(raw.decode("utf-8"))
                        env_id = str(env.get("envelope_id"))
                    except ValueError:
                        env_id = ""
                    shipped_ids.discard(env_id)
                    self._log({"event": "ship_failed", "lane": name, "envelope_id": env_id,
                               "error": str(exc)})
                self.state["shipped_ids"] = sorted(shipped_ids)
                self._save_state()
                raise
            for raw in to_ship:
                env = json.loads(raw.decode("utf-8"))
                result.shipped += 1
                self._log({"event": "shipped", "lane": name, "envelope_id": env.get("envelope_id"),
                           "dedupe_key": env.get("dedupe_key"),
                           "alert_class": env.get("alert_class"),
                           "watch_id": env.get("watch_id"), "fired_at": env.get("fired_at")})

        self.state["offsets"][name] = new_offset
        self.state["shipped_ids"] = sorted(shipped_ids)
        self._save_state()
        return result

    def run(self) -> ShipResult:
        """Ship new envelopes from both lanes. Never raises for a lane
        failure: the failure is recorded in the result, the log, and
        the returned errors — a failed run must be visible."""
        result = ShipResult()
        for name in (OUTBOX_NAME, INSTANT_OUTBOX_NAME):
            try:
                result.lanes.append(self._ship_lane(name))
            except ShipperError as exc:
                result.errors.append(f"{name}: {exc}")
        self._log({"event": "run_summary", "ok": result.ok, "shipped": result.shipped,
                   "errors": result.errors,
                   "lanes": [{l.name: {"shipped": l.shipped,
                                       "skipped_duplicate": l.skipped_duplicate,
                                       "malformed": l.malformed, "failed": l.failed}}
                             for l in result.lanes]})
        return result

    def audit(self, dest_dir: Path) -> dict[str, Any]:
        """Compare source envelope_ids against destination envelope_ids.

        Returns ``{"missing": [...], "per_lane": {...}}``. ``missing``
        lists envelope_ids present in the source outbox but absent from
        the destination — the exact condition that hid the 2026-11-23
        RBI envelope. An empty ``missing`` list is the healthy state.
        """
        missing: list[dict[str, str]] = []
        per_lane: dict[str, dict[str, int]] = {}
        for name in (OUTBOX_NAME, INSTANT_OUTBOX_NAME):
            src_ids = read_envelope_ids(self.source_dir / name)
            dst_ids = read_envelope_ids(dest_dir / name)
            lane_missing = sorted(src_ids - dst_ids)
            per_lane[name] = {"source": len(src_ids), "destination": len(dst_ids),
                              "missing": len(lane_missing)}
            for env_id in lane_missing:
                missing.append({"lane": name, "envelope_id": env_id})
        report = {"missing": missing, "per_lane": per_lane}
        self._log({"event": "audit", **report})
        return report


def build_live_transport() -> SshAppendTransport:
    """Build the live S2 -> S1 transport from the environment.

    Requires INTELX_OUTBOX_SHIPPER_DEST_HOST (S1 hostname/IP) and
    INTELX_OUTBOX_SHIPPER_DEST_DIR (S1 IntelX data/watches dir).
    """
    host = (os.environ.get(ENV_SHIPPER_DEST_HOST) or "").strip()
    dest_dir = (os.environ.get(ENV_SHIPPER_DEST_DIR) or "").strip()
    if not host or not dest_dir:
        raise ShipperError(
            f"live transport needs {ENV_SHIPPER_DEST_HOST} and {ENV_SHIPPER_DEST_DIR}"
        )
    return SshAppendTransport(host=host, dest_dir=dest_dir)


def main(argv: list[str] | None = None) -> int:
    """CLI: ``ship`` (default) or ``audit <dest_dir>``.

    ``ship`` with no dest env configured uses LocalAppendTransport
    only when INTELX_OUTBOX_SHIPPER_DEST_DIR names a local directory
    (staged mode); otherwise it builds the live SSH transport.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    command = args[0] if args else "ship"
    if command == "audit":
        if len(args) < 2:
            print("usage: outbox_shipper.py audit <dest_dir>", file=sys.stderr)
            return 2
        shipper = OutboxShipper(transport=LocalAppendTransport(Path(args[1])))
        report = shipper.audit(Path(args[1]))
        print(json.dumps(report, indent=1))
        return 0 if not report["missing"] else 1
    if command != "ship":
        print(f"unknown command: {command}", file=sys.stderr)
        return 2
    dest_dir = (os.environ.get(ENV_SHIPPER_DEST_DIR) or "").strip()
    host = (os.environ.get(ENV_SHIPPER_DEST_HOST) or "").strip()
    if host:
        transport: Transport = build_live_transport()
    elif dest_dir:
        transport = LocalAppendTransport(Path(dest_dir))
    else:
        print(f"set {ENV_SHIPPER_DEST_HOST} (live) or {ENV_SHIPPER_DEST_DIR} (staged)",
              file=sys.stderr)
        return 2
    shipper = OutboxShipper(transport=transport)
    result = shipper.run()
    print(json.dumps({"ok": result.ok, "shipped": result.shipped,
                      "errors": result.errors}, indent=1))
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
