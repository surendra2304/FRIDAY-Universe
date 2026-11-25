# TASK-INT-020 — IntelX: prove research-with-sources through FRIDAY chat, 3 consecutive live runs (M5 workflow 2)

**Worker:** Muse 13. **Claim:** hub #1483 comment 7161993563, 2026-11-25 ~17:45 IST, on coordinator assignment in WATCH097 (7161378423) — queue head after TASK-INF-037 merged; VOI-030 stays blocked-head skipped. **Branch:** `muse13/task-int-020-intelx-research-runs` @ main e0373ced. **Usage at claim:** 37% of free weekly limit, reset Nov 29 6:09 PM IST.

**Status of this document:** CHECKPOINT 1 + RUN 1 ATTEMPTED — run 1 blocked at the FRIDAY webchat owner-key gate (no brief produced, count 0/3). Block posted on #1483 (comment 7162173741); direction requested from Muse. See §6.

## 1. Acceptance (board record, verbatim substance)

Three consecutive live runs: a real IntelX research brief with sources retrieved through FRIDAY chat, each run recorded with its trace (request, routing, agent evidence, result); a wrong answer presented as success resets the count. (MASTER_PLAN M5: a workflow counts as proven only after 3 consecutive successful live runs on production, each recorded with its trace; a silent failure — a wrong answer presented as success, a dropped result, a fabricated status — resets that workflow's count.)

## 2. Prior state — the count is 0/3 (reconstructed first-hand)

Muse 7 held INT-020 before me (claim #35 comment 7081992323, 2026-11-22 ~21:50 IST; claim PR #1392; branch `muse7/task-int-020-intelx-research-runs`, now deleted from remote — 404 on ref read). No INT-020 evidence doc was ever filed; the run history below is reconstructed from Muse 7's hub posts on #35, read first-hand this run.

| Run | When / route | Brief | Outcome | Count after |
|-----|--------------|-------|---------|-------------|
| 1 | 2026-11-22 21:59:55 IST, FRIDAY web chat | RBI latest repo rate decision, highlights with sources | FAILED honestly — FRIDAY replied IntelX could not complete the research (ConnectError, no highlights fabricated). Root cause: stale `FRIDAY_INTELX_URL=http://127.0.0.1:8005` in the S1 FRIDAY env (hub 7082234516) | 0/3 |
| 2 | 2026-11-22 23:27:48 IST, FRIDAY web chat | Latest US Fed interest rate decision, highlights with sources | FAILED honestly — findings produced (5 docs, 15 findings) but `sourced_findings_unverified`; stored run `lr_7d551ec705b24dcbab1fceb9`, DEGRADED (hub 7083259460, 7084161789) | 0/3 |
| 3 | — | — | Never run. Waited on INT-021, then on the Gemini 503 synthesis fix (INF-026), then on the entailment fix (INF-028 / INT-033). Task re-slotted to Muse 13 by WATCH097. | 0/3 |

**Blockers that stood between run 2 and run 3 — all cleared before my claim:**

- FRD-036 (Muse 9): env fix — `FRIDAY_INTELX_URL` 127.0.0.1:8005 → 10.0.0.120:8005 (+3 more stale URLs); deployed 2026-11-22 22:45–22:54 IST, FRIDAY restarted 22:51:13 IST. (Hub 7082890155.)
- INF-026 (Muse 9, MERGED PR #1441): Gemini 503 on the synthesis path diagnosed (Groq size-guard diversion + gemini-3.8-flash 503 high-demand) and fixed (synthesis budget 16,000 → 14,000 chars, servability tracker, fallback provenance). Deploy evidence PR #1447.
- INT-033 (Muse 9, MERGED PR #1511, merge cfe211cf 2026-11-23 21:10 IST): `synthesis_entailment_unverified` root-caused — three tokenisation defects in `statement_support` (`IntelX/intelx/api/grounded_live_research.py`); fix is false-negative-only repairs (unicode normalisation, trailing-punctuation strip, substring coverage). 11/11 live runs had been DEGRADED before the fix.
- INF-028 (Muse 9, MERGED PR #1561): fix deployed to live IntelX (S2, restart 2026-11-24 01:05:58 IST); synthesis re-probe GREEN — bus run 2 completed, synthesis succeeded, entailment + quotes verified, archive and bus agree (`lr_70c54f7c36604cbeb9922c8b`). Verdict: "`synthesis_entailment_unverified` is gone from the live path. INT-020 run 3 itself is Muse 7's to run — unblocked on the IntelX side."

**Board record note:** TASK-INF-027 (the INF-026 follow-up named in INF-026's evidence) has NO board record on main e0373ced — not my task, flagged here only so the coordinator can re-file it if still owed.

## 3. Live-path recon this run (bridge `run_shell`, read-only, 2026-11-25 ~17:55–18:00 IST)

The fleet has moved since the Nov 22–24 evidence: FRIDAY and IntelX no longer run on S1/S2.

| Check | Result |
|-------|--------|
| S1 `FRIDAY.service` | inactive (dead), MainPID 0 — **expected**: FRIDAY moved to FRIDAY-Server |
| S2 `IntelX.service` | inactive (dead), MainPID 0 — **expected**: IntelX moved to IntelX-Server |
| FRIDAY-Server (server 3, `friday-server`) `FRIDAY.service` | **active, running, MainPID 40483**, listening on :10000 |
| FRIDAY-Server env | `INTELX_URL=https://friday-universe.duckdns.org/intelx`, `FRIDAY_INTELX_URL=https://friday-universe.duckdns.org/intelx` — public-gateway path, not the old S2 IP |
| IntelX-Server (server 6, `ip-172-26-4-138`) `IntelX.service` | **active, running, MainPID 4973**; `/health` 200, `mock_mode: false`, database connected, status `degraded` (by-design `NO_LIVE_PROBE`) |
| IntelX-Server deployed `grounded_live_research.py` | sha256 `c3a39b2d8b06871d8ab02c3a1e92552b128e05279fbdbafab4d7178d7e9e9eab` — **exactly the INF-028-verified hash**; `_normalize_text` count 3 — the INT-033 fix IS live on the current IntelX home |
| S2 on-disk file (same path) | Same sha256 — the S2 tree still carries the fix, but S2 is not the live IntelX anymore |

No config changed, no restart, no key read, no service touched. Read-only recon only.

## 4. Run plan

- **Route:** FRIDAY webchat (`https://friday-universe.duckdns.org/friday/` — the owner's path, same route Muse 7 used for runs 1–2), driven through the live browser. One research brief per run; the full verbatim reply is captured with its sources and timing.
- **Run 1 brief (chosen):** "research the latest AI model releases and give me the highlights with sources" — the same topic as INF-028's green bus re-probe, so a webchat failure would isolate the chat route rather than the research path.
- **Run 2/3 briefs:** fresh current topics, chosen at run time (no repeats of a failed brief verbatim).
- **Trace per run (filed in this doc):** request text + timestamp, routing (webchat → FRIDAY → IntelX), agent evidence (IntelX run id + archive status, synthesis status, findings/sources counts), verbatim reply (or its honest failure), wall time. A run passes only if the reply carries real sourced highlights; a wrong answer presented as success, a dropped result, or a fabricated status resets the count to 0.
- **Known risk:** the webchat may require a sign-in the detached browser run cannot complete — if so, that is reported as a blocker with evidence, not worked around by switching to the dispatch-bus path (the bus path is a different route from the acceptance's "through FRIDAY chat").

## 5. Five states

Implemented n/a (proof task, no code) / tested — / merged NO / deployed n/a / production-verified NO — 0/3 runs; run 1 blocked at the owner-key gate (see §6).

## 6. Run log

### Run 1 — BLOCKED at the owner-key gate (no brief, count stays 0/3)

- **When:** 2026-11-25 17:45:46 IST (browser task ran 17:45–17:46 IST, runtime-measured).
- **Route:** FRIDAY webchat `https://friday-universe.duckdns.org/friday/`, live browser.
- **Request (verbatim):** "Friday, research the latest AI model releases and give me the highlights with sources."
- **Reply (verbatim, same second, 17:45:46 IST):** "I need the owner key in this browser before I can answer. Paste it once below."
- **Page state:** loaded normally (FRIDAY, LIVE, LINK STABLE), no sign-in page or error before sending. After the reply, a "Connect to FRIDAY" panel: "FRIDAY needs the owner key in this browser before it can answer. Paste it once — it stays in this browser and is never sent anywhere except to mint a short-lived session." Owner-key textbox (placeholder "Paste the owner key...") + "Connect" button (disabled until a key is entered).
- **Wait:** 30 s more after the reply (until ~17:46:32 IST) — no additional reply, no research content. Not a partial answer.
- **Sources/citations:** none. No highlights, no sources.
- **Wall time:** under 1 s to the gate reply.
- **Verdict:** BLOCKED, not a pass or a fail of the research path. The gate is new since Muse 7's runs (Nov 22 the webchat answered without a key). No key invented or supplied; no switch to the dispatch-bus or any other route (acceptance requires "through FRIDAY chat").
- **Direction requested** on #1483 (comment 7162173741): (a) owner key through a secure channel for this run, (b) dispatch-bus path accepted as the run route, or (c) another route Muse names. The live path underneath is verified healthy (§3 + INF-028's green bus re-probe) — the block is the chat gate only.

— Muse 13
