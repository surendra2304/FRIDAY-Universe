"""TASK-COR-004 — Cortex routing-accuracy regression gate.

Labelled set of task/event descriptions with known correct target agents,
run through ``AgentRegistry.route_for_event`` — the routing the Orchestrator
uses for every cognitive loop (packages/core orchestrator.py).

Ground truth: the specialist agent whose declared domain + capabilities in
``packages/agents`` own the event class, consistent with the routing
conventions the pre-existing tests assert (pricing->growth, checkout->sales,
error.*->support, heartbeat->reliability, deal/invoice->revops, ...).

Measured history (TASK-COR-004, 2026-11-15):
  BEFORE the routing-signal fix: 57/103 = 55.3%
    - 39 of 46 misses fell through to the reliability default (whole event
      classes had no keyword: payments/billing, rate limits, cancellations,
      demo/intent signals, audit/KYC, complaints/refunds, signups...)
    - substring trap: "cro" fired inside cross_sell / microservice /
      microtransaction (3 misses)
    - rule-order steals: "score" took churn_score_computed from churn_risk;
      "lead" took lead_scoring and lead.qualified from qualification;
      "error" took error.payment_declined from revops (1 miss each class)
  AFTER the fix: 103/103 = 100% on this set, and all 14 pre-existing
  route_for_event assertions in the repo still pass (they are a subset of
  this set). Full report: Cortex/docs/ROUTING_ACCURACY_COR004.md.

Cases whose owner is genuinely debatable are NOT scored; they are listed in
AMBIGUOUS with the reason, so the gate never encodes a coin-flip as truth.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath("packages/agents/src"))
sys.path.insert(0, os.path.abspath("packages/core/src"))
sys.path.insert(0, os.path.abspath("packages/event_schema/src"))
sys.path.insert(0, os.path.abspath("packages/ai_universe_adapter/src"))
sys.path.insert(0, os.path.abspath("packages/tool_runtime/src"))
sys.path.insert(0, os.path.abspath("packages/integrations/src"))
sys.path.insert(0, os.path.abspath("packages/policy_engine/src"))
sys.path.insert(0, os.path.abspath("packages/workflow_engine/src"))
sys.path.insert(0, os.path.abspath("."))

from cortex_agents import AgentRegistry  # noqa: E402

CASES = [
    # compliance (tenant_audit_export / consent_enforce / data_mask_verify / pii_quarantine)
    ("privacy_consent_update", "compliance"),
    ("gdpr_erasure_request", "compliance"),
    ("pii_detected_in_payload", "compliance"),
    ("consent_revoked", "compliance"),
    ("compliance_policy_update", "compliance"),
    ("tenant_audit_export_requested", "compliance"),
    ("data_masking_verification", "compliance"),
    ("regulatory_audit_scheduled", "compliance"),
    ("kyc_verification_failed", "compliance"),
    # cro (A/B tests, variants, split tests)
    ("ab_test_variant_impression", "cro"),
    ("split_test_concluded", "cro"),
    ("experiment_promote_variant", "cro"),
    ("landing_page_variant", "cro"),
    ("cro_experiment_review", "cro"),
    ("cross_sell_experiment_review", "cro"),
    # revops (billing_reconcile / quote_generate; process() scans payment_failed, reads past_due)
    ("deal_contract_negotiation", "revops"),
    ("invoice_issued", "revops"),
    ("contract_renewal_due", "revops"),
    ("acv_expansion_opportunity", "revops"),
    ("deal_stage_stalled", "revops"),
    ("invoice_error_reported", "revops"),
    ("quote_generated", "revops"),
    ("billing_reconciliation_mismatch", "revops"),
    ("payment_failed", "revops"),
    ("error.payment_declined", "revops"),
    ("subscription_past_due", "revops"),
    ("payment_method.attached", "revops"),
    ("microtransaction_failed", "revops"),
    # mitigation (circuit_trip / traffic_throttle / rate_limit_mutate; reads sentinel_signals)
    ("ddos_attack_signature", "mitigation"),
    ("brute_force_login_attempt", "mitigation"),
    ("threat_level_elevated", "mitigation"),
    ("traffic_throttle_engaged", "mitigation"),
    ("anomaly_detection", "mitigation"),
    ("rate_limit_exceeded", "mitigation"),
    ("circuit_breaker_tripped", "mitigation"),
    ("bot_attack_detected", "mitigation"),
    ("credential_stuffing_attempt", "mitigation"),
    ("security.finding", "mitigation"),
    ("fraud_attempt_blocked", "mitigation"),
    # competitive (competitor intel, battlecards)
    ("competitor.datadog_comparison", "competitive"),
    ("competitor_pricing_change", "competitive"),
    ("battlecard_requested", "competitive"),
    ("intelx_market_report", "competitive"),
    ("competitor_feature_launch", "competitive"),
    ("win_loss_analysis", "competitive"),
    # qualification (lead scoring; process() treats demo/intent behaviour as its signals)
    ("qualify.lead", "qualification"),
    ("lead_scoring", "qualification"),
    ("intent_scoring", "qualification"),
    ("demo.requested", "qualification"),
    ("demo.viewed", "qualification"),
    ("demo_request_submitted", "qualification"),
    ("high_intent.detected", "qualification"),
    ("lead.qualified", "qualification"),
    ("mql_threshold_reached", "qualification"),
    ("prospect_fit_evaluated", "qualification"),
    # churn_risk (process() reads session decline + feature_usage_drop_pct)
    ("churn.risk_check", "churn_risk"),
    ("retention_campaign_launch", "churn_risk"),
    ("engagement_drop_detected", "churn_risk"),
    ("churn_score_computed", "churn_risk"),
    ("subscription_cancellation_requested", "churn_risk"),
    ("account_downgrade_completed", "churn_risk"),
    ("feature_usage_drop_alert", "churn_risk"),
    ("session_decline_detected", "churn_risk"),
    ("winback_campaign_sent", "churn_risk"),
    ("inactive_account_30d", "churn_risk"),
    # growth (experiment_mutate / banner_injection; pricing/funnel/acquisition/conversion)
    ("pricing.viewed", "growth"),
    ("pricing_view", "growth"),
    ("pricing.drop_off", "growth"),
    ("exit_intent_detected", "growth"),
    ("banner_campaign_published", "growth"),
    ("funnel_step_abandoned", "growth"),
    ("signup_completed", "growth"),
    ("conversion_completed", "growth"),
    ("campaign_attribution_updated", "growth"),
    ("seo_landing_optimized", "growth"),
    ("referral_program_launch", "growth"),
    # sales (checkout/leads/enterprise; email_dispatch + crm_tool)
    ("checkout.completed", "sales"),
    ("checkout.session.completed", "sales"),
    ("checkout_initiated", "sales"),
    ("lead_created", "sales"),
    ("enterprise.page_view", "sales"),
    ("sales_meeting_booked", "sales"),
    ("cross_sell_opportunity", "sales"),
    ("upsell_offer_accepted", "sales"),
    ("purchase_completed", "sales"),
    # support (errors/issues/help/tickets; ticketing_tool)
    ("error.500", "support"),
    ("error.network", "support"),
    ("error.database_timeout", "support"),
    ("server_error", "support"),
    ("support_ticket_opened", "support"),
    ("help_center_search_failed", "support"),
    ("password_reset_help", "support"),
    ("user_complaint_filed", "support"),
    ("refund_request_submitted", "support"),
    ("bug_report_filed", "support"),
    # reliability (health/latency/uptime; the default)
    ("heartbeat", "reliability"),
    ("latency_p99_breach", "reliability"),
    ("uptime_check_passed", "reliability"),
    ("memory_pressure_warning", "reliability"),
    ("deployment_completed", "reliability"),
    ("database_connection_pool_exhausted", "reliability"),
    ("incident.triggered", "reliability"),
    ("microservice_latency_alert", "reliability"),
]

# Genuinely debatable owners — documented, NOT scored.
AMBIGUOUS = [
    ("page_view", "no single owner; generic telemetry"),
    ("form_submit", "lead capture (sales) vs intent signal (qualification)"),
    ("checkout_error_reported", "error convention (support) vs checkout owner (sales)"),
    ("banner_error_shown", "error convention (support) vs banner owner (growth)"),
    ("microcopy_test_results", "CRO test the 'cro' substring routes correctly by accident"),
    ("pricing_page_repeat_visit", "growth by pricing convention; qualification consumes it as intent"),
]


@pytest.fixture(scope="module")
def registry():
    return AgentRegistry()


@pytest.mark.parametrize("event_type,expected", CASES, ids=[c[0] for c in CASES])
def test_route_for_event_accuracy(registry, event_type, expected):
    assert registry.route_for_event(event_type).domain == expected


def test_routing_accuracy_is_100_percent_on_labelled_set(registry):
    misses = [
        (event_type, expected, registry.route_for_event(event_type).domain)
        for event_type, expected in CASES
        if registry.route_for_event(event_type).domain != expected
    ]
    assert not misses, f"routing misses (event, expected, got): {misses}"
