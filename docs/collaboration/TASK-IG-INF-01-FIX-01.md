# TASK-IG-INF-01-FIX-01 — Inference: fix long-context fit routing

## 1. Task

- **Task:** TASK-IG-INF-01-FIX-01 (P1, Inference)
- **Title (board):** 'Inference: fix long-context fit routing - auto path bypass + health overlay precedes fit filter (IG-INF-01 fix)'
- **Claim:** hub #1483, comment 7164966623, 2026-11-25 ~19:45 IST, per coordinator WATCH101 ruling (7164435710) — skip blocked head INT-020 and blocked pos 2 VOI-030, claim this now.
- **Branch:** `muse13/task-ig-inf-01-fix-01` from main `14181d3c` (created via Git Data API, verified read-back).
- **Work PR:** #1854 (https://github.com/surendra2304/FRIDAY-Universe/pull/1854), head 6e94dd8d, base main 14181d3c. Checkpoint 1: commit 1 `1bde103e` (evidence doc), commit 2 `6e94dd8d` (board flip).

## 2. Board verification (first-hand, main 14181d3c)

- Board file `docs/collaboration/WORK_BOARD.yaml`, blob `fd277ad5`, 22,993 lines, 889 `- id:` records by my regex (coordinator's validator parses 981 — my regex undercounts records under different nesting; no duplicates among the records it sees).
- TASK-IG-INF-01-FIX-01: **AVAILABLE / owner muse_13 / branch null / pr null**, P1, `created_at: '2026-11-25'`, `updated_at: '2026-11-25T15:48:00+05:30'`. Filed by coordinator watch088 from TASK-INF-035 production-verify (PR #1789); assigned to Muse 13 as queue position 3 by watch093.
- No competing claim: hub read through comment 1501 — zero IG-INF-01-FIX-01 claims; WATCH101 assigns it to me.
- Neighbours on main: INT-020 AVAILABLE / owner muse_13 (its CLAIMED flip rides in my open work PR #1834); VOI-030 CLAIMED / owner muse_13 / branch muse13/task-voi-030-acceptance-run-17; INT-053 not yet on the board (0 occurrences — filed in the next coordinator board PR, M13 pos 2).

## 3. Problem (live evidence, TASK-INF-035, PR #1789)

IG-INF-01 (long-context routing respects declared context windows) was PRODUCTION-VERIFY **PARTIAL** 2026-11-25: fit **disclosure** verified live, fit **routing guarantee** NOT verified. Four probes, one real document (first 350k–400k chars of the live work board on S1), via the S1 tunnel to the AWS Inference gateway:

- **L2 — `model: "auto"`, 400,000-char doc, est. 154,046 tokens:** HTTP 200 in 38.88 s, served by `openrouter` / `nvidia/nemotron-3.5-super-vl:free` — a model **outside** the verified catalogue, via the gateway's dynamic ladder. **No fit fields in provenance at all.** The route computes selection (and therefore the fit filter) only for named non-catalogue models, quarantined models, or the bounded retry — for `"auto"` it never runs, so the fit filter is bypassed on the default path.
- **L3A — `model: "no-such-model-xyz"` (forces best-suitable selection), same doc:** HTTP 503 in 60.68 s (full 60 s route deadline). Honest `provider_degraded` 503. Selection could not serve an oversized document within the route budget.
- **L3B — `model: "openai/gpt-oss-120b"` (named 131k-window catalogue model), same doc:** HTTP 503 in 4.15 s, same honest message. Not silently truncated, not wrongly served — but not served at all.
- **L4 — `model: "no-such-model-xyz"`, 350,000-char doc, est. 134,815 tokens:** HTTP 200 in 60.03 s, served by `gemini` / `gemini-3.6-flash`. Provenance DOES carry fit accounting: `estimated_context_tokens: 134885`, `context_window: 131072`, `context_overflow: true`. But the mechanism is not the fit filter choosing a long-window model: the code runs the provider-health overlay **before** the fit filter, and at selection time the gateway health tracker judged `gemini` unhealthy, so all three Gemini models were dropped first; the fit filter then ran over 131k-window models only, and its overflow fallback picked llama-3.3-70b (131,072). The request was served not by the fit choice but by the gateway ladder falling through to gemini-3.6-flash after the openrouter rung died at 14.9 s. Divergence exposed: route-level health said Gemini was unfit to select, while the gateway ladder served Gemini fine moments later.
- The `context_overflow: true` case with a request above **every** window (> 2,097,152 tokens) was NOT RUN — it would need a ~5.4M-char prompt, not a realistic or safe live probe; the overflow disclosure itself is verified by L4's `true` value.

So the acceptance bullet *"requests estimated above 131,072 tokens are routed only to models whose window holds prompt + reserved output"* does **not** hold live in general: (a) `"auto"` bypasses selection and fit entirely; (b) on the selection path the health overlay precedes the fit filter, so long-window models can be filtered out before fit runs; (c) the one oversized request that was served got there via ladder luck, not via the fit choice.

## 4. Recon — code anchors (first-hand, main 14181d3c)

File `Inference/app/api/v1_core_routes.py` (blob `a9191bb3`, 88,241 bytes):

- `_ranked_suitable_models` (line 1261): applies overlays in this order — exclusions, **provider health** (`_provider_available`, line 1244; `pool = healthy or pool` at line 1308), servability quarantine (REL-049), Groq size-guard (INF-012), then the **fit filter LAST** (line 1346: keep fitting models; if none fit, return pool sorted by window size, largest first). The docstring says so explicitly: "TASK-IG-INF-01's context-window fit filter runs last".
- `_select_best_suitable` (line 1359): computes `required_tokens = _estimate_context_tokens(req)` (line 1378) and discloses overflow in provenance (line 1447ff).
- Selection call sites — 1501 (stream), 1584, 1761 (bounded retry) — all gated on `req.model != "auto"` (lines 1494, 1574, 1580).
- `"auto"` path: line 1552 `if req.model == "auto": exec_provider = "auto"`; line 1652 `model=None if model == "auto"` — the request delegates to the gateway with no model, so no selection, no fit, no provenance fit fields. Line 1492: stream default for auto is `openai/gpt-oss-120b` (a routing default, not a fit-aware choice).
- `MODEL_CONTEXT_WINDOWS` (line 1087) + `_estimate_context_tokens` (line 1109) are the existing fit machinery to reuse.

## 5. Repair plan (board acceptance — one or more of)

1. **Fit selection for `"auto"` too** — at least the provenance disclosure (`estimated_context_tokens` / `context_window` / `context_overflow`), even when the gateway ladder still chooses. Minimal form: compute `_select_best_suitable` / the fit accounting for auto requests and attach it to provenance without changing the serve path; fuller form: pass a fit-chosen model into the gateway call instead of `model=None`.
2. **Fit filter before / independent of the health overlay** — e.g. fit-filter the full catalogue first, then apply health within the fitting set, so long-window models are not removed before fit runs. Must preserve the never-empty discipline of the existing overlays (health is advisory; selection never refuses service by itself).
3. **Extend the route deadline for fit-routed oversized requests** so a Gemini first attempt can complete (L3A hit the 60 s budget; L4 took 60.03 s to serve).

Constraints: no change to the `"auto"` contract beyond fit accounting (auto callers get the ladder's pick by contract — INF-035 observation); no provider kills, no restarts, no fleet writes without clearance; free tiers only. Tests: extend `Inference/tests/test_ig_inf01_long_context_routing.py` (12 tests) for the new behaviour; run the suite before filing.

## 6. Acceptance (live re-probe, after the fix lands)

- An oversized long-document request on `"auto"` **AND** on the selection path is served by a model whose declared window holds prompt + reserved output, with provenance showing `estimated_context_tokens` / `context_window` / `context_overflow: false`.
- A request above every window still discloses `context_overflow: true`.
- Do not mark IG-INF-01 verified until then (its board record stays DEPLOYED).

Live-leg notes: the live Inference gateway is the AWS host reached via the S1 tunnel; S1's local `Inference.service` has been down since 2026-11-24 ~13:42 IST (bind conflict after the tunnel took :8001) and is `disabled` (INF-035 observation). Deploying the fix to the live gateway needs Muse's clearance on the hub under the live-servers rule — repo implementation + tests first, deployment clearance requested when the code is ready, re-probe only after it lands.

## 7. Five states

Implemented NO / tested NO / merged NO / deployed NO / production-verified NO — claimed, checkpoint 1 filed (claim + recon + plan). Work PR open (see §1).

## 8. Queue

IG-INF-01-FIX-01 (head) → INT-053 (pos 2, filed in next coordinator board PR) → VOI-030 (pos 3, blocked — calm window; P0 voice NOT WORKING until the owner re-tests). INT-020 stays CLAIMED / owner muse_13, held for the INT-053 synthesis fix (0/3 live runs, all failing at synthesis — evidence in TASK-INT-020 doc, work PR #1834 open, CI green on head b9d665a7: 7 success, 2 skipped).

## 9. Run log

### Checkpoint 1 — claim + recon (2026-11-25 ~19:45 IST, hourly self-check run)

- WATCH101 ruling (7164435710) acted on: claim IG-INF-01-FIX-01 now.
- Board verified first-hand on main 14181d3c (§2); claim posted on #1483, comment 7164966623.
- Recon anchors read first-hand on main (§4); no code changed yet.
- Usage: 38% of free weekly limit, reset Nov 29 6:09 PM IST. No subscription.

— Muse 13
