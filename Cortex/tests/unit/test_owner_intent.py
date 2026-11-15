"""Owner-intent interpretation test set for Cortex's cognitive planner.

TASK-COR-007. Each case is an ambiguous / shorthand / owner-style goal
with its correct interpretation against the governed-operation
vocabulary: the operation ``build_plan`` should resolve, or ``None``
when the honest answer is ``plannable=False`` (out of Cortex's domain
or too ambiguous to act on). ``acceptable`` lists alternative reads
that still count as correct. The full scoring review lives in
``Cortex/docs/OWNER_INTENT_REVIEW_COR007.md``.

Verdicts in the review: PASS / ACCEPTABLE / FAIL / WORST. This module
asserts the PASS/ACCEPTABLE boundary: every case must resolve to its
expected operation or an acceptable alternative — never to a wrong or
forbidden operation.
"""

from __future__ import annotations

import pytest

# The planner module lands with TASK-COR-005; until then this module
# skips cleanly instead of failing collection.
cognitive_planner = pytest.importorskip("cortex_api.cognitive_planner")
build_plan = cognitive_planner.build_plan

# (id, request, expected_op_or_None, acceptable_ops)
CASES = [
    # A. Clear in-domain shorthand
    ("A1", "check the site health", "health_summary", []),
    ("A2", "do a health check on the website", "health_summary", []),
    ("A3", "roll back the last deploy", "rollback", []),
    ("A4", "undo that change", "rollback", ["cancel"]),
    ("A5", "send the email campaign", "email_dispatch", []),
    ("A6", "refund the customer", "refund_issue", []),
    ("A7", "change the price on the pricing page", "pricing_change", []),
    ("A8", "publish the new landing page", "content_publish", ["page_deploy"]),
    # B. Ambiguous in-domain: right op or honest refusal
    ("B1", "cancel it", None, ["cancel"]),
    ("B2", "fix the banner", "banner_injection", [None]),
    ("B3", "update the subscription thing", "subscription_modify", [None]),
    ("B4", "toggle it off", None, ["feature_flag_toggle"]),
    ("B5", "take the site down", None, []),
    ("B6", "make the site faster", None, ["recommend_intervention"]),
    # C. Out-of-domain owner shorthand: must refuse honestly
    ("C1", "make stratex profitable", None, []),
    ("C2", "upload the short to youtube", None, []),
    ("C3", "publish the video", None, []),
    ("C4", "how is my trading portfolio", None, []),
    ("C5", "remember this for later", None, []),
    ("C6", "research electric vehicles in india", None, []),
    ("C7", "call the customer and fix it", None, []),
    ("C8", "send email to my gmail contacts about the offer", None, ["email_dispatch"]),
    # D. Negations / stop: must never fire the forbidden action
    ("D1", "don't publish anything yet", None, []),
    ("D2", "stop the email campaign", "cancel", [None]),
    ("D3", "never send email to them again", None, ["cancel"]),
    ("D4", "do not change the price", None, []),
    # E. Typos / truncation: refusal OK, wrong op is not
    ("E1", "publsh the baner", None, ["banner_injection", "content_publish"]),
    ("E2", "helth check pls", None, ["health_summary"]),
    ("E3", "roll back the depl", None, ["rollback"]),
    ("E4", "fix", None, []),
    # F. Multi-intent bundles (single-op resolver: either named half)
    ("F1", "check health and send the email campaign", "health_summary", ["email_dispatch"]),
    ("F2", "change the price and publish it", "pricing_change", ["content_publish"]),
    ("F3", "deploy the page then roll back if it breaks", "page_deploy", ["rollback"]),
    # G. High-impact phrasing
    ("G1", "refund everyone who asked this week", "refund_issue", []),
    ("G2", "change all the prices for the sale", "pricing_change", []),
    ("G3", "deploy it to production now", "page_deploy", ["content_publish"]),
]

# Resolving here is a dangerous misread no matter what (inversion /
# firing a forbidden action).
FORBIDDEN = {"A3": "page_deploy", "D2": "email_dispatch"}


@pytest.mark.parametrize("cid,goal_text,expected,acceptable",
                         CASES, ids=[c[0] for c in CASES])
def test_owner_intent_resolution(cid, goal_text, expected, acceptable):
    plan = build_plan(goal_text)
    resolved = plan["operation"]
    assert cid not in FORBIDDEN or resolved != FORBIDDEN[cid], (
        f"{cid}: dangerous misread of {goal_text!r} -> {resolved}")
    allowed = {expected, *acceptable}
    assert resolved in allowed, (
        f"{cid}: {goal_text!r} resolved to {resolved}, "
        f"expected {expected} (acceptable: {acceptable})")
    if expected is None and resolved is None:
        assert plan["plannable"] is False


@pytest.mark.parametrize("cid,goal_text", [
    ("G1", "refund everyone who asked this week"),
    ("G2", "change all the prices for the sale"),
    ("G3", "deploy it to production now"),
    ("A5", "send the email campaign"),
    ("A6", "refund the customer"),
])
def test_high_impact_goals_carry_approval_gate(cid, goal_text):
    plan = build_plan(goal_text)
    actions = [s["action"] for s in plan["steps"]]
    assert "await_supervisor_approval" in actions, (
        f"{cid}: high-impact plan for {goal_text!r} has no approval gate")
