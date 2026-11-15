"""TASK-FRD-006: the reflex's peer escalation routes by declared capability.

TASK-COR-009 proved the production defect: FRIDAY's ReflexBrain, on a fault it
could not repair locally, broadcast the generic actions `memory_recall` and
`source_repair` to EVERY mesh peer. Cortex authenticated FRIDAY successfully
and correctly 403'd both at its property-scope gate — neither is a website
operation — roughly two avoidable 403s per unrepaired fault episode, for
months. Cortex was behaving correctly; the caller was the defect.

The routing contract pinned here:

* `memory_recall` is addressed only to peers whose contract declares it —
  today Memora, the fleet's memory, alone.
* Any other generic action (e.g. `source_repair`) goes only to peers whose
  contract declares it. Today no peer declares `source_repair`, so the work
  request is not sent anywhere: the fault stays local and surfaces as
  unrepaired, honestly, instead of being sprayed at peers that cannot serve it.
* A peer that DOES declare an action still receives it, and a verified
  receipt from that peer still completes the escalation.

The harness is the mesh's own contract transport, so the assertions below are
about envelopes on the wire: which peer each envelope was addressed to, and
which action it carried.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from friday.cognition.assistance import AssistanceBroker
from friday.cognition.mesh import ContractTransport, HarnessBehaviour, Mesh, build_contracts
from friday.cognition.reflex import (
    Incident,
    IncidentKind,
    IncidentSeverity,
    OutcomeStatus,
    ReflexBrain,
)

NON_MEMORY_PEERS = (
    "cortex",
    "forge",
    "futuris",
    "inference",
    "intelx",
    "sentinel",
    "stratex",
    "vyralx",
)


def _mesh(
    *, declare: dict[str, tuple[str, ...]] | None = None, request_timeout: float = 30.0
) -> tuple[Mesh, ContractTransport]:
    contracts = build_contracts()
    for contract in contracts.values():
        contract.api_key = contract.api_key or "peer-key"
    for peer, actions in (declare or {}).items():
        contracts[peer].declared_actions = actions
    mesh, harness = Mesh.in_process(
        contracts, backoff_seconds=0.0, attempts=1, request_timeout=request_timeout
    )
    return mesh, harness


def _envelopes(harness: ContractTransport, *, action: str | None = None) -> list[dict]:
    bodies = [call.json_body or {} for call in harness.calls]
    if action is not None:
        bodies = [body for body in bodies if body.get("action") == action]
    return bodies


def _incident() -> Incident:
    return Incident(
        kind=IncidentKind.TEST_FAILURE,
        severity=IncidentSeverity.HIGH,
        source="tests/test_calc.py::test_add",
        summary="NameError: name 'totl' is not defined",
        evidence={
            "test_node_id": "tests/test_calc.py::test_add",
            "source_file": "src/friday/calc.py",
        },
    )


# ── the declaration table itself ─────────────────────────────────────────────


def test_only_memora_declares_memory_recall_and_nobody_declares_source_repair() -> None:
    contracts = build_contracts()
    assert contracts["memora"].supports("memory_recall")
    assert all(
        not contract.supports("memory_recall")
        for name, contract in contracts.items()
        if name != "memora"
    )
    # No peer's code serves a fleet-generic `source_repair` today (Forge's
    # delegate would treat it as an unrelated build goal in its own
    # workspaces; Cortex's scope gate rejects it). Declaring it for anyone
    # would manufacture a capability that does not exist.
    assert all(not contract.supports("source_repair") for contract in contracts.values())


def test_peers_that_support_reads_the_contracts() -> None:
    mesh, _harness = _mesh()
    broker = AssistanceBroker(mesh=mesh)
    assert broker.peers_that_support("memory_recall") == ("memora",)
    assert broker.peers_that_support("source_repair") == ()


# ── recall routing ───────────────────────────────────────────────────────────


def test_recall_is_addressed_to_memora_alone() -> None:
    mesh, harness = _mesh()
    harness.behave(
        "memora",
        HarnessBehaviour(
            result={
                "memories": [
                    {
                        "capability": "source_repair",
                        "answer": "the same NameError was fixed by adding the missing import",
                        "verified": True,
                    }
                ]
            }
        ),
    )

    recalled = asyncio.run(
        AssistanceBroker(mesh=mesh).recall_from_peers(
            "source_repair", question="NameError in src/friday/calc.py"
        )
    )

    assert recalled["asked"] == ["memora"], recalled
    assert recalled["answered_by"] == ["memora"]
    assert recalled["memories"][0]["peer"] == "memora"
    # Every other peer is accounted for as skipped, with the reason.
    assert set(recalled["skipped"]) == set(NON_MEMORY_PEERS), recalled["skipped"]
    assert all("does not declare" in reason for reason in recalled["skipped"].values())
    # And on the wire: exactly one envelope, to Memora, carrying memory_recall.
    calls = _envelopes(harness)
    assert len(calls) == 1, calls
    assert calls[0]["target_agent"] == "memora"
    assert calls[0]["action"] == "memory_recall"
    assert all(call["target_agent"] != "cortex" for call in calls)


def test_recall_named_peers_are_still_filtered_by_declaration() -> None:
    """Naming a peer does not override its contract."""
    mesh, harness = _mesh()

    recalled = asyncio.run(
        AssistanceBroker(mesh=mesh).recall_from_peers(
            "source_repair", peers=("cortex", "forge")
        )
    )

    assert recalled["asked"] == []
    assert set(recalled["skipped"]) == {"cortex", "forge"}
    assert "declares 'memory_recall'" in recalled["reason"]
    assert harness.calls == [], "an envelope left for a peer that does not declare the action"


# ── work-request routing ─────────────────────────────────────────────────────


def test_source_repair_is_not_sent_anywhere_when_no_peer_declares_it() -> None:
    mesh, harness = _mesh()

    asked = asyncio.run(
        AssistanceBroker(mesh=mesh).request_help_from_peers(
            caller="friday",
            capability="source_repair",
            objective="repair the failing test",
        )
    )

    assert asked["asked"] == []
    assert asked["performed"] is False
    assert asked["completed_by"] is None
    assert "no peer declares 'source_repair'" in asked["reason"]
    assert set(asked["skipped"]) == set(build_contracts())
    assert harness.calls == [], "the unrepaired fault was broadcast anyway"


def test_a_peer_that_declares_the_action_still_receives_it_and_can_complete_it() -> None:
    mesh, harness = _mesh(declare={"forge": ("source_repair",)})

    asked = asyncio.run(
        AssistanceBroker(mesh=mesh).request_help_from_peers(
            caller="friday",
            capability="source_repair",
            objective="repair the failing test",
        )
    )

    assert asked["asked"] == ["forge"], asked
    assert asked["performed"] is True
    assert asked["completed_by"] == "forge"
    assert "cortex" in asked["skipped"]
    calls = _envelopes(harness)
    assert len(calls) == 1, calls
    assert calls[0]["target_agent"] == "forge"
    assert calls[0]["action"] == "source_repair"


# ── the reflex, end to end ───────────────────────────────────────────────────


def test_a_fault_episode_emits_no_envelopes_to_cortex(tmp_path: Path) -> None:
    """The production signature, inverted: with the fleet's real contracts, an
    unrepaired fault produces exactly one envelope — memory_recall to Memora —
    and no source_repair envelope to anyone."""
    mesh, harness = _mesh()
    brain = ReflexBrain(tmp_path, mesh=mesh, enabled=True)

    outcome = asyncio.run(brain.handle(_incident()))

    assert outcome.status is OutcomeStatus.NO_FIX_KNOWN, outcome.detail
    assert outcome.action == "synthesise_patch"
    calls = _envelopes(harness)
    assert len(calls) == 1, calls
    assert calls[0]["target_agent"] == "memora"
    assert calls[0]["action"] == "memory_recall"
    assert _envelopes(harness, action="source_repair") == []
    assert all(call["target_agent"] != "cortex" for call in calls)
    # The outcome says why the work went nowhere, instead of claiming peers
    # were asked.
    escalation = outcome.evidence["peer_escalation"]
    assert escalation["asked"] == []
    assert escalation["performed"] is False
    assert "no peer declares 'source_repair'" in escalation["reason"]
    assert "No peer was asked to do the work" in outcome.detail, outcome.detail
    assert "were then asked" not in outcome.detail, outcome.detail


def test_the_escalation_still_completes_through_a_declaring_peer(tmp_path: Path) -> None:
    """Routing narrows the audience; it does not remove the ladder. Memora
    remembers the fault, Forge declares the work, Forge's verified receipt
    completes it — and no other peer receives either envelope."""
    mesh, harness = _mesh(declare={"forge": ("source_repair",)})
    harness.behave(
        "memora",
        HarnessBehaviour(
            result={
                "memories": [
                    {
                        "capability": "source_repair",
                        "answer": "the missing name was a one-character typo; the fix committed",
                        "verified": True,
                    }
                ]
            }
        ),
    )
    brain = ReflexBrain(tmp_path, mesh=mesh, enabled=True)

    outcome = asyncio.run(brain.handle(_incident()))

    assert outcome.status is OutcomeStatus.RESOLVED, outcome.detail
    assert outcome.action == "delegated_to_peer"
    delegation = outcome.evidence["delegation"]
    assert delegation["asked"] == ["forge"], delegation
    assert delegation["completed_by"] == "forge"
    assert outcome.evidence["fleet_recall"]["memories"][0]["peer"] == "memora"
    calls = _envelopes(harness)
    assert {(call["target_agent"], call["action"]) for call in calls} == {
        ("memora", "memory_recall"),
        ("forge", "source_repair"),
    }, calls


def test_a_remembering_peer_that_also_declares_the_work_is_asked_directly(
    tmp_path: Path,
) -> None:
    """Memory still aims the request when the rememberer can do the work."""
    mesh, harness = _mesh(declare={"memora": ("memory_recall", "source_repair")})
    harness.behave(
        "memora",
        HarnessBehaviour(
            result={
                "memories": [
                    {
                        "capability": "source_repair",
                        "answer": "the missing name was a one-character typo; the fix committed",
                        "verified": True,
                    }
                ]
            }
        ),
        action="memory_recall",
    )
    brain = ReflexBrain(tmp_path, mesh=mesh, enabled=True)

    outcome = asyncio.run(brain.handle(_incident()))

    assert outcome.status is OutcomeStatus.RESOLVED, outcome.detail
    delegation = outcome.evidence["delegation"]
    assert delegation["asked"] == ["memora"], delegation
    assert delegation["completed_by"] == "memora"
    assert outcome.evidence["targeted_by_memory"] is True
    assert "memory held a fix" in outcome.detail, outcome.detail
