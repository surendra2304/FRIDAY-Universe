# TASK-IG-INF-01-FIX-01 — Inference: fix long-context fit routing

## 1. Task

- **Task:** TASK-IG-INF-01-FIX-01 (P1, Inference)
- **Title (board):** 'Inference: fix long-context fit routing - auto path bypass + health overlay precedes fit filter (IG-INF-01 fix)'
- **Claim:** hub #1483, comment 7164966623, 2026-11-25 ~19:45 IST, per coordinator WATCH101 ruling (7164435710) — skip blocked head INT-020 and blocked pos 2 VOI-030, claim this now.
- **Branch:** `muse13/task-ig-inf-01-fix-01` from main `14181d3c` (created via Git Data API, verified read-back).
- **Work PR:** #1854 (https://github.com/surendra2304/FRIDAY-Universe/pull/1854), head 2172886e, base main 14181d3c. Checkpoint 1: commit 1 `1bde103e` (evidence doc), commit 2 `6e94dd8d` (board flip), commit 3 `2172886e` (head-pointer correction). **MERGED 2026-11-25 ~20:20 IST by the coordinator flow (merge 7871150c, CI 9/9 green on head 2172886e — WATCH103, hub 7165911052).** Board flip landed: IG-INF-01-FIX-01 → CLAIMED/muse_13/pr 1854 on main (verified first-hand on main 5c901138, §2 below).
- **Implementation branch:** `muse13/task-ig-inf-01-fix-01-impl` from main `0eeaa43a` (checkpoint 2 — see §9).
- **Implementation PR:** #1865 (https://github.com/surendra2304/FRIDAY-Universe/pull/1865), head `b3aa5828`, base main `0eeaa43a`. Commit 1 `2f5aa24c` (code + tests + evidence doc); commit 2 `d0dd7d20` (board flip + PR number); commit 3 `b3aa5828` (REL-068 collection fix). **MERGED 2026-11-25 22:07:37 IST by Surendra (merge 9025af4e, CI 10/10 green on head b3aa5828 — 8 success, 2 skipped, verified first-hand).** Board flip landed: IG-INF-01-FIX-01 → MERGED on main (verified first-hand on main a759a031, board blob 31ae33e4, 990 records, 0 dups).

## 2. Board verification (first-hand, main 14181d3c — checkpoint 1; re-verified on main 5c901138, 20:36 run)

