"""Reverse-tunnel registry for the owner's Android phone.

The cloud FRIDAY has no route into a phone behind carrier NAT, and ADB —
the transport the older ``devices/android_controller.py`` speaks — needs the
phone attached to the machine running FRIDAY, which on Oracle Server 1 it
never is. The phone therefore opens an outbound WebSocket to
``/api/phone/connect/{device_id}`` and this module keeps that socket,
correlates command frames with result frames, and returns a single evidence
record per command. The frame protocol deliberately mirrors
:mod:`friday.remote.laptop_bridge` so the two device bridges read the same.

Security posture:

* A phone never holds the shared control secret. It pairs once with a
  short-lived 6-digit code (issued only to a control-authenticated caller)
  and receives a per-device token; only the token's SHA-256 hash is kept on
  the server, in the state file below, so a state-file leak is not a phone
  takeover and any single device can be revoked without touching others.
* Only the commands in :data:`ALLOWED_PHONE_COMMANDS` are dispatched, and
  only when the connected executor advertised the matching capability in its
  ``hello`` frame. An executor that cannot inject input (the Termux agent)
  therefore gets a precise refusal for ``tap`` instead of a fake success.
* Every result is bounded (per command) so a chatty or hostile executor
  cannot exhaust cloud memory. The output is evidence, not a file channel.
* ``FRIDAY_PHONE_ENABLED=false`` closes pairing and the tunnel entirely.

State: paired-device records persist to ``FRIDAY_PHONE_STATE_FILE`` or
``<FRIDAY>/.data/phone/bridge_state.json`` (atomic replace, mode 0600 where
the OS honours it). Live sockets and pending requests are process memory
only — a FRIDAY restart drops the tunnel and the phone agent reconnects.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from friday.core.logging import get_logger

logger = get_logger("remote.phone_bridge")

MAX_OUTPUT_BYTES = 16 * 1024
MAX_SCREENSHOT_BYTES = 2 * 1024 * 1024
MAX_ERROR_CHARS = 2 * 1024
MAX_ARGS_BYTES = 64 * 1024
DEFAULT_COMMAND_TIMEOUT = 30.0
MAX_COMMAND_TIMEOUT = 300.0
MAX_KNOWN_DEVICES = 16

PAIRING_CODE_TTL_SECONDS = 600.0
PAIRING_CODE_MAX_ATTEMPTS = 5
PAIRING_CODE_LENGTH = 6

ALLOWED_PHONE_COMMANDS = frozenset(
    {
        "device_status",
        "open_app",
        "close_app",
        "open_url",
        "make_call",
        "send_sms",
        "send_whatsapp",
        "read_notifications",
        "set_alarm",
        "media_control",
        "set_volume",
        "find_phone",
        "tap",
        "swipe",
        "type_text",
        "press_key",
        "screenshot",
        # TASK-IG-LAP-01: the on-screen UI hierarchy (node list), the
        # observation half of natural-language UI automation. Executors
        # prune it to actionable nodes before sending (see
        # scripts/phone_ui_agent_adb.py).
        "ui_dump",
    }
)

# Commands whose result is an image payload and therefore gets the larger
# bound. Everything else stays at MAX_OUTPUT_BYTES. ui_dump joins them:
# a pruned hierarchy of a dense screen legitimately exceeds 16 KB.
_LARGE_RESULT_COMMANDS = frozenset({"screenshot", "ui_dump"})

_TRUNCATION_MARKER = "\n[truncated]"
_DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
_PAIRING_CODE_PATTERN = re.compile(r"^\d{6}$")


class PhoneBridgeError(RuntimeError):
    """Base class for failures that the API layer maps to an HTTP status."""


class PhoneNotConnected(PhoneBridgeError):
    """No tunnel is currently registered for the requested phone."""


class PhoneDisconnected(PhoneBridgeError):
    """The tunnel disappeared while a command was in flight."""

    def __init__(self, message: str, evidence: dict[str, Any]) -> None:
        super().__init__(message)
        self.evidence = evidence


class PhoneBridgeTimeout(PhoneBridgeError):
    """The phone did not answer within the requested deadline."""

    def __init__(self, evidence: dict[str, Any]) -> None:
        super().__init__(str(evidence.get("error") or "phone command timed out"))
        self.evidence = evidence


class PhoneUnsupportedCommand(PhoneBridgeError):
    """The connected executor did not advertise this command's capability."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def phone_bridge_enabled() -> bool:
    """Kill switch: ``FRIDAY_PHONE_ENABLED=false`` closes the phone bridge."""
    return os.getenv("FRIDAY_PHONE_ENABLED", "").strip().lower() not in {
        "0",
        "false",
        "no",
        "off",
    }


