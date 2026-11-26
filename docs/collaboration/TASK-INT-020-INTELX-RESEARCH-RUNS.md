# TASK-INT-020 — IntelX: prove research-with-sources through FRIDAY chat, 3 consecutive live runs (M5 workflow 2)

**Worker:** Muse 13. **Claim:** hub #1483 comment 7161993563, 2026-11-25 ~17:45 IST, on coordinator assignment in WATCH097 (7161378423) — queue head after TASK-INF-037 merged; VOI-030 stays blocked-head skipped. **Branch:** `muse13/task-int-020-intelx-research-runs` @ main e0373ced. **Usage at claim:** 37% of free weekly limit, reset Nov 29 6:09 PM IST.

**Status of this document:** CHECKPOINT 2 — RUN 1 ATTEMPTED THREE TIMES VIA THE LOOPBACK ROUTE, ALL THREE FAILED HONESTLY (count 0/3). The webchat owner-key gate (§6) was resolved by coordinator ruling WATCH099 (7162851838): run via loopback `/api/chat` on FRIDAY-Server. All three loopback attempts failed at the same synthesis stage — `synthesis_entailment_unverified` — two topics, three stored DEGRADED runs. A fix task for the synthesis/entailment stage is owed; no further attempts until it lands. See §7.

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

- **Route (revised by WATCH099 ruling, 7162851838):** loopback `POST /api/chat` on FRIDAY-Server (server 3) — `curl http://127.0.0.1:10000/api/chat` with `{"message": "..."}`, no credential (loopback callers stay keyless per the D-023 gate; the deployed code is behind main but the loopback route was proven live by Muse 1's FRD-053 legs the same day). That IS the FRIDAY chat surface; the webchat owner-key gate is a UI-layer gate, not the chat route. No key invented, no credential read, no dispatch-bus route. The webchat route (§6) is superseded.
- **Run 1 brief (chosen):** "research the latest AI model releases and give me the highlights with sources" — the same topic as INF-028's green bus re-probe, so a failure isolates the chat route / synthesis stage rather than the research path.
- **Run 2/3 briefs:** fresh current topics, chosen at run time (no repeats of a failed brief verbatim — except a same-brief retry to test flakiness, recorded as an attempt, not a pass).
- **Trace per run (filed in this doc):** request text + timestamp, routing (loopback /api/chat → FRIDAY → IntelX), agent evidence (IntelX run id + archive status, synthesis status, findings/sources counts), verbatim reply (or its honest failure), wall time. A run passes only if the reply carries real sourced highlights; a wrong answer presented as success, a dropped result, or a fabricated status resets the count to 0.
- **Known risk (now realised):** the synthesis stage fails live on the chat route — see §7.

## 5. Five states

Implemented n/a (proof task, no code) / tested — / merged NO / deployed n/a / production-verified NO — 0/3 runs; three loopback attempts failed honestly at the synthesis stage (§7). A synthesis/entailment fix task is owed before further attempts.

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
- **Answered by WATCH099 (7162851838, ~18:15 IST):** "run it via loopback /api/chat on FRIDAY-Server — the same route Muse 1 used for FRD-053's 8 live legs (real FRIDAY replies, journal proof). That IS the FRIDAY chat surface; the webchat owner-key gate is a UI-layer gate, not the chat route. No key invented, no credential read, no route change to the dispatch bus. Proceed with runs 1-3 and file traces." The webchat route is superseded; §7 is the loopback record.

## 7. Loopback attempts — run 1, three honest failures (count stays 0/3)

Route for all three: bridge `run_shell` server 3 (FRIDAY-Server), `curl -s -m 420 POST http://127.0.0.1:10000/api/chat -H 'Content-Type: application/json' -d '{"message": "..."}'`. No credential used, none read. FRIDAY.service active throughout (MainPID 40483); journal shows each turn processed and `POST /api/chat` from 127.0.0.1 → 200. IntelX on IntelX-Server did real research each time (Tavily + Google News RSS 200, source fetches, synthesis call to Inference 200) and persisted a DEGRADED run. All three replies are verbatim-identical; no highlights were fabricated in any attempt. No reset: an honest failure does not reset the count — only a wrong answer presented as success would.

### Attempt 1a — AI model releases (2026-11-25 ~19:14 IST / 13:14 UTC)

- **Request:** "Friday, research the latest AI model releases and give me the highlights with sources."
- **Result:** HTTP 200, 70.9 s wall (dispatch 67.4 s). **Reply (verbatim):** "IntelX could not complete that research: sourced_findings_unverified. That is the real outcome — no highlights were fabricated." Metadata: `task_state: FAILED`, `probe_success: false`, `intelx: null`, `sources: []`, `research_dispatch: true`.
- **Stored run:** `lr_c5f08d9c5b2e4320be6d31d6` (IntelX `live_research_runs`, read back via the service's own `fetch_live_research`): status DEGRADED, synthesis_status **failed**, answer_kind `unsynthesised_raw_findings`. Summary: "Retrieved 5 source document(s); synthesis failed (synthesis_entailment_unverified) — returning 15 unsynthesised raw finding(s) (verbatim source excerpts), not a synthesised brief." Receipt: None.
- **Journal (IntelX-Server, 13:14 UTC):** Tavily search 200, Google News RSS 200, source fetches incl. one 403 (`/releases/model`) and one robots ConnectTimeout (labla.org, fetch denied until retried); synthesis POST to Inference 200; "live research persisted run_id=lr_c5f08d9c5b2e4320be6d31d6 status=DEGRADED".

### Attempt 1b — same brief, flakiness retry (~19:20 IST / 13:20 UTC)

- **Request:** same brief verbatim (retry to test whether 1a was flaky).
- **Result:** HTTP 200, 55.6 s wall (dispatch 53.2 s). **Reply (verbatim):** identical to 1a. Metadata identical in substance (`task_state: FAILED`, `sources: []`).
- **Stored run:** `lr_365e94dd989243e296c64915`: DEGRADED, synthesis **failed**, `unsynthesised_raw_findings`. Summary identical in substance: 5 source documents, synthesis failed (`synthesis_entailment_unverified`), 15 unsynthesised raw findings.
- **Verdict:** not flaky on this brief — same verdict twice.

### Attempt 1c — different brief, SpaceX Starship (~19:25 IST / 13:22 UTC)

- **Request:** "Friday, research the latest SpaceX Starship test flight news and give me the highlights with sources."
- **Result:** HTTP 200, 34.8 s wall (dispatch 32.5 s). **Reply (verbatim):** identical to 1a/1b. Metadata identical in substance (`task_state: FAILED`, `sources: []`).
- **Stored run:** `lr_b10f970668fa4fd78519d441`: DEGRADED, synthesis **failed**, `unsynthesised_raw_findings`. Summary: "Retrieved 1 source document(s); synthesis failed (synthesis_entailment_unverified) — returning 3 unsynthesised raw finding(s)."
- **Verdict:** not topic-specific — the synthesis stage fails on a second, unrelated brief with a different source set.

### Diagnosis

- The failure is in the **synthesis/entailment stage** (`synthesis_entailment_unverified`), not retrieval: sources are retrieved and fetched (5 docs / 15 findings in 1a–1b, 1 doc / 3 findings in 1c), the synthesis call to Inference returns 200, but entailment verification fails and the run degrades to raw excerpts — which FRIDAY then honestly refuses to present as a brief.
- This is the **same verdict INT-033 was filed to fix** (11/11 live runs DEGRADED before the fix; fix = false-negative-only tokenisation repairs in `grounded_live_research.py`, merged PR #1511, deployed, INF-028 bus re-probe green 2026-11-24 01:43 IST, run `lr_70c54f7c36604cbeb9922c8b`). The deployed file on IntelX-Server carries exactly the INF-028-verified hash (§3), so the fix IS live — yet the verdict persists on the chat route.
- **Open question (not adjudicated here):** why the bus re-probe passed on 2026-11-24 (S2 IntelX) while the chat route fails on 2026-11-25 (IntelX-Server). Candidates: the route (chat vs bus) reaches a different synthesis path/model; the IntelX home move (S2 → server 6) changed something the hash check does not cover (env, model, synthesis budget); or the entailment check still false-negatives on statement shapes outside INT-033's three repairs. No cause is claimed — the evidence above is what the live systems returned.
- **Follow-up owed:** a fix task for the synthesis/entailment stage on the live chat route (INT-033 follow-up), assigned by the coordinator. Further INT-020 attempts are held until it lands — three identical failures are enough evidence; more retries would burn usage without new information.
- **Note:** FRIDAY's chat reply labels the failure `sourced_findings_unverified`, while the stored IntelX run records `synthesis_entailment_unverified`. Both describe the same DEGRADED outcome; the label mismatch is recorded, not resolved.

— Muse 13
