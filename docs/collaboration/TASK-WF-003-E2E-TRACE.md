# TASK-WF-003 — End-to-end trace evidence

**Task:** Integration: second united end-to-end task — a real request flowing FRIDAY, Inference, Memora and IntelX and back, timed, evidence at each hop.
**Claim:** hub issue #1483 comment 7117372214 (2026-11-24 ~05:15 IST), Muse 5.
**Branch:** `muse5/task-wf-003-e2e-trace` (from main `95a92a0f`).
**Trace id:** `wf003-20261124T005930Z`.
**Trace window:** 2026-11-24 06:29:30–06:32:12 IST (00:59:30–01:02:12 UTC).
**Method:** four real dispatches through FRIDAY's live unified dispatch bus
(`POST /api/v1/dispatch/send` on FRIDAY :10000, S1 `10.0.0.121`), one per hop,
timed by the bus (`latency_ms`) and by wall clock. No mock, no fixture, no
bypass. Raw per-hop JSON is on S2 at `/tmp/wf003_trace.json`.

## The request (verbatim)

> Research Oracle Cloud free-tier Ampere A1 limits, remember the key numbers,
> and reason about whether our 6/4 fleet layout fits within them.

One request, four hops: FRIDAY → IntelX (live research) → Memora (store the
finding) → Memora (recall it back) → Inference (reason over the recalled
facts) → back to FRIDAY (aggregate + dispatch-records report).

## Pre-trace fleet probe (2026-11-24 06:26:39 IST)

`GET /api/agents/status` on FRIDAY: HTTP 200, overall `degraded`, 9 agents —
ONLINE 1 (Memora), REACHABLE 4 (Inference, Cortex, Forge, Sentinel),
DEGRADED 2 (IntelX, Futuris — by-design honest degradation per OBS-016,
`NO_LIVE_PROBE` / `NO_MODEL_PROBE`), UNREACHABLE 2 (Stratex — sleeping copy,
expected; VyralX — FRIDAY still probes the deleted AWS address
`http://16.176.9.247:8010`, ConnectTimeout; stale config from the U2 deletion,
out of scope for this task, noted here).
Dispatch bus `GET /api/v1/dispatch/agents`: all 9 agents registered, all
circuits closed, 0 consecutive failures. Records report baseline: `total 0`
(clean since FRIDAY restart).

## Hop results

| Hop | Agent / action | Bus task id | HTTP | Bus status | Bus latency | Wall |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | IntelX / `research_live` | `disp_bddae31fb8af` | 200 | completed | 29,107 ms | 30,864 ms |
| 2 | Memora / `store` | `disp_48fad1ff9382` | 200 | **failed** | 10,109 ms | 14,809 ms |
| 3 | Memora / `query` | `disp_66b1dfc28573` | 200 | **failed** | 3,194 ms | 3,207 ms |
| 4 | Inference / `reason` | `disp_79acdbd57fe3` | 200 | completed | 5,562 ms | 5,649 ms |

Sum of bus latencies: 47,972 ms. Total trace wall time (first dispatch start
to last dispatch end, incl. bridge overhead between stages): ~2m 42s.

## Hop 1 — IntelX `research_live`: COMPLETED

Topic (verbatim): `Oracle Cloud Infrastructure Always Free Ampere A1 compute
instance limits OCPU memory`.

Live research run `lr_84b50db536f442efb17309ae`, `durable_run: true`,
`status: SUCCESS`, synthesis by Inference (`synthesis_status: succeeded`).
`answer_kind: source_attributed_model_draft`, `question_answered: false`,
`quotes_verified: true`, `semantic_entailment_verified: true`.
IntelX's own summary: "Retrieved 1 source document(s); findings are
source-attributed, not independent verification." Confidence: Low — single
domain (`docs.oracle.com`); quotations verified verbatim, claims not
independently fact-checked. 5 documents retrieved, collapsed to 1 distinct
domain; 2 source failures (community.oracle.com HTTP 403; one duplicate URL).
Source retrieved 2026-11-24T00:59:39Z.

Findings (verbatim, all `quote_verified: true`, `live_quote_reverified:
true`, `diversity_flag: single_source`):

1. "Always Free tenancies receive 1,500 OCPU hours and 9,000 GB hours per
   month for OCI Ampere A1 Compute instances, which is equivalent to 2 OCPUs
   and 12 GB of memory."
2. "Users can create up to two OCI Ampere A1 Compute instances with a total
   of 2 OCPUs, or a single instance using all available OCPUs and memory."
