"""Distributed coordination for memory-intensive FRIDAY Universe workloads.

A single Redis lease serializes heavyweight work across independent workers. The
lease is renewed while its owner is alive, and compare-and-set Lua scripts prevent
an expired owner from deleting or extending a newer owner's lease.

The caller must use a Redis endpoint shared by every worker that needs to
coordinate. An in-process asyncio lock is deliberately not used as a fallback:
that would silently break the cross-process safety guarantee.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import socket
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, TypeVar

logger = logging.getLogger(__name__)
_ResultT = TypeVar("_ResultT")

_ACQUIRE_SCRIPT = """
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'PX', ARGV[2]) then
    return redis.call('INCR', KEYS[2])
end
return 0
"""

_RENEW_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""

_RELEASE_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


class HeavyTaskCoordinationError(RuntimeError):
    """Base exception for coordinator and lease failures."""


class HeavyTaskBackendError(HeavyTaskCoordinationError):
    """The authoritative coordination backend could not be reached."""


class HeavyTaskLeaseLost(HeavyTaskCoordinationError):
    """The caller no longer owns the global heavy-task lease."""


class HeavyTaskAcquireTimeout(HeavyTaskCoordinationError):
    """A lease was not acquired within the caller's wait budget."""


class HeavyTaskCoordinator:
    """Serialize heavy work across processes using one shared Redis lease.

    Redis is authoritative. Missing credentials, backend errors, or lease loss
    must not cause callers to continue as though exclusive ownership were held.
    Lease renewal is automatic, so a healthy worker can hold the lease beyond
    the initial TTL, including jobs lasting 30 minutes or longer.
    """

    def __init__(
        self,
        client: Any,
        *,
        key_prefix: str = "friday-universe",
        lease_seconds: float = 120.0,
        heartbeat_interval: float | None = None,
        poll_interval: float = 0.5,
        max_poll_interval: float = 2.0,
    ) -> None:
        if client is None:
            raise ValueError("a Redis-compatible async client is required")
        if not isinstance(key_prefix, str) or not key_prefix.strip():
            raise ValueError("key_prefix must not be empty")
        if any(char.isspace() for char in key_prefix):
            raise ValueError("key_prefix must not contain whitespace")
        if (
            isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, (int, float))
            or not math.isfinite(lease_seconds)
            or not 3.0 <= lease_seconds <= 86400.0
        ):
            raise ValueError("lease_seconds must be between 3 and 86400 seconds")
        heartbeat = heartbeat_interval
        if heartbeat is None:
            heartbeat = min(30.0, lease_seconds / 3.0)
        if (
            isinstance(heartbeat, bool)
            or not isinstance(heartbeat, (int, float))
            or not math.isfinite(heartbeat)
            or heartbeat <= 0
            or heartbeat >= lease_seconds / 2.0
        ):
            raise ValueError("heartbeat_interval must be positive and less than half the lease")
        if (
            isinstance(poll_interval, bool)
            or not isinstance(poll_interval, (int, float))
            or not math.isfinite(poll_interval)
            or poll_interval <= 0
        ):
            raise ValueError("poll_interval must be positive")
        if (
            isinstance(max_poll_interval, bool)
            or not isinstance(max_poll_interval, (int, float))
            or not math.isfinite(max_poll_interval)
            or max_poll_interval < poll_interval
        ):
            raise ValueError("max_poll_interval must be at least poll_interval")

        self.client = client
        self.key_prefix = key_prefix.strip().strip(":")
        if not self.key_prefix:
            raise ValueError("key_prefix must contain non-colon characters")
        self.lock_key = f"{self.key_prefix}:{{heavy-task}}:lease"
        self.fencing_key = f"{self.key_prefix}:{{heavy-task}}:fence"
        self.lease_seconds = float(lease_seconds)
        self.lease_ms = int(self.lease_seconds * 1000)
        self.heartbeat_interval = float(heartbeat)
        self.poll_interval = float(poll_interval)
        self.max_poll_interval = float(max_poll_interval)

    @classmethod
    def from_url(cls, url: str, **kwargs: Any) -> "HeavyTaskCoordinator":
        """Build a coordinator from a Redis URL without importing Redis eagerly."""
        if not isinstance(url, str) or not url.strip():
            raise ValueError("a shared Redis URL is required for heavy-task coordination")
        try:
            from redis.asyncio import Redis
        except ImportError as exc:
            raise HeavyTaskBackendError(
                "Redis support requires the redis package; no local-lock fallback is safe"
            ) from exc
        client = Redis.from_url(
            url.strip(),
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )
        return cls(client, **kwargs)

    async def _eval(self, script: str, keys: list[str], args: list[str]) -> int:
        try:
            result = await self.client.eval(script, len(keys), *(keys + args))
            return int(result)
        except HeavyTaskCoordinationError:
            raise
        except Exception as exc:
            raise HeavyTaskBackendError(
                f"Redis operation failed ({type(exc).__name__}); heavy work must not proceed without a lease"
            ) from exc

    @staticmethod
    def _decode(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="replace")
        return str(value)

    async def acquire(
        self,
        task_id: str,
        *,
        owner: str | None = None,
        wait_timeout: float | None = 0.0,
    ) -> "HeavyTaskLease | None":
        """Acquire the global lease, waiting up to wait_timeout when requested.

        A zero timeout performs one atomic acquisition attempt. None waits
        indefinitely and remains cancellable. None is returned only when the
        wait budget expires; backend failures raise instead of failing open.
        """
        task_id = self._validate_label(task_id, "task_id")
        owner = self._validate_label(
            owner or f"{socket.gethostname()}:{os.getpid()}",
            "owner",
        )
        if wait_timeout is not None and (
            isinstance(wait_timeout, bool)
            or not isinstance(wait_timeout, (int, float))
            or not math.isfinite(wait_timeout)
            or wait_timeout < 0
        ):
            raise ValueError("wait_timeout must be non-negative or None")

        deadline = None if wait_timeout is None else time.monotonic() + float(wait_timeout)
        nonce = uuid.uuid4().hex
        lock_value = json.dumps(
            {"nonce": nonce, "task_id": task_id, "owner": owner},
            sort_keys=True,
            separators=(",", ":"),
        )
        delay = self.poll_interval

        while True:
            fencing_token = await self._eval(
                _ACQUIRE_SCRIPT,
                [self.lock_key, self.fencing_key],
                [lock_value, str(self.lease_ms)],
            )
            if fencing_token > 0:
                lease = HeavyTaskLease(
                    coordinator=self,
                    task_id=task_id,
                    owner=owner,
                    lock_value=lock_value,
                    fencing_token=fencing_token,
                )
                lease._start_heartbeat()
                return lease

            if deadline is not None and time.monotonic() >= deadline:
                return None

            sleep_for = random.uniform(delay * 0.8, delay * 1.2)
            if deadline is not None:
                sleep_for = min(sleep_for, max(0.0, deadline - time.monotonic()))
            await asyncio.sleep(sleep_for)
            delay = min(self.max_poll_interval, delay * 1.7)


    async def run(
        self,
        task_id: str,
        operation: Callable[["HeavyTaskLease"], Awaitable[_ResultT]],
        *,
        owner: str | None = None,
        wait_timeout: float | None = 0.0,
    ) -> _ResultT:
        """Run an async operation under the lease and cancel it if ownership is lost.

        The operation receives its lease and should call ensure_valid() before
        irreversible checkpoints. When automatic renewal detects ownership loss
        or a backend outage, the coordinator cancels the operation and raises
        HeavyTaskLeaseLost instead of returning a success-shaped result.
        """
        if not callable(operation):
            raise ValueError("operation must be an async callable accepting a lease")
        async with self.hold(
            task_id,
            owner=owner,
            wait_timeout=wait_timeout,
        ) as lease:
            work_task = asyncio.create_task(
                operation(lease),
                name=f"heavy-task-work:{task_id}",
            )
            lost_task = asyncio.create_task(
                lease._lost_event.wait(),
                name=f"heavy-task-loss-watch:{task_id}",
            )
            try:
                await asyncio.wait(
                    {work_task, lost_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if lease.is_lost:
                    if not work_task.done():
                        work_task.cancel()
                    await asyncio.gather(work_task, return_exceptions=True)
                    lease.ensure_valid()
                lease.ensure_valid()
                return await work_task
            finally:
                lost_task.cancel()
                await asyncio.gather(lost_task, return_exceptions=True)
                if not work_task.done():
                    work_task.cancel()
                    await asyncio.gather(work_task, return_exceptions=True)

    @staticmethod
    def _validate_label(value: str, field: str) -> str:
        if not isinstance(value, str):
            raise ValueError(f"{field} must be a string")
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{field} must not be empty")
        if len(normalized) > 256:
            raise ValueError(f"{field} must be at most 256 characters")
        if any(ord(char) < 32 for char in normalized):
            raise ValueError(f"{field} must not contain control characters")
        return normalized

    async def inspect(self) -> dict[str, Any]:
        """Report current lock owner and remaining TTL without exposing its nonce."""
        try:
            raw_value = self._decode(await self.client.get(self.lock_key))
            ttl_ms = int(await self.client.pttl(self.lock_key))
        except Exception as exc:
            raise HeavyTaskBackendError(
                f"Redis inspection failed ({type(exc).__name__})"
            ) from exc

        if raw_value is None or ttl_ms in (-2, 0):
            return {
                "locked": False,
                "task_id": None,
                "owner": None,
                "lease_remaining_ms": 0,
            }
        if ttl_ms < 0:
            raise HeavyTaskBackendError(
                "heavy-task lock is missing its expiry; refusing to report a healthy lease"
            )
        try:
            details = json.loads(raw_value)
        except (TypeError, ValueError) as exc:
            raise HeavyTaskBackendError("heavy-task lock contains an invalid owner record") from exc
        if not isinstance(details, dict) or not details.get("task_id") or not details.get("owner"):
            raise HeavyTaskBackendError("heavy-task lock owner record is incomplete")
        return {
            "locked": True,
            "task_id": details["task_id"],
            "owner": details["owner"],
            "lease_remaining_ms": ttl_ms,
        }

    @asynccontextmanager
    async def hold(
        self,
        task_id: str,
        *,
        owner: str | None = None,
        wait_timeout: float | None = 0.0,
    ) -> AsyncIterator["HeavyTaskLease"]:
        """Context manager that guarantees best-effort lease cleanup on exit."""
        lease = await self.acquire(task_id, owner=owner, wait_timeout=wait_timeout)
        if lease is None:
            raise HeavyTaskAcquireTimeout(
                f"could not acquire the global heavy-task lease for {task_id!r}"
            )
        try:
            yield lease
        finally:
            try:
                await lease.release()
            except HeavyTaskBackendError:
                # Redis TTL is the crash-recovery path; don't mask the actual
                # build/scan/forecast exception when cleanup connectivity fails.
                logger.exception(
                    "Unable to release heavy-task lease for task %s; TTL will recover it",
                    task_id,
                )


def coordinator_from_environment(
    environ: dict[str, str] | None = None,
) -> HeavyTaskCoordinator | None:
    """Resolve the shared coordinator from service configuration.

    Development remains usable without Redis unless the operator explicitly
    requires distributed serialization. Production deployments should set both
    FRIDAY_UNIVERSE_HEAVY_TASK_REDIS_URL and
    FRIDAY_UNIVERSE_REQUIRE_DISTRIBUTED_HEAVY_TASKS=true. A missing URL in
    required mode raises immediately rather than silently using a local lock.
    """
    env = os.environ if environ is None else environ
    url = env.get("FRIDAY_UNIVERSE_HEAVY_TASK_REDIS_URL", "").strip()
    required_value = env.get("FRIDAY_UNIVERSE_REQUIRE_DISTRIBUTED_HEAVY_TASKS", "")
    required = required_value.strip().lower() in {"1", "true", "yes", "on"}
    if not url:
        if required:
            raise HeavyTaskBackendError(
                "FRIDAY_UNIVERSE_HEAVY_TASK_REDIS_URL is required when distributed "
                "heavy-task coordination is enabled"
            )
        return None
    prefix = env.get("FRIDAY_UNIVERSE_HEAVY_TASK_KEY_PREFIX", "friday-universe").strip()
    if not prefix or any(char.isspace() for char in prefix) or not prefix.strip(":"):
        raise ValueError(
            "FRIDAY_UNIVERSE_HEAVY_TASK_KEY_PREFIX must be non-empty and contain no whitespace"
        )
    try:
        return HeavyTaskCoordinator.from_url(url, key_prefix=prefix)
    except (ValueError, HeavyTaskBackendError):
        raise
    except Exception as exc:
        raise HeavyTaskBackendError(
            f"unable to configure distributed heavy-task coordination ({type(exc).__name__})"
        ) from exc


class HeavyTaskLease:
    """A renewable lease. Call ensure_valid before irreversible checkpoints."""

    def __init__(
        self,
        *,
        coordinator: HeavyTaskCoordinator,
        task_id: str,
        owner: str,
        lock_value: str,
        fencing_token: int,
    ) -> None:
        self.coordinator = coordinator
        self.task_id = task_id
        self.owner = owner
        self.lock_value = lock_value
        self.fencing_token = fencing_token
        self._lost_event = asyncio.Event()
        self._lost_reason: str | None = None
        self._released = False
        self._release_guard = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    @property
    def is_lost(self) -> bool:
        return self._lost_event.is_set()

    @property
    def lost_reason(self) -> str | None:
        return self._lost_reason

    @property
    def is_released(self) -> bool:
        return self._released

    def _start_heartbeat(self) -> None:
        self._heartbeat_task = asyncio.create_task(
            self._heartbeat_loop(),
            name=f"heavy-task-lease:{self.task_id}",
        )

    def _lose(self, reason: str) -> None:
        if not self._lost_event.is_set():
            self._lost_reason = reason
            self._lost_event.set()
            logger.error(
                "Heavy-task lease lost for %s (fencing token %s): %s",
                self.task_id,
                self.fencing_token,
                reason,
            )

    async def heartbeat(self) -> bool:
        """Extend this lease now; return False and mark loss when ownership fails."""
        if self._released or self.is_lost:
            return False
        try:
            renewed = await self.coordinator._eval(
                _RENEW_SCRIPT,
                [self.coordinator.lock_key],
                [self.lock_value, str(self.coordinator.lease_ms)],
            )
        except HeavyTaskBackendError as exc:
            self._lose(str(exc))
            return False
        if renewed != 1:
            self._lose("Redis no longer recognizes this lease owner")
            return False
        return True

    async def _heartbeat_loop(self) -> None:
        try:
            while not self._released and not self.is_lost:
                await asyncio.sleep(self.coordinator.heartbeat_interval)
                await self.heartbeat()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._lose(f"unexpected heartbeat failure ({type(exc).__name__})")

    def ensure_valid(self) -> None:
        """Raise instead of allowing a task to continue after lease loss."""
        if self.is_lost:
            raise HeavyTaskLeaseLost(
                self.lost_reason or f"lease for task {self.task_id!r} has been lost"
            )
        if self._released:
            raise HeavyTaskLeaseLost(f"lease for task {self.task_id!r} has been released")

    async def release(self) -> bool:
        """Release only if Redis still stores this exact lease's owner token."""
        async with self._release_guard:
            if self._released:
                return False
            self._released = True
            heartbeat_task = self._heartbeat_task
            if heartbeat_task is not None and heartbeat_task is not asyncio.current_task():
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
            try:
                deleted = await self.coordinator._eval(
                    _RELEASE_SCRIPT,
                    [self.coordinator.lock_key],
                    [self.lock_value],
                )
            except HeavyTaskBackendError:
                self._lose("release request failed; Redis TTL will recover the lease")
                raise
            return deleted == 1
