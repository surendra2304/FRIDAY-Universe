# TASK-INF-045 — Fallback-path audibility: receipts record a fallback reason

Owner: Muse 7. Branch: `muse7/task-inf-045-fallback-audibility` (from main `df4e261b`).
Claim: hub issue #1483 comment 7199637560.

## Acceptance (board record)

- Forced-fallback live probe filed with the full receipt (class, model, latency, fallback, fallback reason).
- Fallback reason captured in receipts, or the gap + the fix filed.
- No silent fallback in the probe.

## Trace (first-hand, GitHub API blobs on main df4e261b)

INF-022 receipts live in `Inference/app/providers/gateway.py`: `execute()` builds the
receipt (capability, requested/served provider+model, prompt token estimate, deadline
class, timeout budget, outcome, latency, `fallback_used`, `fallback_direct`) and
`Inference/app/health.py` surfaces counts + recent receipts on /status.

Gap found: receipts carried no fallback *reason*. `fallback_used` is derived after the
fact (served != requested), and only the large-prompt Gemini bypass annotated the
receipt (`fallback_direct` + `routing_note`). The other ladder entries — Groq
prompt-over-limit guard, disabled rungs (nvidia/bytez), the unconfigured-provider
gate, and primary-attempt failure (timeout / rate limit / unavailable / slice
exhausted) — entered `_execute_dynamic_fallback` with no reason on the receipt. A
fallback could therefore be visible as a boolean while its cause stayed silent.

## Fix (this PR)

- Receipt gains `fallback_reason` (default null).
- `_annotate_fallback_reason()` records the first reason that sent the request to
  the ladder, at every `_execute_dynamic_fallback` entry: `groq_prompt_over_limit`,
  `large_prompt_primary_skipped`, `provider_disabled`, `provider_unconfigured`, and
  `_primary_failure_reason(last_error)` for primary failures (`primary_timeout`,
  `primary_rate_limited`, `primary_unavailable`, `primary_slice_exhausted`,
  `provider_unconfigured`, `primary_error`).
- Safety net in `execute()`: a served fallback with no entry annotation records
  `served_by_fallback` — a fallback receipt never carries a null reason.
- Tests (`Inference/tests/test_inf022_routing_receipts.py`): large-bypass reason
  asserted exactly; primary success asserts null reason; error receipt asserts a
  reason; new primary-failure test asserts the ladder-served receipt carries
  `primary_error`/`primary_unavailable` with `fallback_direct` false.
- CI repair (2026-11-26 hourly check): PR #2003's contracts job failed the
  REL-068 collection guard because this PR modifies
  `test_inf022_routing_receipts.py` while no PR workflow collected it. The file
  now rides in the Inference tier-1 invocation in
  `.github/workflows/friday-universe-ci.yml`. Collecting it exposed one stale
  all-providers-fail test: INF-030 added APInex as a waterfall rung, so the
  error-receipt test now fails `apinex` too (the same stale-test finding Muse 5
  filed under INF-044). Local verification in a clean Inference venv
  (`requirements.txt` + pytest + pytest-asyncio + aiosqlite): the 9 receipt
  tests pass, and the full Inference tier-1 list (54 tests) passes.

## Live probe leg — blocked, stated plainly

Receipts are in-memory and process-local by design; the full receipt is readable
only on the live Inference /status. From this VM I have no verified route to the
live Inference /status that needs no server change, so the forced-fallback live
probe is NOT claimed here. It needs the coordinator's bridge route to the live
Inference service (read /status before/after one forced-fallback request). No
server move, restart, or config change was made or is requested by this PR.

## Five states

- implemented: YES (repo-side fix + tests in this PR)
- tested: YES locally (54-test Inference tier-1 list green, incl. the 9 receipt
  tests); CI on this PR pending the repair push — see checks
- merged: NO
- deployed: NO
- production-verified: NO (live probe leg blocked as above)

— Muse 7
