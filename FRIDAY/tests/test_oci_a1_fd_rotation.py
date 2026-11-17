"""Fault-domain rotation tests for the continuous OCI A1 allocator.

Production observation (2026-11-17): the shared tenancy throttle bucket
lets roughly two launch attempts through per cycle — the first is answered
"Out of host capacity", the second aborts the cycle with 429
TooManyRequests. With a fixed candidate order the allocator therefore only
ever probed the first two candidates and never reached FAULT-DOMAIN-2/3.
These tests pin the rotation fix and the unchanged cadence/budget contract.
"""
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.oci_a1_common import rotate_candidates
from scripts.oci_a1_continuous import (
    AUTH_OR_CONFIG_ERROR_SECONDS,
    NO_CAPACITY_SECONDS,
    PENDING_INSTANCE_SECONDS,
    RATE_LIMIT_SECONDS,
    TRANSIENT_ERROR_SECONDS,
    ContinuousAllocator,
    load_candidate_cursor,
    persist_candidate_cursor,
    persist_state,
)

ALL_DOMAINS = [None, "FAULT-DOMAIN-1", "FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]


class FakeOciError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _capacity_error():
    return FakeOciError(503, "ServiceError", "Out of host capacity.")


def _throttle_error():
    return FakeOciError(429, "TooManyRequests", "Too many requests.")


def _conflict_capacity_error():
    return FakeOciError(409, "OutOfHostCapacity", "Out of host capacity.")


def _model(**kwargs):
    return SimpleNamespace(**kwargs)


def _fake_oci(report_entries):
    models = SimpleNamespace(
        CreateComputeCapacityReportDetails=_model,
        CreateCapacityReportShapeAvailabilityDetails=_model,
        CapacityReportInstanceShapeConfig=_model,
        LaunchInstanceDetails=_model,
        LaunchInstanceShapeConfigDetails=_model,
        InstanceSourceViaImageDetails=_model,
        CreateVnicDetails=_model,
    )

    def paginate(call, **kwargs):
        return SimpleNamespace(data=call(**kwargs))

    oci = SimpleNamespace(
        pagination=SimpleNamespace(list_call_get_all_results=paginate),
        core=SimpleNamespace(models=models),
    )
    compute = SimpleNamespace(
        list_instances=lambda **_: [],
        get_image=lambda *_a, **_k: SimpleNamespace(
            data=SimpleNamespace(lifecycle_state="AVAILABLE")
        ),
        create_compute_capacity_report=lambda *_a, **_k: SimpleNamespace(
            data=SimpleNamespace(shape_availabilities=report_entries)
        ),
    )
    network = SimpleNamespace(
        get_subnet=lambda *_a, **_k: SimpleNamespace(
            data=SimpleNamespace(lifecycle_state="AVAILABLE")
        )
    )
    signer = SimpleNamespace(tenancy_id="ocid1.tenancy.test")
    return oci, signer, compute, network


def _no_capacity_report():
    from scripts.oci_a1_common import SHAPE, TARGET_MEMORY_GB, TARGET_OCPUS

    return [
        _model(
            availability_status="OUT_OF_HOST_CAPACITY",
            available_count=0,
            fault_domain="FAULT-DOMAIN-1",
            instance_shape=SHAPE,
            instance_shape_config=_model(
                ocpus=TARGET_OCPUS, memory_in_gbs=TARGET_MEMORY_GB
            ),
        )
    ]


def _available_report(domains):
    from scripts.oci_a1_common import SHAPE, TARGET_MEMORY_GB, TARGET_OCPUS

    return [
        _model(
            availability_status="AVAILABLE",
            available_count=1,
            fault_domain=domain,
            instance_shape=SHAPE,
            instance_shape_config=_model(
                ocpus=TARGET_OCPUS, memory_in_gbs=TARGET_MEMORY_GB
            ),
        )
        for domain in domains
    ]


class ThrottledLauncher:
    """Launch stub: 1st call of each cycle -> capacity, 2nd -> 429.

    Mirrors the observed production regime. After a 429 the next call is a
    new cycle, so call parity identifies the position within the cycle.
    """

    def __init__(self, capacity_exc):
        self.capacity_exc = capacity_exc
        self.attempted = []

    def __call__(self, details, **_kwargs):
        self.attempted.append(getattr(details, "fault_domain", None))
        if len(self.attempted) % 2 == 1:
            raise self.capacity_exc()
        raise _throttle_error()


# --- rotate_candidates (pure helper) -------------------------------------


def test_rotate_candidates_identity_wrap_and_copy_semantics():
    items = ["a", "b", "c", "d"]
    assert rotate_candidates(items, 0) == items
    assert rotate_candidates(items, 1) == ["b", "c", "d", "a"]
    assert rotate_candidates(items, 2) == ["c", "d", "a", "b"]
    assert rotate_candidates(items, 6) == ["c", "d", "a", "b"]  # start mod len
    assert items == ["a", "b", "c", "d"]  # input not mutated
    assert rotate_candidates([], 3) == []
    assert rotate_candidates(["x"], 5) == ["x"]


# --- cursor persistence ---------------------------------------------------


def test_cursor_persists_and_reloads(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    assert load_candidate_cursor() == 0
    persist_candidate_cursor(3)
    assert load_candidate_cursor() == 3
    state = json.loads((Path(tmp_path) / "state.json").read_text())
    assert state["candidate_cursor"] == 3


def test_cursor_load_tolerates_corrupt_state(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    (Path(tmp_path) / "state.json").write_text("{not json", encoding="utf-8")
    assert load_candidate_cursor() == 0


def test_persist_state_carries_cursor_over_outcome_writes(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    persist_candidate_cursor(2)
    persist_state("retrying_after_error", {"http_status": 429})
    state = json.loads((Path(tmp_path) / "state.json").read_text())
    assert state["outcome"] == "retrying_after_error"
    assert state["candidate_cursor"] == 2


# --- cadence / budget contract (unchanged by the fix) ---------------------


def test_cadence_constants_unchanged():
    assert NO_CAPACITY_SECONDS == 60
    assert PENDING_INSTANCE_SECONDS == 20
    assert TRANSIENT_ERROR_SECONDS == 120
    assert RATE_LIMIT_SECONDS == 180
    assert AUTH_OR_CONFIG_ERROR_SECONDS == 300


# --- the headline simulation: fallback loop (no-capacity report) ----------


def test_throttled_cycles_rotate_across_all_fault_domains(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    oci, signer, compute, network = _fake_oci(_no_capacity_report())
    launcher = ThrottledLauncher(_capacity_error)
    compute.launch_instance = launcher
    allocator = ContinuousAllocator(
        oci_module=oci, signer=signer, compute=compute, network=network
    )

    cycles = []
    for _ in range(4):
        before = len(launcher.attempted)
        result = allocator.attempt_once()
        cycles.append(launcher.attempted[before:])
        # Throttle abort keeps the exact pre-fix cadence and outcome.
        assert result.outcome == "retrying_after_error"
        assert result.delay_seconds == RATE_LIMIT_SECONDS
        # Per-cycle attempt budget unchanged: never more than the 4
        # candidates, and the throttle still cuts the cycle at 2.
        assert len(cycles[-1]) == 2

    assert cycles[0] == [None, "FAULT-DOMAIN-1"]  # pre-fix behaviour, cycle 1
    assert cycles[1] == ["FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]  # newly reached
    assert cycles[2] == [None, "FAULT-DOMAIN-1"]
    assert cycles[3] == ["FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]
    # Every fault domain is probed within any 2 consecutive cycles.
    assert set(cycles[0] + cycles[1]) == set(ALL_DOMAINS)
    # Cursor advanced by exactly the attempts made: (0 + 4*2) % 4 == 0,
    # and it survived the outcome persist_state writes.
    state = json.loads((Path(tmp_path) / "state.json").read_text())
    assert state["candidate_cursor"] == 0
    assert state["outcome"] == "retrying_after_error"


def test_cursor_survives_allocator_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    oci, signer, compute, network = _fake_oci(_no_capacity_report())
    launcher = ThrottledLauncher(_capacity_error)
    compute.launch_instance = launcher
    first = ContinuousAllocator(
        oci_module=oci, signer=signer, compute=compute, network=network
    )
    first.attempt_once()
    assert first.candidate_cursor == 2

    # A restarted process (new allocator, same state directory) resumes
    # at the first untried candidate instead of resetting to index 0.
    oci2, signer2, compute2, network2 = _fake_oci(_no_capacity_report())
    launcher2 = ThrottledLauncher(_capacity_error)
    compute2.launch_instance = launcher2
    restarted = ContinuousAllocator(
        oci_module=oci2, signer=signer2, compute=compute2, network=network2
    )
    assert restarted.candidate_cursor == 2
    restarted.attempt_once()
    assert launcher2.attempted == ["FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]


def test_full_no_capacity_cycle_advances_cursor_by_full_turn(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    oci, signer, compute, network = _fake_oci(_no_capacity_report())
    attempted = []

    def always_capacity(details, **_kwargs):
        attempted.append(getattr(details, "fault_domain", None))
        raise _capacity_error()

    compute.launch_instance = always_capacity
    allocator = ContinuousAllocator(
        oci_module=oci, signer=signer, compute=compute, network=network
    )
    result = allocator.attempt_once()
    assert result.outcome == "no_capacity"
    assert result.delay_seconds == NO_CAPACITY_SECONDS
    assert attempted == ALL_DOMAINS  # all 4 tried, as pre-fix
    assert allocator.candidate_cursor == 0  # advanced by 4 == full turn


# --- rotation also applies to the capacity-report candidates loop ---------


def test_report_candidates_rotate_under_throttle(tmp_path, monkeypatch):
    monkeypatch.setenv("STATE_DIRECTORY", str(tmp_path))
    domains = ["FAULT-DOMAIN-1", "FAULT-DOMAIN-2", "FAULT-DOMAIN-3"]
    oci, signer, compute, network = _fake_oci(_available_report(domains))
    launcher = ThrottledLauncher(_conflict_capacity_error)
    compute.launch_instance = launcher
    allocator = ContinuousAllocator(
        oci_module=oci, signer=signer, compute=compute, network=network
    )

    first = allocator.attempt_once()
    second = allocator.attempt_once()
    assert first.outcome == second.outcome == "retrying_after_error"
    assert first.delay_seconds == second.delay_seconds == RATE_LIMIT_SECONDS
    assert launcher.attempted[:2] == ["FAULT-DOMAIN-1", "FAULT-DOMAIN-2"]
    # Cycle 2 resumes at the untried candidate, then wraps around.
    assert launcher.attempted[2:] == ["FAULT-DOMAIN-3", "FAULT-DOMAIN-1"]
    assert set(launcher.attempted) == set(domains)