3. "The minimum boot volume size for each OCI Ampere A1 Compute instance is
   47 GB, regardless of the shape configuration."

Source (single): "Always Free Resources",
<https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm#Details_of_the_Always_Free_compute_instances__a1_flex>

## Hop 2 — Memora `store`: FAILED (truthful failure, known gate)

Store payload: the three IntelX findings above, tagged `TASK-WF-003 trace
wf003-20261124T005930Z`, `memory_type: observation`, target namespace
`memora://friday/general` (Memora default for the FRIDAY actor).

Bus receipt: `status: failed`, error verbatim:

> `HTTP 401: {"detail":"Invalid agent credentials","error":"http_401","message":"Invalid agent credentials","success":false}`

This is the known VAL-009 401 gate: FRIDAY's dispatch bus sends no credential
Memora accepts, so Memora fails closed. **No bypass was attempted and none
will be.** The gate is owned by INT-020 (Muse 7). The memory was NOT stored;
nothing in this trace claims otherwise.

## Hop 3 — Memora `query`: FAILED (same gate)

Query (verbatim): `Oracle Ampere A1 free tier limits WF-003`. Same 401,
verbatim: `HTTP 401: {"detail":"Invalid agent credentials", ...}`. No recall
was possible; the Inference hop below therefore reasoned over the IntelX
findings passed directly in its prompt (stated there), not over a Memora
recall. The recall leg is the missing piece of the chain until INT-020 lands.

## Hop 4 — Inference `reason`: COMPLETED

Prompt: the three IntelX findings (quotes verified) plus "Memora recall
returned: no recall" (the 401, stated), asking for a 3-sentence verdict on
whether the 6/4 fleet fits the Always Free Ampere A1 allowance.
Model: `openai/gpt-oss-20b` via Groq, `confidence: 0.55`.

Response verbatim (158 chars — **truncated mid-sentence as returned**; the
first sentence, the verdict, is complete):

> "No, the FRIDAY Universe 6/4 fleet does not fit within the Oracle Always
> Free Ampere A1 allowance.
> The fleet requires two Oracle VMs, each needing at least a"

The verdict is the model's, quoted as returned; its supporting reasoning was
cut off by the provider/model and is NOT reconstructed here. The verdict is
not independently verified — the Always Free allowance (2 OCPUs / 12 GB
across up to 2 instances, per the IntelX findings above) is on its face
enough for two small VMs, so the model's "does not fit" needs its missing
reasoning before anyone acts on it. Flagged, not settled.

## Back at FRIDAY — dispatch-records report

`GET /api/v1/dispatch/records/report` after the trace (06:32:12 IST):

```json
{"enabled": true, "total": 4,
 "by_status": {"submitted": 0, "assigned": 0, "dispatched": 0,
               "completed": 2, "failed": 2, "routing_failed": 0},
 "by_agent": {"IntelX": 1, "Memora": 2, "Inference": 1},
 "unassigned": 0}
```

All four dispatches are in the unified TaskRecord lifecycle, with the 2/2
split exactly as the hops ran. The bus recorded the failures; it did not
hide them.

## Verdict

**Trace executed end-to-end as a trace; acceptance PARTIALLY met.** The
request flowed FRIDAY → IntelX → Inference → back with real evidence at
every hop that ran: live IntelX research with verified quotes and a durable
run id; a real Inference verdict from a live model. The Memora leg did NOT
complete — both its hops failed with the documented 401 gate (INT-020).
That failure is evidence filed at the hop, not a gap in the trace: the
chain is 2 of 4 hops completed, 2 failed for a known, separately-owned
cause. Whether that satisfies "traced end-to-end across FRIDAY, Inference,
Memora and IntelX" is Muse's judgement — the Memora evidence will only turn
green when INT-020 lands, and re-running the store + recall hops then is a
small follow-up, not a new task.

## Follow-ups (not done here)

- INT-020 (Muse 7): Memora 401 gate — after it lands, re-run hops 2–3
  (store + recall of run `lr_84b50db536f442efb17309ae`'s findings) and append
  the result here.
- Inference's truncated reply: worth one re-ask once the recall leg works,
  with the recalled numbers in the prompt, to get the full reasoning behind
  the "does not fit" verdict.
- VyralX fleet probe still points at deleted AWS `16.176.9.247:8010` —
  stale endpoint config, out of scope, needs a fleet-config fix (not this
  task).

— Muse 5
