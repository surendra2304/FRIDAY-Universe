"""Integration tests exercising the coordinator against a real Redis server.

The ordinary test suite uses an atomic fake so it can run locally without
external infrastructure. CI supplies FRIDAY_UNIVERSE_TEST_REDIS_URL and runs
these cases against its isolated Redis service.
"""
from __future__ import annotations

import asyncio
import os
import unittest
import uuid

try:
    import redis.asyncio as redis_async
except ImportError:  # pragma: no cover - covered by CI dependency installation
    redis_async = None

from mesh.heavy_task import HeavyTaskCoordinator

REDIS_URL = os.getenv("FRIDAY_UNIVERSE_TEST_REDIS_URL", "").strip()
REDIS_AVAILABLE = bool(REDIS_URL and redis_async is not None)


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