def normalise_device_id(value: str) -> str:
    """Return a safe device id or raise ``ValueError``.

    The id ends up in a URL path component, a log line and the API response,
    so it is restricted to a small character set rather than escaped later.
    """
    text = (value or "").strip()
    if not _DEVICE_ID_PATTERN.match(text):
        raise ValueError(
            "device_id must be 1-64 characters of letters, digits, dot, colon, dash or underscore"
        )
    return text


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _bounded(value: Any, limit: int = MAX_OUTPUT_BYTES) -> str:
    """Render a value as UTF-8 text no larger than ``limit`` bytes."""
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str)
        except (TypeError, ValueError):
            text = str(value)
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text
    marker = _TRUNCATION_MARKER.encode("utf-8")
    keep = max(0, limit - len(marker))
    return raw[:keep].decode("utf-8", errors="ignore") + _TRUNCATION_MARKER


def _normalise_timeout(value: float | int | None) -> float:
    try:
        timeout = float(DEFAULT_COMMAND_TIMEOUT if value is None else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timeout must be a number of seconds") from exc
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be a positive number of seconds")
    return min(timeout, MAX_COMMAND_TIMEOUT)


def _normalise_args(args: dict[str, Any] | None) -> dict[str, Any]:
    if args is None:
        return {}
    if not isinstance(args, dict):
        raise ValueError("args must be a JSON object")
    try:
        encoded = json.dumps(args)
    except (TypeError, ValueError) as exc:
        raise ValueError("args must contain only JSON-serialisable values") from exc
    if len(encoded.encode("utf-8")) > MAX_ARGS_BYTES:
        raise ValueError("args is too large")
    return dict(args)


def _evidence(
    *,
    request_id: str,
    device_id: str,
    command: str,
    started_at: str,
    finished_at: str,
    ok: bool,
    output: Any,
    error: Any,
) -> dict[str, Any]:
    limit = MAX_SCREENSHOT_BYTES if command in _LARGE_RESULT_COMMANDS else MAX_OUTPUT_BYTES
    return {
        "request_id": request_id,
        "device_id": device_id,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": bool(ok),
        "output": _bounded(output, limit),
        "error": None if error is None else _bounded(error, MAX_ERROR_CHARS),
    }


def default_state_file() -> Path:
    """Where paired-device records live (override: FRIDAY_PHONE_STATE_FILE)."""
    override = os.getenv("FRIDAY_PHONE_STATE_FILE", "").strip()
    if override:
        return Path(override).expanduser()
    here = Path(__file__).resolve()
    # FRIDAY/src/friday/remote/phone_bridge.py -> FRIDAY/.data/phone/...
    return here.parents[3] / ".data" / "phone" / "bridge_state.json"


class PairingStore:
    """Paired devices + outstanding pairing codes.

    Device records persist to disk (hashed tokens only). Pairing codes are
    memory-only: a restart invalidates an unconsumed code, which is the safe
    direction. All disk writes are atomic (tmp file + ``os.replace``) and go
    through one lock, because pairing is rare and correctness beats speed.
    """

    def __init__(self, state_file: Path | None = None) -> None:
        self._state_file = state_file or default_state_file()
        self._lock = threading.Lock()
        self._devices: dict[str, dict[str, Any]] = {}
        self._codes: dict[str, dict[str, Any]] = {}
        self._load()

    # -- persistence -----------------------------------------------------

    def _load(self) -> None:
        try:
            raw = self._state_file.read_text(encoding="utf-8")
            data = json.loads(raw)
        except FileNotFoundError:
            return
        except Exception as exc:
            logger.warning("Phone bridge state file unreadable (%s); starting empty", exc)
            return
        devices = data.get("devices") if isinstance(data, dict) else None
        if isinstance(devices, dict):
            for device_id, record in devices.items():
                if isinstance(record, dict) and record.get("token_hash"):
                    self._devices[str(device_id)] = record

    def _save_locked(self) -> None:
        try:
            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_file.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"devices": self._devices}, indent=2, sort_keys=True),
                encoding="utf-8",
            )
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            os.replace(tmp, self._state_file)
        except Exception as exc:
            logger.warning("Phone bridge state save failed: %s", exc)

    # -- pairing codes ----------------------------------------------------

    def create_pairing_code(self, label: str = "") -> dict[str, Any]:
        """Issue a single-use 6-digit code. Returns code + expiry (once)."""
        now = time.time()
        with self._lock:
            self._prune_codes_locked(now)
            code = f"{secrets.randbelow(1_000_000):06d}"
            while code in self._codes:  # vanishingly unlikely, but free to check
                code = f"{secrets.randbelow(1_000_000):06d}"
            self._codes[code] = {
                "created_at": now,
                "expires_at": now + PAIRING_CODE_TTL_SECONDS,
                "attempts": 0,
                "label": (label or "").strip()[:64],
            }
        return {
            "pairing_code": code,
            "expires_in_seconds": int(PAIRING_CODE_TTL_SECONDS),
            "expires_at": datetime.fromtimestamp(
                now + PAIRING_CODE_TTL_SECONDS, tz=timezone.utc
            ).isoformat(),
        }

    def consume_pairing_code(
        self, code: str, device_name: str = "", executor: str = ""
    ) -> dict[str, Any] | None:
        """Exchange a valid code for a device record + one-time plain token.

        Returns ``None`` for an unknown, expired or burned code — the caller
        cannot distinguish which, by design. A wrong guess burns one attempt
        on *every* outstanding code, so online guessing is bounded by the
        attempt cap on the whole code space, not per code.
        """
        text = (code or "").strip()
        if not _PAIRING_CODE_PATTERN.match(text):
            return None
        now = time.time()
        with self._lock:
            self._prune_codes_locked(now)
            record = self._codes.get(text)
            if record is None:
                for other in self._codes.values():
                    other["attempts"] = int(other.get("attempts", 0)) + 1
                self._prune_codes_locked(now)
                return None
            if int(record.get("attempts", 0)) >= PAIRING_CODE_MAX_ATTEMPTS:
                self._codes.pop(text, None)
                return None
            # Single-use: consume before issuing so a replay races to nothing.
            self._codes.pop(text, None)
            device_id = "phone-" + uuid.uuid4().hex[:12]
            token = secrets.token_urlsafe(32)
            self._devices[device_id] = {
                "token_hash": _hash_token(token),
                "name": (device_name or "").strip()[:64] or "Android phone",
                "executor": (executor or "").strip()[:32] or "unknown",
                "paired_at": _now_iso(),
                "label": record.get("label", ""),
            }
            self._save_locked()
        return {"device_id": device_id, "device_token": token}

    def _prune_codes_locked(self, now: float) -> None:
        stale = [
            code
            for code, rec in self._codes.items()
            if rec.get("expires_at", 0) <= now
            or int(rec.get("attempts", 0)) > PAIRING_CODE_MAX_ATTEMPTS
        ]
        for code in stale:
            self._codes.pop(code, None)

    # -- device records -----------------------------------------------------

    def authenticate(self, device_id: str, token: str) -> bool:
        """Constant-time check of a presented device token."""
        if not device_id or not token:
            return False
        with self._lock:
            record = self._devices.get(device_id)
            expected = record.get("token_hash") if record else None
        if not expected:
            return False
        return hmac.compare_digest(_hash_token(token), str(expected))

    def get_device(self, device_id: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._devices.get(device_id)
            return dict(record) if record else None

    def list_device_records(self) -> dict[str, dict[str, Any]]:
        with self._lock:
            return {k: dict(v) for k, v in self._devices.items()}

    def revoke(self, device_id: str) -> bool:
        with self._lock:
            if device_id not in self._devices:
                return False
            self._devices.pop(device_id, None)
            self._save_locked()
            return True


@dataclass
class PhoneConnection:
    """One live reverse tunnel and the requests waiting on it."""

    device_id: str
    websocket: Any
    executor: str = "unknown"
    capabilities: frozenset[str] = ALLOWED_PHONE_COMMANDS
    connected_at: str = field(default_factory=_now_iso)
    last_seen: str = field(default_factory=_now_iso)
    pending: dict[str, asyncio.Future[dict[str, Any]]] = field(default_factory=dict)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class PhoneBridge:
    """Registry of phone reverse tunnels, keyed by device id.

    Mirrors :class:`friday.remote.laptop_bridge.LaptopBridge`, plus the
    pairing store and a thread-safe entry point: FRIDAY's tool layer is
    synchronous and runs in worker threads, while every registry mutation
    must happen on the server event loop that owns the sockets. The loop is
    captured when a tunnel registers (``_home_loop``) and
    :meth:`execute_sync` hops onto it with ``run_coroutine_threadsafe``.
    """

    def __init__(self, pairing_store: PairingStore | None = None) -> None:
        self._connections: dict[str, PhoneConnection] = {}
        self._known: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()
        self._home_loop: asyncio.AbstractEventLoop | None = None
        self.pairing = pairing_store or PairingStore()
        for device_id in self.pairing.list_device_records():
            self._known[device_id] = {"connected_at": None, "last_seen": None}

    # -- tunnel lifecycle ---------------------------------------------------

    async def register(
        self,
        device_id: str,
        websocket: Any,
        executor: str = "unknown",
        capabilities: Any = None,
    ) -> PhoneConnection | None:
        """Attach a tunnel and return the connection it replaced, if any.

        ``capabilities=None`` means the executor sent no hello frame and is
        treated as claiming the full allowlist (its own per-command errors
        stay honest); a list — even an empty one — gates dispatch to exactly
        what the executor declared.
        """
        device_id = normalise_device_id(device_id)
        if capabilities is None:
            caps = ALLOWED_PHONE_COMMANDS
        else:
            caps = frozenset(
                str(c).strip()
                for c in capabilities
                if str(c).strip() in ALLOWED_PHONE_COMMANDS
            )
        now = _now_iso()
        try:
            self._home_loop = asyncio.get_running_loop()
        except RuntimeError:
            pass
        async with self._lock:
            previous = self._connections.get(device_id)
            connection = PhoneConnection(
                device_id=device_id,
                websocket=websocket,
                executor=(executor or "unknown")[:32],
                capabilities=caps,
                last_seen=now,
            )
            self._connections[device_id] = connection
            self._remember(device_id, connection.connected_at, now)
            if previous is not None:
                self._fail_pending(previous, "phone_replaced")
            self._prune_known()
        log = logger.warning if previous is not None else logger.info
        log("Phone tunnel registered: %s (executor=%s, %d capabilities)", device_id, connection.executor, len(caps))
        return previous

    async def unregister(self, device_id: str, websocket: Any | None = None) -> None:
        """Remove a tunnel and fail every command still waiting on it.

        ``websocket`` disambiguates a stale route task from a newer tunnel
        for the same phone: a reconnect registers the replacement first, and
        the old task's cleanup must not evict it.
        """
        try:
            device_id = normalise_device_id(device_id)
        except ValueError:
            return
        async with self._lock:
            connection = self._connections.get(device_id)
            if connection is None:
                return
            if websocket is not None and connection.websocket is not websocket:
                return
            self._connections.pop(device_id, None)
            self._fail_pending(connection, "phone_disconnected")
            self._remember(device_id, connection.connected_at, _now_iso())
        logger.info("Phone tunnel unregistered: %s", device_id)

    async def touch(self, device_id: str) -> None:
        """Record a heartbeat so ``last_seen`` reflects phone liveness."""
        try:
            device_id = normalise_device_id(device_id)
        except ValueError:
            return
        async with self._lock:
            connection = self._connections.get(device_id)
            if connection is None:
                return
            connection.last_seen = _now_iso()
            self._remember(device_id, connection.connected_at, connection.last_seen)

    async def resolve_result(self, device_id: str, payload: dict[str, Any]) -> bool:
        """Complete the future waiting for ``payload['request_id']``."""
        try:
            device_id = normalise_device_id(device_id)
        except ValueError:
            return False
        request_id = str(payload.get("request_id") or "").strip()
        if not request_id:
            return False
        async with self._lock:
            connection = self._connections.get(device_id)
            if connection is None:
                return False
            connection.last_seen = _now_iso()
            future = connection.pending.pop(request_id, None)
            if future is None or future.done():
                return False
            future.set_result(dict(payload))
        return True

    # -- introspection --------------------------------------------------------

    async def list_devices(self) -> list[dict[str, Any]]:
        """Return every paired phone, online first, then alphabetically."""
        records = self.pairing.list_device_records()
        async with self._lock:
            devices: dict[str, dict[str, Any]] = {}
            for device_id in set(self._known) | set(records):
                meta = self._known.get(device_id, {})
                record = records.get(device_id, {})
                devices[device_id] = {
                    "device_id": device_id,
                    "name": record.get("name"),
                    "executor": record.get("executor"),
                    "paired_at": record.get("paired_at"),
                    "online": False,
                    "connected_at": None,
                    "last_seen": meta.get("last_seen"),
                    "capabilities": [],
                    "pending_requests": 0,
                }
            for device_id, connection in self._connections.items():
                entry = devices.get(device_id, {"device_id": device_id})
                entry.update(
                    {
                        "online": True,
                        "executor": connection.executor,
                        "connected_at": connection.connected_at,
                        "last_seen": connection.last_seen,
                        "capabilities": sorted(connection.capabilities),
                        "pending_requests": len(connection.pending),
                    }
                )
                devices[device_id] = entry
        return sorted(devices.values(), key=lambda item: (not item["online"], item["device_id"]))

    def is_connected(self, device_id: str | None = None) -> bool:
        """Sync liveness check (no lock: a stale read is acceptable here)."""
        if device_id:
            return device_id in self._connections
        return bool(self._connections)

    def default_device_id(self) -> str | None:
        """The phone to use when the caller didn't name one.

        The owner's setup has exactly one phone; with several paired, the
        first *online* one wins, then the first paired one.
        """
        for device_id, connection in self._connections.items():
            return device_id
        records = self.pairing.list_device_records()
        return next(iter(records), None)

    # -- command dispatch ------------------------------------------------------

    async def execute(
        self,
        device_id: str,
        command: str,
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Run one allowlisted command on ``device_id`` and return evidence.

        Raises :class:`PhoneNotConnected` when there is no tunnel,
        :class:`PhoneUnsupportedCommand` when the executor never advertised
        the capability, :class:`PhoneBridgeTimeout` when the deadline
        expires, and :class:`PhoneDisconnected` when the tunnel closes
        mid-command.
        """
        device_id = normalise_device_id(device_id)
        command = (command or "").strip()
        if command not in ALLOWED_PHONE_COMMANDS:
            raise ValueError(
                f"Unsupported phone command '{command}'. Allowed: "
                + ", ".join(sorted(ALLOWED_PHONE_COMMANDS))
            )
        clean_args = _normalise_args(args)
        deadline = _normalise_timeout(timeout)

        request_id = uuid.uuid4().hex
        started_at = _now_iso()
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()

        async with self._lock:
            connection = self._connections.get(device_id)
            if connection is None:
                raise PhoneNotConnected(f"Phone '{device_id}' is not connected")
            if command not in connection.capabilities:
                raise PhoneUnsupportedCommand(
                    f"The connected executor ({connection.executor}) does not support "
                    f"'{command}'. Supported: {', '.join(sorted(connection.capabilities))}"
                )
            connection.pending[request_id] = future
            connection.last_seen = started_at
            self._remember(device_id, connection.connected_at, started_at)

        frame = {
            "type": "command",
            "request_id": request_id,
            "device_id": device_id,
            "command": command,
            "args": clean_args,
            "timeout": deadline,
        }
        try:
            async with connection.send_lock:
                await connection.websocket.send_json(frame)
        except Exception as exc:
            await self._discard_pending(device_id, request_id)
            raise PhoneDisconnected(
                f"Phone '{device_id}' disconnected before the command was sent",
                _evidence(
                    request_id=request_id,
                    device_id=device_id,
                    command=command,
                    started_at=started_at,
                    finished_at=_now_iso(),
                    ok=False,
                    output="",
                    error=f"phone_disconnected: {type(exc).__name__}",
                ),
            ) from exc

        try:
            result = await asyncio.wait_for(future, timeout=deadline)
        except asyncio.TimeoutError:
            await self._discard_pending(device_id, request_id)
            evidence = _evidence(
                request_id=request_id,
                device_id=device_id,
                command=command,
                started_at=started_at,
                finished_at=_now_iso(),
                ok=False,
                output="",
                error=f"timeout after {deadline:g}s",
            )
            logger.warning("Phone command timed out: %s %s (%s)", device_id, command, request_id)
            raise PhoneBridgeTimeout(evidence) from None

        bridge_error = result.get("_bridge_error")
        if bridge_error:
            raise PhoneDisconnected(
                f"Phone '{device_id}' disconnected while the command was running",
                _evidence(
                    request_id=request_id,
                    device_id=device_id,
                    command=command,
                    started_at=started_at,
                    finished_at=_now_iso(),
                    ok=False,
                    output="",
                    error=str(bridge_error),
                ),
            )

        evidence = _evidence(
            request_id=request_id,
            device_id=device_id,
            command=command,
            started_at=str(result.get("started_at") or started_at),
            finished_at=str(result.get("finished_at") or _now_iso()),
            ok=bool(result.get("ok")),
            output=result.get("output"),
            error=result.get("error"),
        )
        logger.info(
            "Phone command completed: %s %s ok=%s request=%s",
            device_id,
            command,
            evidence["ok"],
            request_id,
        )
        return evidence

    def execute_sync(
        self,
        device_id: str,
        command: str,
        timeout: float = DEFAULT_COMMAND_TIMEOUT,
        args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Blocking wrapper for FRIDAY's synchronous tool layer.

        Hops onto the server loop captured at tunnel registration. Raises
        :class:`PhoneNotConnected` when no tunnel has ever registered in
        this process (there is no loop to hop to and no phone to reach).
        """
        loop = self._home_loop
        if loop is None or loop.is_closed():
            raise PhoneNotConnected(
                "No phone tunnel has connected in this process yet; "
                "the phone agent is not running or FRIDAY just restarted."
            )
        deadline = _normalise_timeout(timeout)
        coro = self.execute(device_id, command, deadline, args)
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        try:
            return future.result(timeout=deadline + 15.0)
        except TimeoutError:
            future.cancel()
            raise PhoneBridgeTimeout(
                _evidence(
                    request_id="",
                    device_id=device_id,
                    command=command,
                    started_at=_now_iso(),
                    finished_at=_now_iso(),
                    ok=False,
                    output="",
                    error=f"timeout after {deadline:g}s (sync bridge wait)",
                )
            ) from None

    async def _discard_pending(self, device_id: str, request_id: str) -> None:
        async with self._lock:
            connection = self._connections.get(device_id)
            if connection is not None:
                connection.pending.pop(request_id, None)

    @staticmethod
    def _fail_pending(connection: PhoneConnection, reason: str) -> None:
        pending = connection.pending
        connection.pending = {}
        for future in pending.values():
            if not future.done():
                future.set_result({"_bridge_error": reason})

    def _remember(self, device_id: str, connected_at: str | None, last_seen: str | None) -> None:
        self._known[device_id] = {
            "connected_at": connected_at,
            "last_seen": last_seen,
        }

    def _prune_known(self) -> None:
        if len(self._known) <= MAX_KNOWN_DEVICES:
            return
        offline = [
            device_id
            for device_id in self._known
            if device_id not in self._connections
            and device_id not in self.pairing.list_device_records()
        ]
        offline.sort(key=lambda device_id: self._known[device_id].get("last_seen") or "")
        for device_id in offline[: len(self._known) - MAX_KNOWN_DEVICES]:
            self._known.pop(device_id, None)


# One registry per process. Its mutable state is guarded by ``PhoneBridge._lock``;
# the pairing store has its own lock because HTTP routes touch it off-loop.
phone_bridge = PhoneBridge()


__all__ = [
    "ALLOWED_PHONE_COMMANDS",
    "DEFAULT_COMMAND_TIMEOUT",
    "MAX_OUTPUT_BYTES",
    "PAIRING_CODE_TTL_SECONDS",
    "PairingStore",
    "PhoneBridge",
    "PhoneBridgeError",
    "PhoneBridgeTimeout",
    "PhoneDisconnected",
    "PhoneNotConnected",
    "PhoneUnsupportedCommand",
    "default_state_file",
    "normalise_device_id",
    "phone_bridge",
    "phone_bridge_enabled",
]
