# TASK-INT-050 — Evidence: live watch-cycle verification, wave 3

- Task: PRODUCTION-VERIFY IntelX corpus items IG2-INT-03, IG2-INT-04, IG2-INT-05, IG2-INT-06 — live watch-cycle verification (wave 3), P2.
- Claim: hub #2045 comment 7236167865, 2026-11-28 ~13:17 IST, on WATCH262 §C assignment (hub 7236059938: "M7 → TASK-INT-050"). Board on main `d7c30e75ff0712379b50defa3af4a057200ddeb7` verified first-hand this run: INT-050 AVAILABLE / owner muse_5 (stale; flip rides WATCH263), branch null, pr null. Branch `muse7/task-int-050-intelx-wave3-verify` created from main `d7c30e75`.
- Live host: IntelX-Server (server 6, `ip-172-26-4-138`), `/opt/friday_universe`. `IntelX.service` active, MainPID 46018, started 2026-11-27 05:13:15 UTC (uvicorn `intelx.app.main:app` :8005). Probe window 2026-11-28 07:50–07:52 UTC (~13:20–13:22 IST), via bridge `run_shell` on server 6, deployed venv (`/opt/friday_universe/venv/bin/python`, cwd `/opt/friday_universe/IntelX`). Read-only probes plus outbound reads; no config changed, no restart, no server move.
- Health: `/healthz` 200 (mock_mode false); `/health` 503 degraded-by-design (capabilities unknown, NO_LIVE_PROBE / CONFIG_ONLY; database connected) — the known report, unchanged.
- Method note: mirrors TASK-INT-049 (PR #2070): each item exercised through the deployed service's own code, with a failure case per item, plus a fresh watch-cycle observation and a deploy-drift check. Local test re-runs rest on main CI (`test` success on `d7c30e75`, verified first-hand; 12 success / 1 skipped / 1 failure — the failure is `Deploy Specialist Fleet (Server 2)`, a deploy job, not a test job; 2 infra jobs in progress).

## Per-item live verdicts

### IG2-INT-03 — Helix on-demand username lookup — LIVE FAIL (real-fetch leg)

- Gate verified live: `helix_lookup` with an unapproved subject raised `PermissionError` with **0 fetches** before refusal — no gate, no scan, no network traffic.
- Discipline verified on live code (injected fetch): found hit caps at LOW; control-probe false positive discarded (0 hits, 1 discarded, overall NONE); blocked platform (403) reported as unknown, never as absence. Control username deterministic and distinct per subject. Curated platform list: 12.
- Real-fetch leg FAILED: bounded scan of the impossible control username only (no person scanned; `INTELX_HELIX_APPROVED_SUBJECTS` absent from `.env` and process env, so no owner-approved subject exists to scan) returned **5/5 unknown, 0 hits** (GitHub, GitLab, Keybase, Reddit, Mastodon). Root cause reproduced first-hand: the production `HttpFetchConnector` raises `HTTPStatusError` on 404 (`web.py:375 raise_for_status`), while `helix_lookup._default_fetch` expects a `(status, final_url, content)` tuple and `_verdict` maps 404 → `not_found`. GitHub/Keybase/Mastodon control URLs correctly return 404 (curl from the same host confirms 404), but the connector raises, so every absent profile reads "blocked or inconclusive". GitLab (403 sign-in wall) and Reddit (403, 0 bytes) are genuinely inconclusive. Net: **absence is never provable through the live fetch path** — a real defect, not a probe artifact.
- Production API leg NOT deployed: live `osint_tools.py` blob `e4bb74c9` drifts from main `34e27be1`; `grep -c username-lookup` live = 0; OpenAPI (179 paths) has no username-lookup path; `helix_watch.py` ABSENT live. The INT-051 route (`POST /osint/username-lookup`) exists on main only.
- Named fix task filed from this record: **TASK-INT-050-FIX-01** — repair the Helix fetch contract (map connector 404 to `not_found` instead of raising into unknown; keep 403/bot-wall as unknown) and deploy the INT-051 username-lookup wiring (`osint_tools` + `helix_watch`) under coordinator clearance. Until then IG2-INT-03 is not production-verified.

### IG2-INT-04 — Robin pipeline + untrusted-data hygiene — LIVE PASS (core)

- Hygiene verified live: `strip_invisible` removed zero-width/bidi/control/BOM characters exactly (`"hello world\nnext\tline"` preserved); `wrap_untrusted` defused a forged `<<<END_UNTRUSTED_DATA>>>` delimiter (`[delimiter removed]`, exactly one closing delimiter, `is_wrapped` true); `refine_query` kept the quoted phrase and built 4 pivots.
- Pipeline verified on live code (injected search/fetch): 1 evidence item returned wrapped-only, 2 dropped (irrelevant page + unfetchable page), zero-width character stripped from evidence text.
- Live clearnet leg: `HttpFetchConnector().fetch("https://example.com/")` → 200, 577 bytes, "Example Domain" present, hygiene-wrapped successfully — the production connector + hygiene path works end-to-end on a real fetch.
- Wiring present live: `osint_tools.py` imports and calls `run_investigation` (lines 167/169); OpenAPI carries `POST /api/v1/research/investigations`.
- Drift note (extension, not core): the INT-051 saved-investigation extension is NOT deployed — `investigation_store.py` ABSENT live, no `GET /research/investigations/{id}` or follow-up route in OpenAPI. Core IG2-INT-04 passes; the saved-investigation routes ride the same coordinator deploy leg as FIX-01's wiring.

### IG2-INT-05 — AI-trending Radar feed — LIVE PARTIAL (3 of 4 sources fail live)

- Library verified live on real feeds: `AiRadar().poll_once()` ingested **919 fresh items** from `hf_blog` (271,990 bytes, HTTP 200), trends computed (top: "hugging face" score 52.0, 52 mentions), second poll returned **0 fresh** (dedupe holds), and a deliberately bad source was reported honestly (`SSRFBlockedError` in `source_status`, 0 items — never silently filled).
- Source failures (real defect): `arxiv_cs_ai`, `arxiv_cs_cl`, and `hacker_news` each returned **403 with 0 bytes** through the production `HttpFetchConnector`, surfacing as `unparseable feed: no element found` in `source_status` — while plain curl from the same host returned **200** for all three (arXiv 892 bytes, HN 11,527 bytes). `web.py` matches main exactly, so the defect is in the main connector's request profile toward these hosts, not deploy drift. The radar's honesty contract held (failures reported, nothing invented), but 3 of 4 named sources cannot be polled in production.
- Standing leg not running: `GET /api/v1/feeds/ai-radar` → 200 with `items_buffered: 0`, `last_poll_at: null` on all four sources; `ENABLE_AI_RADAR` absent from `.env` and process env. The route is live; the standing instance has never been driven.
- Named fix task filed from this record: **TASK-INT-050-FIX-02** — repair the connector request profile so arXiv/HN feeds poll successfully (200 with content, as curl achieves), then enable/drive the standing radar loop under coordinator clearance. Until then IG2-INT-05 is production-verified only for the hf_blog source path.

### IG2-INT-06 — HaveIBeenPwned breach checks — LIVE PASS

- Password leg real and live (k-anonymity, synthetic inputs only): weak synthetic → `checked True, found True, occurrences 52,373,976`, prefix `5BAA6` (only the 5-char prefix left the host); random synthetic → `checked True, found False, occurrences 0`. Both directions proven against the real Pwned Passwords range API.
- Email leg fail-closed as designed: `check_email_breaches("a@example.com", api_key="")` → `status unavailable, checked False`, 0 breaches, reason states the paid-key requirement; the fetcher was never called (asserted). `HIBP_API_KEY` absent from `.env` and process env — no key exists, and the check never fabricates "no breaches".
- No standalone breach route in OpenAPI (by design: the breach section embeds in the footprint audit). Library-level production verification stands.

## Watch-cycle observation (fresh, 2026-11-28 ~13:20 IST)

- Cycles alive: journal shows 30-min cadence all morning (05:15, 05:45, 06:15, 06:45, 07:15, 07:45 UTC), every cycle `alerted=0` on both watches (latest 07:45 UTC: `ai_model_releases fetched=2369 alerted=0 dup=2369`; `india_tech_regulatory fetched=64 alerted=0 dup=60 below=4`). `state.json` mtime 2026-11-28 07:45:27 UTC.
- Outbox: 6 envelopes, all `digest`, scores [4, 5, 3, 4, 4, 3], max 5 (instant bar 6); newest fired 2026-11-27 21:44:43 UTC. `instant_outbox.jsonl` ABSENT. State unchanged since INT-061 (~09:18 IST today).
- Envelope-recency clause: FAILS again — the cycle runs but has produced no alert in ~13 hours; no item's alert leg is proven by observation (same finding as INT-049/INT-061).

## Deploy drift (13-file check vs main d7c30e75)

- 10/13 match main exactly: all four item modules (`helix_lookup.py`, `breach_check.py`, `ai_radar.py`, `untrusted_ingest.py`), all four IG2 test files, `feeds.py`, `web.py` (git blob hashes computed on live files; `/opt/friday_universe` is not a git checkout).
- 3 drift: `osint_tools.py` (live `e4bb74c9` vs main `34e27be1` — predates INT-051 wiring), `helix_watch.py` ABSENT, `investigation_store.py` ABSENT. The item libraries are current; the INT-051 API wiring layer lags.

## Held leg — NOT run (no clearance)

- Duplicate/flood burst + one real alert end-to-end per item: HELD. WATCH262 grants no burst/alert clearance for INT-050, and the owner stop order (in force since 2026-11-24) has no lift for this task in anything read this run. Triggering a burst and dispatching a real alert is a live write on the production service — not run without explicit coordinator clearance (same ruling as INT-049).
- Person-scan leg for IG2-INT-03: not run — no owner-approved subject is configured; only the impossible control username was scanned.
- Ask to Muse (coordinator): (1) file TASK-INT-050-FIX-01 (Helix fetch contract + username-lookup wiring deploy) and TASK-INT-050-FIX-02 (radar connector 403 + standing loop) from this record; (2) grant or deny the burst/alert live leg for INT-050; (3) rule whether INT-050 closes as PARTIAL with the two fix tasks carrying the failing legs, or stays open until they land.

## Five states

- implemented YES (all four items MERGED: PRs #718/#722/#723/#731) / tested YES (live exercises above, 2026-11-28 ~13:20 IST; `test` success on main `d7c30e75`) / merged YES / deployed PARTIAL (item libraries + tests match main; INT-051 wiring layer stale/absent; standing radar loop off) / production-verified PARTIAL (IG2-INT-04 YES, IG2-INT-06 YES, IG2-INT-05 PARTIAL — hf_blog path only, IG2-INT-03 NO — fetch-contract defect + route absent; alert/burst leg HELD, envelope-recency FAILS).

## Files

- This evidence doc: `docs/collaboration/TASK-INT-050-EVIDENCE.md`
- Board record: flips ride the coordinator board PR (WATCH263); no board hunk in this PR.
- Probe outputs (working state): `~/workspace/goals/muse-7-onboarding-for-friday-universe/hidden_files/int050_probe_1316.txt`, `int050_probe2_1316.txt`, `int050_probe3_1316.txt`

— Muse 7
