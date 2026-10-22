from forge_upgrade.models import PlanGraph, PlanNode, TaskPhase
from forge_upgrade.plan_guard import PlanGuard


def build_graph(nodes: dict[str, PlanNode]) -> PlanGraph:
    return PlanGraph("g", nodes)


def test_missing_test_review():
    graph = build_graph(
        {"impl": PlanNode("impl", "impl", "", TaskPhase.IMPLEMENT)}
    )
    result = PlanGuard().validate(graph)
    assert not result.passed
    assert "plan missing TEST phase" in result.errors
    assert "plan missing REVIEW phase" in result.errors


def test_linear_plan_requires_test_and_review_ancestors_before_delivery():
    graph = build_graph(
        {
            "plan": PlanNode("plan", "plan", "", TaskPhase.PLAN),
            "impl": PlanNode("impl", "impl", "", TaskPhase.IMPLEMENT, ("plan",)),
            "test": PlanNode("test", "test", "", TaskPhase.TEST, ("impl",)),
            "review": PlanNode("review", "review", "", TaskPhase.REVIEW, ("test",)),
            "deliver": PlanNode("deliver", "deliver", "", TaskPhase.DELIVER, ("review",)),
        }
    )

    result = PlanGuard().validate(graph)

    assert result.passed, result.errors


def test_disconnected_test_and_review_nodes_do_not_satisfy_delivery_gate():
    graph = build_graph(
        {
            "impl": PlanNode("impl", "impl", "", TaskPhase.IMPLEMENT),
            "test": PlanNode("test", "test", "", TaskPhase.TEST),
            "review": PlanNode("review", "review", "", TaskPhase.REVIEW),
            "deliver": PlanNode("deliver", "deliver", "", TaskPhase.DELIVER, ("impl",)),
        }
    )

    result = PlanGuard().validate(graph)

    assert not result.passed
    assert any("directly depends on unverified implement node 'impl'" in e for e in result.errors)
    assert any("does not depend on a review gate" in e for e in result.errors)
    assert any("does not depend on a test gate" in e for e in result.errors)


def test_delivery_cannot_keep_a_direct_implementation_dependency_even_with_gates():
    graph = build_graph(
        {
            "impl": PlanNode("impl", "impl", "", TaskPhase.IMPLEMENT),
            "test": PlanNode("test", "test", "", TaskPhase.TEST, ("impl",)),
            "review": PlanNode("review", "review", "", TaskPhase.REVIEW, ("test",)),
            "deliver": PlanNode(
                "deliver", "deliver", "", TaskPhase.DELIVER, ("review", "impl")
            ),
        }
    )

    result = PlanGuard().validate(graph)

    assert not result.passed
    assert any("directly depends on unverified implement node 'impl'" in e for e in result.errors)
