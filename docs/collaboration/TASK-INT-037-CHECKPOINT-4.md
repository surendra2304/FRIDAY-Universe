# TASK-INT-037 — Checkpoint 4: code-guard PR implemented + tested, ready to open

Filed 2026-11-24 ~16:05 IST by Muse 3, on branch `muse3/task-int-037-futuris-cursor-401s`.
Branch tip before this commit: `a98e6d89` (guard tests).

## 1. Direction received — guard PR is the next step

- Coordinator watch 7128069261 (run scheduled 15:17 IST): "**M3 INT-037:** checkpoint 3
  noted (commit `8969e313`, 121 lines). Proceed with the code-guard PR as your next step
  (401 → retry once with next key in chain + loud warning naming the rejected key; chain
  order unchanged). M8: file the raw grep counts M3 asked for, or state they were not kept."
- Coordinator watch 7128801462 (run scheduled 15:37 IST): "**M3:** INT-037 checkpoint 3
  noted; guard PR next, as directed."

This checkpoint records the implementation, done this run (~16:05 IST).

## 2. Implementation — `MemoraClient._request` 401 guard

Target: `Futuris/futuris/integrations/memora_cloud_fallback.py`, used by the cursor path
`memora_event_consumer.py` → `memora_client` shim → `memora_cloud_fallback._request`
(shim verified this run: it re-exports `MemoraClient, memora_client` from the fallback;
the singleton is built with no explicit `api_key`, so the live chain is env-driven).

Commit `5fa13b4e` (verified read back from the branch, blob `14c06443`):

- New `_key_candidates(agent)` helper: ordered `(label, key)` candidates, chain order kept —
  explicit `api_key` first, dedicated `{AGENT}_MEMORA_API_KEY` second, per-agent
  `{AGENT}_API_KEY` third; `MEMORA_API_KEY` never consulted (TASK-MEM-005-R2); candidates
  deduped by value, so a key appearing twice in the chain is never presented twice.
- `_request` now walks at most the first two candidates: on HTTP 401 from the presented
  key it logs a loud warning naming the rejected key (label, never the key value) and the
  fallback key, then retries the same request ONCE with the next key. If the retry also
  401s, it returns the error dict as today. No third key, no second retry. Non-401 errors
  never retry. The no-key error (`{AGENT}_API_KEY is not configured`) is unchanged.

## 3. Regression tests — 4 new, 8/8 green locally

Commit `a98e6d89` (verified read back from the branch, blob `cedbb15c`), in
`Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py`:

- `test_dedicated_key_401_retries_once_with_peer_key` — 401 on the dedicated key, 200 on
  the peer key; asserts 2 requests, first Bearer dedicated, second Bearer peer, and the
  warning names `FUTURIS_MEMORA_API_KEY` and `FUTURIS_API_KEY` (caplog).
- `test_401_on_both_keys_returns_error` — 401 on both keys; error dict, `last_error`
  `Memora HTTP 401`, exactly 2 requests (no third key).
- `test_401_without_fallback_key_does_not_retry` — dedicated key only; 401 fails as today,
  exactly 1 request.
- `test_non_401_error_does_not_retry` — HTTP 500; error dict, exactly 1 request.

Verified locally this run with pytest 9.2.0 (venv, Python 3.12.3): **8 passed** — the 4
pre-existing MEM-005-R2 chain-order tests plus the 4 new INT-037 tests. The pre-existing
test bodies are byte-identical to the branch original after stripping the intended
additions (verified by strip-and-compare); the `memora-shared-key` fixture value is
intact in all 3 places. Repo CI on the work PR is the merge gate.

## 4. Design decisions (checkpoint 3 §4 open question — decided)

- **Notice-write path OUT of scope for this PR.** `_persist_notice_to_memora` in
  `memora_event_consumer.py` uses `settings.MEMORA_API_KEY` directly via httpx, not this
  client; it already fails loudly on non-2xx. The cursor/read path is the INT-037
  acceptance leg; the notice path is a separate follow-up candidate, not smuggled in here.
- **Explicit-key case:** if a caller passes `api_key` explicitly and it 401s, the retry
  goes to the dedicated env key next (chain order, one retry). The live consumer passes
  no explicit key, so this path is dormant in production.
- **Chain order UNCHANGED** (MEM-005-R2 test still passes — verified in the 8/8 run).

## 5. Board hunk — rides in the coordinator consolidated board PR

The branch base predates the current main board by ~16 h, so a whole-board write from
this branch would clobber other workers' flips. Per coordinator watch 7128069261
("watch011 consolidated board PR files in tomorrow's (2026-11-25) first run — rebuild
hunks from then-current main"), the guard work PR carries NO board file change; the hunk
below goes in the PR body for consolidation:

```yaml
  - id: TASK-INT-037
    status: CLAIMED → IN_PROGRESS
    pr: null → <guard work PR number, filled when opened this run>
    evidence:
      - 'Guard PR <number> (code-guard leg, checkpoint 4): MemoraClient._request retries once on HTTP 401 with the next chain key + loud warning naming the rejected key; chain order unchanged; 4 new regression tests, 8/8 green locally; CI pending on the PR. Notice-write path out of scope (checkpoint 4 §4).'
```

Board re-verified this run on main `dc0e35e4` (blob `2163ddd1`, 18,814 lines): INT-037
CLAIMED / owner muse_3 / branch `muse3/task-int-037-futuris-cursor-401s` / pr null / P1.

## 6. Still owed (not in this PR)

- **Raw grep counts behind "0 true 401s" (M8).** No M8 post since the request; M8 is on
  TASK-STR-047 (claim PR #1654 merged 15:10 IST). Fallback if the raw output is gone: a
  fresh granted S1 probe window aggregated per 15-minute research cycle, raw counts filed.
- **Three consecutive clean cycles** per the ruling (IntelX scheduled research cycle =
  15 min, ~60 cursor polls each) — evidence per cycle, raw counts attached.

## 7. State verified this run (~16:05 IST)

- Branch tip before this commit: `a98e6d89`. Guard commits `5fa13b4e` + `a98e6d89` read
  back verified from the branch.
- Both Oracle servers ONLINE (bridge `get_system_info`; S2 git `09603dff` — S2 checkout
  trails main `dc0e35e4` by the #1652/#1653/#1654 merges, expected, not a fault).
  S2-side: `IntelX/data/watches/outbox.jsonl` still 1,823 bytes (same 2 digest envelopes,
  no instant alert, no `instant_outbox.jsonl`); `state.json` 1,265,976 bytes (polling
  continues, up from 1,261,048 at 15:05 IST).
- Usage 21% of free weekly limit (checked this run via subscription-status; reset
  Nov 28, 11:24 AM IST). Not exhausted — no wrap-up, no cancellations.
- Cron: `muse3-hourly-self-check` + `muse3-weekly-reset` armed; `muse3-work-request`
  absent (correct while mid-task).

## 8. Next steps

1. Open the guard work PR from this branch (code + tests + this checkpoint); Muse merges,
   never the worker. PR body carries the §5 board hunk for consolidation.
2. File the raw grep counts (M8) or run a fresh granted S1 probe window aggregated per
   15-minute cycle — three consecutive cycles at 0 true 401s, raw counts attached.
3. Then the INT-037 acceptance is met: source named with log evidence (checkpoint 2),
   fix merged (guard PR), three clean cycles (evidence per cycle).

— Muse 3
