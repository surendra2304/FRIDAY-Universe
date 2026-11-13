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

## Production followup — canonical recall defect reproduced, work continues

PR72 `c5ceac42` passed7CIchecks/2conditionalDocker skips; merged `7a0e9a043bd79066896dcfc8e28fd08b29cbb09c`; FleetCD43358743587SUCCESS. S1updated; S2correctlyunchanged for FRIDAY-only paths (not claiming code deployed there). Fresh7S1/6S2protectedfilesbyteidentical, tracked/indexclean. The initial generic rollout helper incorrectly required the FRIDAY commit on intentionally skipped S2 and reported missing ancestry; separate scope-correct safety check proved its protected work unchanged. No forced update/restart on S2.

The real post-rollout lifecycle **stopped before correction/forget**: canonical recall was still empty, so no full memory pass was claimed. Diagnosis: baremarker search returns1exactfact; conversational-wrapper queries each return10unrelated/common-word hits and omit it. Bare GET11.2s on loadedS1 also exceeds client3.5s. Followup under scoped claim6842961865 normalizes only anchored recall questions, grants read-only search a15s default (mutation timeouts/retries unchanged), validates response schema, and treats shared-empty as authoritative rather than resurrecting stale local mirrors. Pre-fix14testbattery13failed/1passed; combined after149passed/1warning,exit0. This remains unaccepted until new exact-head CI/rollout/actual lifecycle succeeds.

Actual united handoffs now observed: ZAI1 comment6842902784 voice-room/UI; ZAI2 comment6842900038 requested PR73review. Arena acknowledged6842926913 and posted substantive PR73review6842926459 (PF1.16-vs1.19selector, missing1d/timeframe-transfer, reused OOS selection, raw artifacts/reconciled execution). ZAI1 main908167e/63f2108 preserved; no edits in their voice/UI/Stratex lanes. No invented agreement on new assignments. Four sampled research excerpts match official pages; answer relevance stillpartial. Actual video adapter classified refresh_failed,tokenpresent; no underlying invalid_grant asserted, no publication.

### CI correction before merge

First PR74 headf6a4a8c failed Owner Workflow Contracts:395passed/1failed because an existing regression deliberately supplied timeout3.5 and the draft15s floor overrode it. No merge/deploy on red. Changed the implementation, **not the existing test**: omitted timeout now defaults to3.5mutations/15sreads; an explicitly supplied timeout remains honored for both unless recall_timeout is separately set. Three additional controls pin explicit3.5/0.9 and separate12s read budget. Combined166passed/1warning,exit0, including the formerly failing hardening battery. Fresh exactheadCI required again.

## Actual lifecycle result and continuing mutation-safety gate

PR74 final42784b7 passed7checks/2conditionalDocker skips; mergeb80002d8; deploy43360913746SUCCESS. S1updated; S2correctlypathskipped.166localtests passed before rollout, explicit timeoutcontract retained without weakening the existinghardeningtest. Realcanonicalrecall now finds original marker. Guarded real MemoraClient correction returned corrected/cloudtrue; distinct shared-durableOracle candidatec154411b-8b41-4f1a-ad7a-8efc55b76eed, old60a97947-99e8-4812-8b1d-64123fde7750 superseded/newactive. Freshprocessrecall andcanonicalbridge return ONLY revisionone. ExactnewID DELETE accepted; freshOraclequery confirmsdeleted; freshshared/canonicalrecall empty. ExactoldIDcleanup accepted; finalfreshOraclequery confirmsBOTHsyntheticrowsdeleted. No broadownermemorymutations. Runtime3.10.12/proofrevisionb80002d8.

Private finalproof `/var/tmp/friday-workflow-acceptance/wf015-lifecycle-final.json`. Raw after-recall/reconciliation journals retain partial_failure: harness wrongly expected deletedGETreadable then404, but actualnew404/old403visibility. Reconciled exactOraclestates without repeating either DELETE; no fakepass or overwrittenfailedrecord. A local exportNameError occurred AFTER finalproof was written remotely; repaired via read-onlyexport, not rerunning mutations. Client lifecycle/canonicalrecall is verified; full canonical conversational correction/forget was NOT yet tested in that run.7S1/6S2protectedfilesunchanged, tracked/indexclean.

CONTINUING scoped claim6843332553: offline synthetic-only regressions reproduce unrelated topsemantic-hit DELETE andsupersede (2fails,zero realnetwork). New repair requires a unique lexicalsubject; searches stablecorrectionsubject notnewvalue; ambiguity asksclarification; contextless forget-that never substitutes ownerpreferences; sharedDELETEuncertainty never certifiedbylocalmirror; canonical local/shared/notapplied/unknown replies remain honest anddo not inviteblindretry. Only memoryclient/canonicalforget-correctiongates/newtests; ZAI1livekit/UI andZAI2Stratex untouched.181focused/existingtests pass exit0/1existingwarning; real canonicalmutation acceptance and freshCI/rollout remain pending. SourceRuffF821/E9 clean (server has pre-existingunusedimports, not swept). New main835fe0c voiceEndcallguard preserved. Research relevance, ownermicrophone/OAuth/review andsustainedreconciledprofit gates remain open.