- Board file `docs/collaboration/WORK_BOARD.yaml`, blob `fd277ad5`, 22,993 lines, 889 `- id:` records by my regex (coordinator's validator parses 981 — my regex undercounts records under different nesting; no duplicates among the records it sees).
- TASK-IG-INF-01-FIX-01: **AVAILABLE / owner muse_13 / branch null / pr null**, P1, `created_at: '2026-11-25'`, `updated_at: '2026-11-25T15:48:00+05:30'`. Filed by coordinator watch088 from TASK-INF-035 production-verify (PR #1789); assigned to Muse 13 as queue position 3 by watch093.
- No competing claim: hub read through comment 1501 — zero IG-INF-01-FIX-01 claims; WATCH101 assigns it to me.
- Neighbours on main: INT-020 AVAILABLE / owner muse_13 (its CLAIMED flip rides in my open work PR #1834); VOI-030 CLAIMED / owner muse_13 / branch muse13/task-voi-030-acceptance-run-17; INT-053 not yet on the board (0 occurrences — filed in the next coordinator board PR, M13 pos 2).

### Re-verification — main 5c901138 (20:36 self-check run, before implementation)

- PR #1854 **MERGED** (state closed, merged True; WATCH103: merge 7871150c, CI 9/9 green on head 2172886e). No stall: checkpoint 1 landed with green CI.
- Board on main 5c901138 (blob 3f472e2d, 2,895,614 bytes — fetched via git blob API; the contents API returns empty for files this large): **890 records by the corrected `^  - id:` regex, 0 dups** (coordinator's validator parses 984 — my regex still undercounts nested records; no duplicates among the records it sees).
  - TASK-IG-INF-01-FIX-01: **CLAIMED / muse_13 / muse13/task-ig-inf-01-fix-01 / pr 1854**, P1 ✓
  - TASK-INT-053: **AVAILABLE / muse_13 / null / null**, P2 ✓ (filed via coordinator board PR #1855, merge 9e5e9a6a — WATCH103)
  - TASK-INT-020: AVAILABLE / muse_13 / null / null, P2 (CLAIMED flip rides in open PR #1834)
  - TASK-VOI-030: CLAIMED / muse_13 / muse13/task-voi-030-acceptance-run-17 / pr null, P1
  - TASK-INF-040 / INF-041 / INF-037: MERGED ✓
- Hub #1483: 1,530 comments at run start (last 7166221593, ~20:33 IST). WATCH102 (7165214180, ~20:10 IST) + WATCH103 (7165911052, ~20:21 IST) read in full: no new M13 directive — "M13: IG-INF-01-FIX-01 claimed (7164966623). INT-053 filed as pos 2." (WATCH102). Fleet alert carried by the coordinator: Server 2 disk 92% and climbing (owner-word action, not mine). VOI-043 (Muse 1, P0 voice legs (c)+(d)) complete, work PR #1856 merge owed — voice improving, but VOI-030 still blocked pending the owner's re-test.

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

Implemented YES / tested YES (CI 10/10 green on merged head b3aa5828 — 8 success, 2 skipped, verified first-hand) / merged YES (PR #1865, merge 9025af4e, 2026-11-25 22:07:37 IST by Surendra) / deployed NO / production-verified NO — checkpoint 1 merged (PR #1854, merge 7871150c, CI 9/9 green). Live re-probe still needs Muse's deployment clearance after the code lands; clearance requested on #1483, comment 7169108662.

## 8. Queue

IG-INF-01-FIX-01 (head) → INT-053 (pos 2, filed on main via coordinator board PR #1855, merge 9e5e9a6a — AVAILABLE/muse_13) → VOI-030 (pos 3, blocked — calm window; P0 voice NOT WORKING until the owner re-tests; VOI-043 legs (c)+(d) complete per Muse 1, PR #1856 merge owed). INT-020 stays CLAIMED / owner muse_13, held for the INT-053 synthesis fix (0/3 live runs, all failing at synthesis — evidence in TASK-INT-020 doc, work PR #1834 open, CI green on head b9d665a7: 7 success, 2 skipped).

## 9. Run log

### Checkpoint 1 — claim + recon (2026-11-25 ~19:45 IST, hourly self-check run)

- WATCH101 ruling (7164435710) acted on: claim IG-INF-01-FIX-01 now.
- Board verified first-hand on main 14181d3c (§2); claim posted on #1483, comment 7164966623.
- Recon anchors read first-hand on main (§4); no code changed yet.
- Usage: 38% of free weekly limit, reset Nov 29 6:09 PM IST. No subscription.

— Muse 13

### Checkpoint 2 — implementation filed (2026-11-25 ~20:50 IST, hourly self-check run)

- **State check first:** PR #1854 MERGED (merge 7871150c, CI 9/9 green — WATCH103); board on main 5c901138 verified first-hand (§2) — no stall, progress real. WATCH102/103 read in full; no new M13 directive.
- **What changed** (`Inference/app/api/v1_core_routes.py`, +~90 lines incl. comments):
  1. **Fit for `"auto"` too (disclosure only):** when `req.model == "auto"` and the estimated size exceeds the 131,072-token floor, the route computes `_select_best_suitable(req)` into `auto_fit` and attaches `estimated_context_tokens` / `context_window` / `context_overflow` / `fit_selected_model` to provenance. The serve path is untouched — the executed request still carries `model=None`, the ladder still chooses. Below the floor `auto_fit` stays None and the `"auto"` path is byte-identical.
  2. **Fit filter before the health overlay** (`_ranked_suitable_models`): fit now runs first on the full pool; the health, servability (REL-049) and Groq-guard (INF-012) overlays filter *within* the fitting set, each keeping its never-empty fallback. On the overflow path (nothing fits) the pool is returned window-sorted, largest first, and the availability overlays are skipped — the choice is the largest holder either way. This is the L4 fix: route-level health can no longer drop the long-window models before fit runs.
  3. **Extended route deadline for fit-routed requests:** `route_timeout` is now `REQUEST_TIMEOUT × 2.0` (`_FIT_ROUTED_TIMEOUT_MULTIPLIER`) when best-suitable selection ran with fit accounting (selection path only; `"auto"` keeps the standard 60 s budget). The bounded policy retry shares the same deadline, so the extension covers it too. Provenance discloses `route_timeout_seconds: 120.0` on fit-routed serves.
- **Tests** (`Inference/tests/test_ig_inf01_long_context_routing.py`, 12 → 18 tests): the old `test_overflow_with_big_windows_unavailable_picks_largest_remaining` expectation is replaced — it pinned the defective order (health before fit); the new `test_fit_runs_before_health_so_unhealthy_long_window_models_still_serve` pins the fix (Gemini unhealthy → gemini-3.8-flash still chosen, overflow False). Added: ranking-level fit-before-health pin, overflow-with-unhealthy-long-windows largest-holder pin, quarantine-still-applies-within-fitting-set (servability fixture, REL-049 pattern), auto route provenance test (ladder stub serves gemini-3.6-flash; executed request still `model=None`), fit-routed deadline test (first-attempt timeout in (100, 120], provenance `route_timeout_seconds` 120.0) + standard-deadline control (timeout in (50, 60], no extension disclosed). No other test file uses `required_tokens` (checked test_rel043 / test_inf012 / test_inf016 / test_v1_auto_fastlane first-hand) — only this file's expectations change.
- **Validation:** both files `py_compile` clean; expected ranking values cross-checked by a standalone simulation of the new order against the real catalogue data (fit-before-health trio, quarantine pair, overflow largest-holder, token estimates 308,716 / 4,616,408). **No local test run:** a scratch repo clone was created for a local pytest run but the run was stopped by an execution-risk check on the cloned content, and the clone was removed; the suite runs in CI on the work PR instead — **tested state stays NO until CI is green, verified first-hand in the next run.**
- **Known gap (not in this fix):** the streaming path (`stream_model` default `openai/gpt-oss-120b` for `"auto"`) has no provenance surface and is unchanged — an oversized `"auto"` stream still routes to the 131k default. Follow-up owed, not acceptance-blocking (acceptance is about the non-stream route + provenance).
- **Work PR #1865** (https://github.com/surendra2304/FRIDAY-Universe/pull/1865), head `2f5aa24c`, base main `0eeaa43a`, 1 commit, +294/−40, 3 files, open; mergeable_state unknown at opening (GitHub computing). Commit 2 on the same branch adds the board flip (IG-INF-01-FIX-01 → IN_PROGRESS / pr 1865) + this PR number in the doc.
- Usage: 38% of free weekly limit (19:36 run; re-check owed next run), reset Nov 29 6:09 PM IST. No subscription.

— Muse 13

### Checkpoint 4 — MERGED (2026-11-25 ~22:40 IST, hourly self-check run)

- **Work PR #1865 MERGED** by Surendra (merge 9025af4e, 22:07:37 IST, head b3aa5828, 3 commits, +303/−45, 5 files). **CI 10/10 green on the merged head, verified first-hand** (8 success, 2 skipped — test + contracts both success). Board on main a759a031 verified first-hand (blob 31ae33e4, 990 records, 0 dups): IG-INF-01-FIX-01 → MERGED / muse_13 / pr 1865 (flip rode in coordinator board PR #1874, WATCH108).
- **Five states:** implemented YES / tested YES / merged YES / deployed NO / production-verified NO. The live re-probe leg is blocked on deployment clearance — requested from Muse on #1483, comment 7169108662. Until clearance lands, the live leg stays owed, not claimed as done.
- **Queue moves:** head now blocked on clearance, so per the blocked-head rule the next task is claimed: TASK-INT-053 (claim comment 7169108662, branch muse13/task-int-053-synthesis-fix @ main a759a031; checkpoint 1 PR follows in the same run). INT-020 stays CLAIMED, held for the INT-053 fix. VOI-030 stays blocked (calm window).
- Usage: 39% of free weekly limit (last verified 20:36 IST), reset Nov 29 6:09 PM IST. No subscription.

— Muse 13
