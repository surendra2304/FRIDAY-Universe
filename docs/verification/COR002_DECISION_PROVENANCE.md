# TASK-COR-002 — Cortex decision provenance: audit + fix

Audit date: 2026-11-15. Claim: issue #35 comment 6890984834.
Branch: `claude/task-cor-002-decision-provenance` (base: main 337a1e3f, Merge PR #280).

## Audit base integrity

- Deployed Server 2 sha256 == fresh main for all four audited modules
  (decision_recommendation_system.py `3e4580de…`, recommendation_engine.py
  `d7a33120…`, enhanced_crm.py `6527c203…`, predictive_analytics.py `db0ea54d…`).
- Cortex.service active on Server 2, uvicorn :8009, 1 worker.

## Journal census (journalctl -u Cortex.service, 2026-11-08 → 2026-11-15, 8,175 lines)

Decision-surface traffic in the whole window was ALL crew probes from 127.0.0.1;
zero organic decision, recommendation, lead or analytics calls.

- POST /api/v1/cortex/decision/alternatives/{id}/score — 8 requests, **8× HTTP 500**
  (KeyError: 'criterion_id').
- POST /api/v1/cortex/decision/recommend — 1× 500 (same class), 1× 200.
- GET /api/v1/cortex/decision/report — 2× 200.
- /api/v1/recommendations/*, /api/v1/leads/*, /api/v1/crm/*, /api/v1/analytics/* —
  **zero requests** in the window.

## Controlled live probes (2026-11-15 ~12:58–13:02 IST, inputs tagged cor002-*)

Auth: X-Friday-Api-Key (decision routes) and a server-minted HS256 JWT (role-gated
routes). Secrets were used in-shell on the server and never printed.

| # | Output | Result | Traceable? |
|---|--------|--------|------------|
| 1 | decision/recommend, 2 criteria × 2 alternatives, only 1 of 4 score cells supplied (A/cost=0.2) | 200, best=A, confidence **0.5833**, rationale "highest weighted score (0.70)" | **NO** — 3 of 4 cells silently defaulted to 0.5 (`criteria_scores.get(crit_id, 0.5)`); confidence = best_score/Σscores (a share, not a probability); no inputs/timestamp/basis in output |
| 2 | decision/report | 200, aggregates #1 | NO — inherits #1, no provenance |
| 3 | recommendations?strategy=collaborative (u1: 1 item; u2: 2 items, 1 shared) | 200, confidence **0.7071** | NO — confidence is the cosine overlap 1/√(1·2) from ONE shared item; no basis |
| 4 | recommendations?strategy=hybrid (**the default**) | **500** for any user with a profile | NO OUTPUT — `hybrid_recommend` calls `content_filter(user_id, top_k * 2)`; content_filter's 2nd positional parameter is `all_items` → AttributeError on an int. Reproduced locally with the exact probe sequence |
| 5 | recommendations for never-seen user | 200, empty list | NO — indistinguishable from no-data; no data_status |
| 6 | POST /leads/score (minimal AND full payloads) | **500 on every call** | NO OUTPUT — route persists LeadScoreHistoryModel with no `id`; Oracle ORA-01400 cannot insert NULL into ("CORTEX"."LEAD_SCORES"."ID") (journal 2026-11-15 13:00:49 IST). Score survives only in process memory |
| 7 | GET /leads/{id}/follow-up (minimal lead) | 200, score **10** | NO — 8 of 10 points from never-supplied inputs (industry "" → firmographic +5 default; source "" → source 3 default; only website_visits=10 supplied → behavior 2) |
| 8 | POST /leads/{id}/clv with `{}` | 200, predicted_clv **444.0** | NO — entirely from route defaults (avg_order_value 1000, purchase_frequency 2, lifetime 3y) × the phantom-influenced score of #7 |
| 9 | POST /analytics/forecast ([10,12,11,13,15,14,16]) | 200, "accuracy" **0.9428**, "seasonality" true | NO — accuracy is in-sample 1 − residual_std/mean of the OLS fit, NOT forecast accuracy; seasonality flag is a first-half vs second-half mean-shift >20% test (level shift), not seasonality |
| 10 | POST /analytics/demand-forecast ([100,110,105,120]) | 200, confidence **0.8**, "Increase inventory" | NO — confidence = min(0.85, 0.4 + 2·\|growth\|); growth uses ONLY first/last points |
| 11 | POST /analytics/seasonality ([5,9]×4, period 2 — perfect period-2 pattern) | 200, has_seasonality **false**, period_averages [7,7,7,7], CV 0.0 | NO — and the answer is wrong: detector compares whole-period means, structurally cannot detect within-period seasonality |
| 12 | predict_customer_behavior (library) | confidence ∈ {0.8, 0.6, 0.5, 0.4} | NO — bucket constants by frequency rule, no basis |
| 13 | analyze_trend (library/route) | confidence = min(0.9, 0.3 + 5·\|last-step %Δ\|) | NO — single-step formula, no basis |

## Verdict

- Sampled production outputs: **13** (11 delivered, 2 HTTP 500 with no output).
- Fully traceable: **0 of 11 delivered outputs (0%)**.
- Phantom-input decisions proven live: #1 (75% of the matrix invented), #7 (80% of
  the score from defaults), #8 (100% of financial inputs defaulted).
- Production defects found: hybrid recommendations 500 for every user with a
  profile (#4); lead-score route 500 on 100% of calls (#6); seasonality detector
  structurally incapable of detecting within-period seasonality (#11).

## Fix (this PR)

All under `Cortex/apps/api/src/cortex_api/`:

- **NEW `provenance.py`** — REL-032-pattern helper: `build_provenance(...)` /
  `input_record(...)`. Sources: caller_supplied / engine_default / route_default /
  derived / stored_state. Block: `generated_at` (ISO UTC), `inputs_used`,
  `defaults_applied`, `confidence`, `confidence_basis`, `data_status`
  (auto: no_data / partial_inputs_defaulted / complete_inputs).
- **decision_recommendation_system.py** — Recommendation carries provenance:
  every matrix cell recorded as caller_supplied vs engine_default (0.5), weights
  and risk/return as stored_state; basis states the confidence is a score share,
  NOT a calibrated probability. Report's recent_recommendations carry
  data_status + defaults_applied. New `_require_fields` → HTTP 400 naming
  missing fields on criteria/alternatives/score/recommend (kills the
  KeyError-500 class: 8/8 production score requests). /recommend returns the
  full record incl. provenance.
- **recommendation_engine.py** — hybrid bug fixed
  (`content_filter(user_id, top_k=top_k * 2)`); new
  `recommendation_provenance(...)` (history size, similar-user count,
  item-feature count, profile last_active, per-strategy basis, no_data for
  unknown users); both GET recommendation responses include provenance.
- **enhanced_crm.py** — LeadScore carries provenance (route passes
  `supplied_fields`; unsupplied inputs marked route_default; basis discloses
  predicted_value = total × $100 heuristic, NOT measured revenue); score route:
  400 on missing lead_id, history row now gets `id=uuid.uuid4().hex` (the
  ORA-01400 fix), and an IntegrityError on commit → 404 (scoring an
  uncaptured lead violates the LEAD_SCORES→LEADS FK on enforcing databases —
  a client error, not a 500). Follow-up and CLV responses include provenance;
  CLV discloses its three financial inputs as caller_supplied vs route_default.
- **predictive_analytics.py** — provenance on ForecastResult / TrendAnalysis /
  DemandForecast / behavior prediction / seasonality: forecast basis states the
  "accuracy" is in-sample fit, NOT forecast accuracy, and the seasonality flag
  is a level-shift heuristic; demand basis discloses endpoints-only growth and
  the confidence formula; seasonality basis states the whole-period-means
  limitation in every return path. **Detector math deliberately unchanged** —
  the basis is disclosed; changing the statistic is a separate decision.

## Tests

`Cortex/tests/unit/test_cor002_decision_provenance.py` — 15 tests:

- **15/15 pass with this fix; 15/15 fail on clean main 337a1e3f** (verified in a
  pristine worktree of main with only the test file added).
- Coverage: defaulted-cell disclosure (exactly 3 defaults in the partial-matrix
  case), complete-matrix = complete_inputs, decision route 400-on-missing-field,
  hybrid no-crash regression, recommendation provenance + unknown-user no_data,
  lead-score provenance marking, lead-score route persists a row with non-null
  id (the ORA-01400 lock), CLV defaults disclosure, forecast/trend/demand/
  behavior/seasonality basis assertions.
- Neighbouring suites on the branch: test_rel020_analytics_honesty +
  test_no_fabricated_data + test_advanced_analytics = 17 passed.
- Full Cortex unit sweep (458 collected, excluding 2 files that need the
  `respx` package absent from the sandbox venv — pre-existing): branch
  8F/403P/47E vs clean main 7F/382P/69E. All 7 main failures are pre-existing;
  the single branch-only failure
  (test_webhook_gateway_security::test_stripe_route_is_not_shadowed_by_the_catch_all,
  a subsystem this PR does not touch) also fails intermittently on clean main
  (2 failed in main's standalone run, 0 in another) — flaky in this sandbox,
  not a regression. Error-count variance is fixture/tempfile noise under
  sandbox load and differs between runs of the same tree.

## Residuals / not claimed

- LEAD_SCORES FK behaviour on production Oracle could not be re-verified live
  (bridge reads were inconclusive under load). The route is correct under both
  schema variants: captured leads score and persist; uncaptured lead_ids get a
  clean 404 instead of a 500.
- Seasonality detector statistic unchanged (basis disclosed only).
- Probe residue: none persisted — decision/recommendation probe state is
  in-memory in the single Cortex worker; lead-score probes 500'd before commit.
- Status at handoff: implemented + tested, PR open (IN_REVIEW). Merged /
  deployed / production-verified are the coordinator's steps and are NOT
  claimed here.
