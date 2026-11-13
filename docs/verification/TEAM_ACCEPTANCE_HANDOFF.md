# United owner-workflow acceptance — TASK-WF-015

**Continuing, not complete.** Arena Agent 1 owns this acceptance lane. The owner explicitly rejected stopping after WF014. The machine-readable matrix is [OWNER_WORKFLOW_ACCEPTANCE.yaml](OWNER_WORKFLOW_ACCEPTANCE.yaml).

## Team boundaries

Issue35 claim [6842655427](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6842655427) asks ZAI Agent 1 to review/co-own historical PR55 and ZAI Agent 2 for actual voice/owner-audio handoff. No reply to those new requests has been observed. Their existing CI/registry, voice and Stratex/backtest work is preserved; this is not a claim of agreed new assignments. Re-read issue35 before assuming ownership or rollout exclusivity.

Exact-path extension [6842719695](https://github.com/surendra2304/FRIDAY-Universe/issues/35#issuecomment-6842719695): `FRIDAY/src/friday/memory/memora_client.py`, new `FRIDAY/tests/test_shared_memory_lifecycle.py`, plus this acceptance documentation and registry mirror. No voice-worker, trading-strategy, CI-configuration or generated-converter changes.

## Real deployed observations before this fix

Checkout `e36ee11a424b5128c98314b01abac29231362ad6`:

- Canonical `/api/chat` stored disposable marker `wf0153274db929d` with `memory_store=true`; immediate recall returned zero remembered facts. Later fresh-process authenticated Memora searches found exact active ID `60a97947-99e8-4812-8b1d-64123fde7750`. Do not explain this transient as fixed without evidence.
- A guarded real `MemoraClient.correct_fact` call, allowing only that exact live synthetic search result, returned `error`. Reconciliation found the old revision still active. No broad-query deletion, no fixture substituted for live search, no blind mutation retry.
- The deployed `MemoryWriteResponse` exposes ID/durability but **no status**; `correct_fact` rejected that legitimate contract. Its subsequent remote transition also used `urllib` response `.status_code` rather than `.status`, demonstrated with a real `http.client.HTTPResponse` regression. Existing correction tests used only the local SQLite fallback and missed both contracts.
- Canonical research IntelX `task_5cb407ee2846` retrieved the actual CSV/JSON documentation URLs with `retrieved_document`/`independently_verified=false`. CSV excerpts discussed DictWriter, escaping and line counts but did not fully answer the quoted-comma question. Retrieval is real; answer relevance remains partial, not a pass based on two citations.
- Read-only video inventory: ffmpeg present; actual configured YouTube adapter failed `RuntimeError`. That exception is not evidence of `invalid_grant`; classify it before prescribing OAuth repair. No render/upload/publication performed in this task.

Private raw receipts live under `/var/tmp/friday-workflow-acceptance/` with `wf015-` prefixes. Do not publish environment files, tokens, owner memories or raw service logs. The synthetic fact is deliberately not an owner preference.

## Repair contract and test evidence

The client fix accepts an ID-bearing successful deployed receipt, rejects explicit failures/non-durable receipts, requests a distinct candidate for intentional correction (`allow_duplicates=true`, normal writes unchanged), uses urllib `.status`, and inspects actual winner/loser IDs. Memora may legitimately prefer the old fact: report `not_applied`, never invent a successful replacement. Unknown or timed-out shared transitions stay `unconfirmed`; do not certify cloud correction by editing a local mirror and do not automatically retry.

Before repair, focused regression battery: **5 failed / 5 passed**, exit1 (after installing missing sandbox dependencies; initial collection exit4 was environment-only). After repair plus expanded transport/default/local-scope controls: **125 passed**, exit0 across `test_shared_memory_lifecycle.py`, `test_memory_commands.py`, `test_batch4_memory_brain.py`. These tests are hermetic contracts, **not deployed acceptance**.

## Still required

1. Fresh exact-head CI, protected-untracked preflight and controlled rollout; then real fresh-process lifecycle proof with exact synthetic IDs and cleanup. Retain failed-before evidence.
2. Resolve canonical immediate recall and mutation-target safety before full memory acceptance. Do not use “forget that” to test broad owner memories.
3. Improve/verify research question relevance separately from retrieval fidelity.
4. Consume actual ZAI replies; do not manufacture acknowledgments. Owner microphone session, legitimate OAuth/review, rendered-artifact playback and sustained exchange-reconciled profit remain separate gates.

WF013 package and WF014 source-bound receipts remain unchanged. WF014 final Telegram message55 was already sent. A narrow fix does not justify another whole-work-completed notification or stopping broader owner acceptance.
