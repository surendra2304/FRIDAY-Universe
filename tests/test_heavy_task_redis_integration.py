"""Integration tests exercising the coordinator against a real Redis server.

The ordinary test suite uses an atomic fake so it can run locally without
external infrastructure. CI supplies FRIDAY_UNIVERSE_TEST_REDIS_URL and runs
these cases against its isolated Redis service.
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
import uuid
from pathlib import Path

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - covered by CI dependency installation
    redis_async = None

from mesh.heavy_task import HeavyTaskCoordinator, HeavyTaskLeaseLost

FUTURIS_ROOT = Path(__file__).resolve().parents[1] / "Futuris"
if FUTURIS_ROOT.is_dir():
    sys.path.insert(0, str(FUTURIS_ROOT))
try:
    from futuris.infra.cpu import run_cpu_process_cancellable
except ImportError:  # The lighter validation workflow omits the Futuris CPU extras.
    run_cpu_process_cancellable = None

REDIS_URL = os.getenv("FRIDAY_UNIVERSE_TEST_REDIS_URL", "").strip()
REDIS_AVAILABLE = bool(REDIS_URL and redis_async is not None)
CPU_WORKER_AVAILABLE = run_cpu_process_cancellable is not None


def _write_child_pid_then_wait(marker_path: str, duration_seconds: float) -> int:
    """Module-level picklable CPU job used to prove cancellation kills its child."""
    Path(marker_path).write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(duration_seconds)
    return os.getpid()


@unittest.skipUnless(
    REDIS_AVAILABLE,
    "set FRIDAY_UNIVERSE_TEST_REDIS_URL and install redis to run live Redis tests",
)
class HeavyTaskRedisIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.client = redis_async.Redis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        self.prefix = f"friday-test-{uuid.uuid4().hex}"
        self.coordinator_a = HeavyTaskCoordinator(
            self.client,
            key_prefix=self.prefix,
            lease_seconds=3,
            heartbeat_interval=0.25,
            poll_interval=0.01,
            max_poll_interval=0.05,
        )
        self.coordinator_b = HeavyTaskCoordinator(
            self.client,
            key_prefix=self.prefix,
            lease_seconds=3,
            heartbeat_interval=0.25,
            poll_interval=0.01,
            max_poll_interval=0.05,
        )

    async def asyncTearDown(self) -> None:
        await self.client.delete(
            self.coordinator_a.lock_key,
            self.coordinator_a.fencing_key,
        )
        await self.client.aclose()

    async def test_two_independent_clients_share_one_global_lease(self) -> None:
        first, second = await asyncio.gather(
            self.coordinator_a.acquire("forge-verification", owner="forge"),
            self.coordinator_b.acquire("sentinel-scan", owner="sentinel"),
        )
        leases = [lease for lease in (first, second) if lease is not None]
        self.assertEqual(len(leases), 1)
        status = await self.coordinator_a.inspect()
        self.assertTrue(status["locked"])
        self.assertIn(status["owner"], {"forge", "sentinel"})
        await leases[0].release()

    async def test_heartbeat_keeps_lease_beyond_initial_ttl(self) -> None:
        lease = await self.coordinator_a.acquire("long-fit", owner="futuris")
        self.assertIsNotNone(lease)
        # Longer than the initial three-second expiry; only heartbeat renewal
        # can keep this key authoritative for the competing client.
        await asyncio.sleep(3.4)
        lease.ensure_valid()
        status = await self.coordinator_b.inspect()
        self.assertTrue(status["locked"])
        self.assertGreater(status["lease_remaining_ms"], 1500)
        contender = await self.coordinator_b.acquire(
            "forge-build",
            owner="forge",
            wait_timeout=0.05,
        )
        self.assertIsNone(contender)
        await lease.release()

    async def test_stale_owner_cannot_release_replaced_lease(self) -> None:
        lease = await self.coordinator_a.acquire("old-task", owner="old-worker")
        self.assertIsNotNone(lease)
        replacement = '{"nonce":"new-owner","task_id":"new-task","owner":"new-worker"}'
        await self.client.set(self.coordinator_a.lock_key, replacement, px=10000)
        self.assertFalse(await lease.release())
        stored = await self.client.get(self.coordinator_a.lock_key)
        self.assertEqual(stored, replacement)


    @unittest.skipUnless(
        CPU_WORKER_AVAILABLE,
        "Futuris worker dependencies are not installed in this test environment",
    )
    async def test_lease_loss_terminates_child_before_coordinator_returns(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            marker = str(Path(directory) / "worker.pid")

            async def long_work(lease):
                lease.ensure_valid()
                return await run_cpu_process_cancellable(
                    "lease-loss-integration",
                    _write_child_pid_then_wait,
                    marker,
                    30.0,
                    _exclusive=True,
                )

            work = asyncio.create_task(
                self.coordinator_a.run(
                    "futuris:model-fit",
                    long_work,
                    owner="futuris",
                    wait_timeout=0,
                )
            )
            deadline = asyncio.get_running_loop().time() + 8
            while not Path(marker).exists() and asyncio.get_running_loop().time() < deadline:
                await asyncio.sleep(0.02)
            self.assertTrue(Path(marker).exists(), "CPU worker process did not start")
            child_pid = int(Path(marker).read_text(encoding="utf-8"))

            replacement = (
                '{"nonce":"replacement","task_id":"new-owner","owner":"other-worker"}'
            )
            await self.client.set(self.coordinator_a.lock_key, replacement, px=10000)

            with self.assertRaises(HeavyTaskLeaseLost):
                await asyncio.wait_for(work, timeout=6)

            with self.assertRaises(ProcessLookupError):
                os.kill(child_pid, 0)
            self.assertEqual(await self.client.get(self.coordinator_a.lock_key), replacement)

    async def test_fencing_counter_survives_release_and_reacquisition(self) -> None:
        first = await self.coordinator_a.acquire("first", owner="worker-a")
        self.assertIsNotNone(first)
        first_token = first.fencing_token
        await first.release()

        second = await self.coordinator_b.acquire("second", owner="worker-b")
        self.assertIsNotNone(second)
        self.assertGreater(second.fencing_token, first_token)
        await second.release()


if __name__ == "__main__":
    unittest.main()
