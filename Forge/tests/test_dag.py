import pytest

from forge_upgrade.dag import DagScheduler
from forge_upgrade.models import NodeStatus, PlanGraph, PlanNode, TaskPhase


def graph():
    nodes = {
        "plan": PlanNode("plan", "plan", "", TaskPhase.PLAN),
        "impl": PlanNode("impl", "impl", "", TaskPhase.IMPLEMENT, ("plan",)),
        "test": PlanNode("test", "test", "", TaskPhase.TEST, ("impl",)),
        "review": PlanNode("review", "review", "", TaskPhase.REVIEW, ("test",)),
    }
    return PlanGraph("g", nodes)


def test_ready_waves():
    scheduler = DagScheduler(graph())
    scheduler.validate()
    assert [node.node_id for node in scheduler.ready()] == ["plan"]
    scheduler.mark_running("plan")
    scheduler.mark_passed("plan")

    assert [node.node_id for node in scheduler.ready()] == ["impl"]
    scheduler.mark_running("impl")
    scheduler.mark_passed("impl")
    assert [node.node_id for node in scheduler.ready()] == ["test"]


def test_pending_prerequisite_cannot_be_started_or_passed():
    scheduler = DagScheduler(graph())

    with pytest.raises(ValueError, match="cannot start"):
        scheduler.mark_running("impl")
    with pytest.raises(ValueError, match="only a running node can pass"):
        scheduler.mark_passed("plan")


def test_node_cannot_be_started_twice_without_becoming_ready_again():
    scheduler = DagScheduler(graph())
    scheduler.ready()
    scheduler.mark_running("plan")

    with pytest.raises(ValueError, match="cannot start"):
        scheduler.mark_running("plan")
    assert scheduler.runtime["plan"].attempts == 1


def test_failure_blocks_all_transitive_descendants():
    scheduler = DagScheduler(graph())
    scheduler.ready()
    scheduler.mark_running("plan")
    scheduler.mark_failed("plan", "synthetic test failure")

    assert scheduler.failed()
    assert not scheduler.complete()
    assert scheduler.runtime["plan"].status == NodeStatus.FAILED
    assert scheduler.runtime["impl"].status == NodeStatus.BLOCKED
    assert scheduler.runtime["test"].status == NodeStatus.BLOCKED
    assert scheduler.runtime["review"].status == NodeStatus.BLOCKED
    assert scheduler.blocking_nodes() == ["impl", "test", "review"]
    assert scheduler.progress() == 1.0


def test_empty_graph_is_complete_with_full_progress():
    scheduler = DagScheduler(PlanGraph("empty", {}))

    assert scheduler.complete()
    assert not scheduler.failed()
    assert scheduler.progress() == 1.0


def test_validation_catches_mapping_key_that_disagrees_with_node_id():
    invalid = PlanGraph(
        "bad",
        {"other-key": PlanNode("node-id", "node", "", TaskPhase.PLAN)},
    )
    with pytest.raises(ValueError, match="node key mismatch"):
        DagScheduler(invalid).validate()
