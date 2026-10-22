from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from forge_upgrade.persistence.idempotency import (
    IdempotencyCapacityError,
    IdempotencyStore,
)


def test_idempotency_basic_compatibility() -> None:
    store = IdempotencyStore()
    key = store.make_key("t", "i")

    assert not store.seen(key)
    store.remember(key, "response")
    assert store.seen(key)
    assert store.get(key).response_hash == "response"  # type: ignore[union-attr]


@pytest.mark.parametrize("ttl", [0, -1, float("inf"), float("-inf"), float("nan"), True])
def test_store_rejects_invalid_ttl(ttl: float) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        IdempotencyStore(ttl_seconds=ttl)


def test_store_rejects_unrepresentable_expiry_value() -> None:
    with pytest.raises(ValueError, match="finite positive"):
        IdempotencyStore(ttl_seconds=10**10000)


@pytest.mark.parametrize("capacity", [0, -1, True, 1.5])
def test_store_rejects_invalid_capacity(capacity: int) -> None:
    error = TypeError if isinstance(capacity, float) or isinstance(capacity, bool) else ValueError
    with pytest.raises(error):
        IdempotencyStore(max_items=capacity)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("task_id", "intent_hash"),
    [("", "i"), ("t", ""), ("   ", "i"), ("t", "  ")],
)
def test_make_key_rejects_blank_identity_parts(task_id: str, intent_hash: str) -> None:
    with pytest.raises(ValueError):
        IdempotencyStore.make_key(task_id, intent_hash)


def test_key_encoding_does_not_have_delimiter_collisions() -> None:
    left = IdempotencyStore.make_key("a:b", "c")
    right = IdempotencyStore.make_key("a", "b:c")
    assert left != right


def test_ttl_expiration_is_enforced_and_expired_entries_are_pruned(monkeypatch) -> None:
    import forge_upgrade.persistence.idempotency as module

    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    store = IdempotencyStore(ttl_seconds=5, max_items=2)
    store.remember("expired", "response")

    clock[0] = 104.99
    assert store.seen("expired")
    clock[0] = 105.0
    assert not store.seen("expired")
    assert store.get("expired") is None
    assert store._items == {}


def test_inflight_claim_does_not_expire_with_completed_result_ttl(monkeypatch) -> None:
    import forge_upgrade.persistence.idempotency as module

    clock = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    store = IdempotencyStore(ttl_seconds=5, max_items=1)
    assert store.try_claim("long-operation")

    clock[0] = 10_000.0
    assert store.seen("long-operation")
    assert store.get("long-operation").status == "in_flight"  # type: ignore[union-attr]
    with pytest.raises(IdempotencyCapacityError, match="in-flight"):
        store.try_claim("duplicate-operation")


def test_update_existing_full_store_does_not_evict_an_unrelated_record() -> None:
    store = IdempotencyStore(max_items=2)
    store.remember("first", "old-response")
    store.remember("second", "second-response")

    store.remember("first", "new-response")

    assert store.get("first").response_hash == "new-response"  # type: ignore[union-attr]
    assert store.get("second").response_hash == "second-response"  # type: ignore[union-attr]
    assert len(store._items) == 2


def test_new_completed_record_evicts_oldest_completed_record_only() -> None:
    store = IdempotencyStore(max_items=2)
    assert store.try_claim("inflight")
    store.remember("completed", "response")
    store.remember("new", "new-response")

    assert store.get("inflight") is not None
    assert store.get("new") is not None
    assert store.get("completed") is None


def test_store_does_not_evict_inflight_claims_when_at_capacity() -> None:
    store = IdempotencyStore(max_items=1)
    assert store.try_claim("active")

    with pytest.raises(IdempotencyCapacityError, match="in-flight"):
        store.remember("other", "response")

    assert store.get("active") is not None
    assert store.get("active").status == "in_flight"  # type: ignore[union-attr]


def test_claim_complete_duplicate_and_release_lifecycle() -> None:
    store = IdempotencyStore(max_items=2)

    assert store.try_claim("request-1")
    assert not store.try_claim("request-1")
    pending = store.get("request-1")
    assert pending is not None
    assert pending.status == "in_flight"
    assert pending.response_hash is None

    store.remember("request-1", "result-hash")
    completed = store.get("request-1")
    assert completed is not None
    assert completed.status == "completed"
    assert completed.response_hash == "result-hash"
    assert not store.release("request-1")

    assert store.try_claim("failed-request")
    assert store.release("failed-request")
    assert store.get("failed-request") is None
    assert store.try_claim("failed-request")


def test_concurrent_claims_admit_only_one_owner() -> None:
    store = IdempotencyStore(max_items=100)
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda _: store.try_claim("one-operation"), range(100)))

    assert sum(results) == 1
    assert store.get("one-operation").status == "in_flight"  # type: ignore[union-attr]


def test_bad_keys_and_response_hashes_are_rejected() -> None:
    store = IdempotencyStore()
    with pytest.raises(ValueError, match="key must not be empty"):
        store.try_claim(" ")
    with pytest.raises(ValueError, match="response_hash must not be empty"):
        store.remember("valid-key", "")
