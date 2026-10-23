# Distributed heavy-task coordination

FRIDAY-Universe uses one Redis-backed lease to serialize the most expensive
workloads that can otherwise multiply CPU and memory use across workers. The
shared implementation lives in `mesh/heavy_task.py`; all participating
services must use the same Redis database and key prefix.

## Integrated call sites

- **Forge:** baseline capture and the complete build/test/quality verification
  battery acquire the lease before running their checkers.
- **Futuris:** model fitting acquires the lease around the full fit/predict stage.
- **Sentinel:** action types classified as scans, audits, vulnerability/dependency
  work, static analysis, or codebase checks run under the same lease.
- Every service checks lease ownership, and the lease heartbeat renews it while
  work is in progress. Lease loss cancels the cooperative async operation and
  does not silently switch to a process-local mutex.

The Redis lease TTL defaults to 120 seconds and renews every 30 seconds. This is
a renewable lease, not a fixed-duration task timer; healthy work may run longer
than 30 minutes. Fencing tokens monotonically increase and can be attached to
downstream writes that support stale-owner rejection.

## Compose setup

The `docker-compose.oracle.yml` stack contains a Redis 7 service with persistent
storage, password authentication, and no published host port. Forge, Futuris,
and Sentinel wait for Redis health and receive the same key prefix and URL.

Before running Compose, set `FRIDAY_UNIVERSE_REDIS_PASSWORD` in the shell or a
private, untracked Compose `.env` file. Generate a URL-safe high-entropy value
with:

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Do not commit that value. Keep its URL-safe characters intact; the Compose file
uses it in the Redis URL. A password is required for Compose configuration, and
the Redis server requires the same password.

The participating services set
`FRIDAY_UNIVERSE_REQUIRE_DISTRIBUTED_HEAVY_TASKS=true`. If the Redis URL is
missing at startup, configuration fails rather than falsely claiming global
serialization. If Redis later becomes unavailable or a lease is lost, heavy
operations fail closed.

In development, omitting the Redis URL is allowed by default so pure unit tests
and local edits do not require a Redis server. That mode does not provide
cross-process serialization; set the required-mode flag whenever that property
must be enforced.

## Lease semantics

- Acquisition is atomic (`SET NX PX`) and includes a unique owner nonce.
- Renewal and release are compare-and-set operations; an expired owner cannot
  renew or delete a newer owner's lease.
- Fencing tokens are allocated atomically and use the same Redis Cluster hash
  slot as the lease.
- Contending workers may wait indefinitely with cancellable async waits. A
  failed Redis operation does not grant a lease.
- `HeavyTaskCoordinator.run` cancels cooperative async work after lease loss.
  CPU child-process termination and downstream fencing still depend on the
  operation/adapter honoring cancellation or the fencing token.

## Validation status

The repository regression suite uses a shared atomic Redis test double for
acquisition, competing workers, renewal, fencing, timeouts, release races, and
lease-loss cancellation. The test double validates client logic, not Redis
server behavior. A live Redis integration/soak test and a real deployment have
not been claimed as completed by these code changes.
