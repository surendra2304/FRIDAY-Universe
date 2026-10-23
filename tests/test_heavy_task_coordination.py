from __future__ import annotations

import asyncio
import time
import unittest

from mesh.heavy_task import (
    _ACQUIRE_SCRIPT,
    HeavyTaskAcquireTimeout,
    HeavyTaskBackendError,
    HeavyTaskCoordinator,
    HeavyTaskLeaseLost,
)


class FakeRedis:
    """Small atomic Redis test double; separate clients can share the same state."""

    def __init__(self, shared_state: dict | None = None) -> None:
        state = shared_state if shared_state is not None else {}
        self.values = state.setdefault("values", {})
        self.counters = state.setdefault("counters", {})
        self.gate = state.setdefault("gate", asyncio.Lock())
        self.fail = False

    def _purge(self, key: str) -> None:
        current = self.values.get(key)
        if current and current[1] is not None and current[1] <= time.monotonic():
            self.values.pop(key, None)

    async def eval(self, script: str, number_of_keys: int, *args: str) -> int:
        if self.fail:
            raise OSError("simulated Redis outage")
        keys = list(args[:number_of_keys])
        argv = list(args[number_of_keys:])
        async with self.gate:
            lock_key = keys[0]
            self._purge(lock_key)
            if script == _ACQUIRE_SCRIPT:
                if lock_key in self.values:
                    return 0
                value, lease_ms = argv
                self.values[lock_key] = (value, time.monotonic() + int(lease_ms) / 1000)
                fence_key = keys[1]
                self.counters[fence_key] = self.counters.get(fence_key, 0) + 1
                return self.counters[fence_key]

            value = argv[0]
            current = self.values.get(lock_key)
            if not current or current[0] != value:
                return 0
            if "PEXPIRE" in script:
                self.values[lock_key] = (
                    value,
                    time.monotonic() + int(argv[1]) / 1000,
                )
                return 1
            if "redis.call('DEL'" in script:
                self.values.pop(lock_key, None)
                return 1
            raise AssertionError("test encountered an unknown Redis script")

    async def get(self, key: str):
        if self.fail:
            raise OSError("simulated Redis outage")
        async with self.gate:
            self._purge(key)
            value = self.values.get(key)
            return value[0] if value else None

    async def pttl(self, key: str) -> int:
        if self.fail:
            raise OSError("simulated Redis outage")
        async with self.gate:
            self._purge(key)
            value = self.values.get(key)
            if value is None:
                return -2
            return max(0, int((value[1] - time.monotonic()) * 1000))


class HeavyTaskCoordinatorTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        shared: dict = {}
        self.redis_a = FakeRedis(shared)
        self.redis_b = FakeRedis(shared)
        self.coordinator_a = HeavyTaskCoordinator(
            self.redis_a,
            key_prefix="test-universe",
            lease_seconds=3,
            heartbeat_interval=0.1,
            poll_interval=0.005,
            max_poll_interval=0.02,
        )
        self.coordinator_b = HeavyTaskCoordinator(
            self.redis_b,
            key_prefix="test-universe",
            lease_seconds=3,
            heartbeat_interval=0.1,
            poll_interval=0.005,
            max_poll_interval=0.02,
        )

    async def asyncTearDown(self) -> None:
        # Tests intentionally simulate lease loss and backend outages. Expire
        # leftover records so each isolated event loop starts with clean state.
        for redis_client in (self.redis_a, self.redis_b):
            async with redis_client.gate:
                redis_client.values.clear()

    async def test_only_one_of_two_workers_can_acquire(self) -> None:
        first, second = await asyncio.gather(
            self.coordinator_a.acquire("forge-build", owner="worker-a"),
            self.coordinator_b.acquire("sentinel-scan", owner="worker-b"),
        )
        leases = [lease for lease in (first, second) if lease is not None]
        self.assertEqual(len(leases), 1)
        await leases[0].release()

    async def test_release_allows_next_worker_to_acquire(self) -> None:
        first = await self.coordinator_a.acquire("forge-build", owner="a")
        self.assertIsNotNone(first)
        self.assertTrue(await first.release())
        second = await self.coordinator_b.acquire("forecast-fit", owner="b")
        self.assertIsNotNone(second)
        self.assertGreater(second.fencing_token, first.fencing_token)
        await second.release()

    async def test_wait_timeout_returns_none_when_lock_is_busy(self) -> None:
        first = await self.coordinator_a.acquire("forge-build", owner="a")
        self.assertIsNotNone(first)
        started = time.monotonic()
        second = await self.coordinator_b.acquire(
            "security-scan",
            owner="b",
            wait_timeout=0.04,
        )
        elapsed = time.monotonic() - started
        self.assertIsNone(second)
        self.assertGreaterEqual(elapsed, 0.03)
        self.assertLess(elapsed, 0.5)
        await first.release()

    async def test_indefinite_waiter_acquires_after_release(self) -> None:
        first = await self.coordinator_a.acquire("forge-build", owner="a")
        self.assertIsNotNone(first)
        waiter = asyncio.create_task(
            self.coordinator_b.acquire("security-scan", owner="b", wait_timeout=None)
        )
        await asyncio.sleep(0.03)
        self.assertFalse(waiter.done())
        await first.release()
        second = await asyncio.wait_for(waiter, timeout=0.5)
        self.assertIsNotNone(second)
        await second.release()

    async def test_fencing_tokens_increase_monotonically(self) -> None:
        first = await self.coordinator_a.acquire("job-one", owner="a")
        self.assertIsNotNone(first)
        first_token = first.fencing_token
        await first.release()
        second = await self.coordinator_b.acquire("job-two", owner="b")
        self.assertIsNotNone(second)
        self.assertGreater(second.fencing_token, first_token)
        await second.release()

    async def test_old_owner_cannot_delete_new_owner_lease(self) -> None:
        first = await self.coordinator_a.acquire("job-one", owner="a")
        self.assertIsNotNone(first)
        async with self.redis_a.gate:
            self.redis_a.values[self.coordinator_a.lock_key] = (
                '{"nonce":"new","task_id":"job-two","owner":"b"}',
                time.monotonic() + 3,
            )
        self.assertFalse(await first.release())
        status = await self.coordinator_b.inspect()
        self.assertTrue(status["locked"])
        self.assertEqual(status["task_id"], "job-two")

    async def test_lease_heartbeat_extends_ttl_for_long_running_jobs(self) -> None:
        lease = await self.coordinator_a.acquire("long-running-task", owner="worker")
        self.assertIsNotNone(lease)
        await asyncio.sleep(0.35)
        lease.ensure_valid()
        status = await self.coordinator_b.inspect()
        self.assertTrue(status["locked"])
        self.assertEqual(status["task_id"], "long-running-task")
        self.assertGreater(status["lease_remaining_ms"], 2000)
        await lease.release()

    async def test_lost_owner_is_detected_and_fails_closed(self) -> None:
        lease = await self.coordinator_a.acquire("long-running-task", owner="worker")
        self.assertIsNotNone(lease)
        async with self.redis_a.gate:
            self.redis_a.values[self.coordinator_a.lock_key] = (
                '{"nonce":"replacement","task_id":"new-task","owner":"other"}',
                time.monotonic() + 3,
            )
        self.assertFalse(await lease.heartbeat())
        with self.assertRaises(HeavyTaskLeaseLost):
            lease.ensure_valid()
        await lease.release()

    async def test_backend_error_does_not_fall_back_to_a_local_lock(self) -> None:
        self.redis_a.fail = True
        with self.assertRaises(HeavyTaskBackendError):
            await self.coordinator_a.acquire("forge-build", owner="worker")
        self.redis_a.fail = False

    async def test_inspect_reports_owner_without_returning_secret_nonce(self) -> None:
        lease = await self.coordinator_a.acquire("security-scan", owner="sentinel")
        self.assertIsNotNone(lease)
        status = await self.coordinator_b.inspect()
        self.assertEqual(status["owner"], "sentinel")
        self.assertEqual(status["task_id"], "security-scan")
        self.assertNotIn("nonce", status)
        self.assertGreater(status["lease_remaining_ms"], 0)
        await lease.release()

    async def test_hold_context_releases_when_body_raises(self) -> None:
        with self.assertRaisesRegex(ValueError, "task failed"):
            async with self.coordinator_a.hold("forecast-fit", owner="futuris") as lease:
                lease.ensure_valid()
                raise ValueError("task failed")
        status = await self.coordinator_b.inspect()
        self.assertFalse(status["locked"])

    async def test_hold_raises_when_acquisition_times_out(self) -> None:
        lease = await self.coordinator_a.acquire("first", owner="a")
        self.assertIsNotNone(lease)
        with self.assertRaises(HeavyTaskAcquireTimeout):
            async with self.coordinator_b.hold(
                "second",
                owner="b",
                wait_timeout=0,
            ):
                self.fail("body must not run without the lock")
        await lease.release()

    async def test_release_is_idempotent(self) -> None:
        lease = await self.coordinator_a.acquire("job", owner="worker")
        self.assertIsNotNone(lease)
        self.assertTrue(await lease.release())
        self.assertFalse(await lease.release())

    async def test_invalid_task_metadata_is_rejected(self) -> None:
        for task_id in ("", "   ", "task\nname", "x" * 257):
            with self.subTest(task_id=repr(task_id)):
                with self.assertRaises(ValueError):
                    await self.coordinator_a.acquire(task_id)
        with self.assertRaises(ValueError):
            await self.coordinator_a.acquire("ok", wait_timeout=-1)

    async def test_invalid_timing_configuration_is_rejected(self) -> None:
        for kwargs in (
            {"lease_seconds": 2},
            {"lease_seconds": 3, "heartbeat_interval": 1.5},
            {"poll_interval": 0},
            {"poll_interval": 1, "max_poll_interval": 0.5},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    HeavyTaskCoordinator(self.redis_a, **kwargs)


if __name__ == "__main__":
    unittest.main()
