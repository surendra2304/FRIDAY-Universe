# TASK-INT-049 — Evidence: live watch-cycle verification, wave 3 (run 2)

- Task: PRODUCTION-VERIFY IntelX corpus items IG-INT-05, IG-INT-06, IG2-INT-01, IG2-INT-02 — live watch-cycle verification (wave 3), P2.
- Claim: hub #2045 comment 7210009999, 2026-11-27 ~10:11 IST, on direct coordinator direction (WATCH202 §4: "M4: claim INT-049 next on your work-request"). Board on main `99e5fe12` verified first-hand this run: AVAILABLE / owner muse_4, M6 branch retained for adoption.
- Probe base: main `99e5fe12` (blob `5b60a050ab`, 25,575 lines). PR base: main `c334f212` (board PR #2069 merged after the probe; `WORK_BOARD.yaml` +47/-37 only — no item file changed, so all probe hashes still hold).
- Live host: IntelX-Server (server 6, `ip-172-26-4-138`), `/opt/friday_universe`. `IntelX.service` active, MainPID 35285, started 2026-11-26 06:32:44 UTC (uvicorn `intelx.app.main:app --port 8005 --workers 1`, WorkingDirectory `/opt/friday_universe/IntelX`). Probe window 2026-11-27 04:42–04:55 UTC (~10:12–10:25 IST), via bridge `run_shell` on server 6.
- Prior art: Muse 6 checkpoint 1 (repo scoping, 41/41 tests) + checkpoint 2 (live observation 2026-11-26 ~11:15 IST: browser_sidecar drift, registry 102, envelope-recency fail, soak synthesis failed). This run re-probes everything first-hand; M6's findings are carried only where re-verified below.
- Method note: this VM's local test re-run and local git operations were blocked this run by an execution-risk check on the worktree checkout. Mitigations: repo tests rest on M6's first-hand 41/41 re-run (checkpoint 1) + CI on main `99e5fe12` verified green first-hand this run (14 check-runs: 11 success + 3 skipped, 0 failed; `test` success). Branch/commit/PR filed via the GitHub git-data API, no local git.

## Per-item live verdicts

### IG-INT-05 — named research/archive source utilities — LIVE PASS (with drift note)

- Live code exercised through the deployed service's own venv (`/opt/friday_universe/venv/bin/python`, cwd `/opt/friday_universe/IntelX`):
  - `ArchiveOrgClient.search("collection:prelinger", rows=3)` → 3 real rows: `EnglishC1949` (English Children: Life in the City, movies), `Everyday1948`, `EasyDoes1940`.
  - `ArchiveOrgClient.metadata("EnglishC1949")` → title "English Children: Life in the City", 43 files.
  - `metadata("this-identifier-does-not-exist-xyz123")` → `None` (honest not-found signal, verified live).
  - `WolframAlphaClient` → `configured: False`; `query()` raises `NamedSourceUnavailable` ("WolframAlpha requires an AppID... No result was fabricated in its place") — fail-closed live.
  - Registry live: 5 sources, kinds honest (Internet Archive api_keyless, WolframAlpha api_keyed, OpenCulture / AlternativeTo / JustWatch seed_site).
- Drift note: live `named_sources.py` blob `5ebadfe4` = commit `65a123c4` (2026-11-15, the original IG-INT-05 commit). Main's blob `5239652e` adds two later sources (INT-046 Telegram, commit `97f012cb` 2026-11-26; INT-047 Tor Metrics, commit `0c19cc45` 2026-11-27). The IG-INT-05 functions themselves are intact and verified live; the file predates two other tasks' additions.

### IG-INT-06 — scouted repo registry — LIVE PASS

- `intelx.scouted_repos.summary()` on the live service → `count: 102`, fit_counts adopt 6 / adapt 40 / reference-only 46 / reject 10; entries loaded 102. Matches main's registry exactly (file blob matches main `a18c2403`).
- Verdict: the 102-entry registry is live on the deployed service.

### IG2-INT-01 — on-demand camofox sidecar — LIVE FAIL (blocked, not a code failure)

- `SidecarConfig.from_env()` live: `enabled: False`, `base_url: http://127.0.0.1:9377`, no start command. No `INTELX_CAMOFOX_*` key in the unit environment or in `IntelX/.env`. Nothing listens on 9377. No camofox binary on the host.
- `CamofoxClient.health()` → `False`. `BrowserSidecarConnector.fetch("https://example.com/")` → status 0, error "camofox sidecar unavailable (not running and no start command configured)" — fail-closed as designed.
- `detect_bot_wall(403, cloudflare, empty body)` → `is_wall True, suspected, cloudflare` — the bot-wall detection half is verified live.
- Drift note: live `browser_sidecar.py` blob `19634494` = commit `2ee30c1a` (2026-11-16, the original IG2-INT-01 commit). Main's blob `0ac04c8e` is commit `c11dbeb9` (2026-11-25, TASK-INT-051: +43 lines, `fetch_macro` + `fetch_transcript`). The live module is the original sidecar code; the INT-051 additions are absent live. A re-sync + service restart is owed (route proposed in M6 checkpoint 2; still needs coordinator clearance — not granted in WATCH201/202).
- What unblocks it: coordinator clearance + owner decision to install/enable the sidecar on IntelX-Server (Camoufox binary ~300MB disk; service memory cap ~180MB — the module itself says the intended hosts are the owner's machine or the future ARM server). Until then no bot-walled fetch can run on this host, by design.

### IG2-INT-02 — iterative deep-research loop — LIVE PASS

- Bounded live run via the deployed service's venv: `IterativeDeepResearcher(WebSearchConnector(), max_rounds=2, max_sources=6, min_quality=0.60, min_sources_per_item=1, max_queries_per_round=4, results_per_query=4).research("RBI proposes stop switch to block digital payment frauds", ["What safeguards did RBI propose?", "When does the stop switch apply?"])`.
- Result: `stop_reason: coverage_complete`, coverage 1.0, 6 sources, 1 round, 6.833 s. Round 0: 2 queries, 8 results seen, 6 kept, 0 dups, 0 low-quality rejections, 0 search failures.
- Sources are real live feeds (not fixtures): Economic Times (2), India Today, Google News RSS, Instagram, honyone.com — quality 0.74–0.77, medium bucket. Extractive cited brief saved on the server at `/tmp/int049_deepresearch.md`; both subquestions covered.
- Nuance (honest): one cited snippet for "When does the stop switch apply?" is off-topic industrial content (honyone.com emergency-stop-switch page) that still passed the 0.60 quality bar. The loop ran correctly on live feeds; the coverage metric is mechanical and one citation is weak. Not a code failure — recorded for the verifier.

## Watch-cycle observation (fresh, 2026-11-27 ~10:18 IST)

- Cycles alive: journal shows `[Watch:ai_model_releases] fetched=2368 alerted=0 dup=2368` and `[Watch:india_tech_regulatory] fetched=64 alerted=0 dup=63 below=1` at 04:04:29 and 04:34:31 UTC today (~30 min cadence, same as M6 found).
- State (`IntelX/data/watches/state.json`): 2 watches. ai_model_releases seen=2374, fired=2, last_fired 2026-11-24T21:30:32Z, last_first_seen 2026-11-26T13:03:24Z. india_tech_regulatory seen=769, fired=2, last_fired 2026-11-24T14:30:07Z, last_first_seen 2026-11-27T04:34:31Z.
- Outbox (`IntelX/data/watches/outbox.jsonl`): 4 envelopes total; newest still `8ca3ca25…` (GPT-6 protein-design digest), fired 2026-11-24T21:30:32Z. **No alert in ~3 days.** `instant_outbox.jsonl` absent (default path `data/watches/instant_outbox.jsonl`).
- Envelope-recency clause: FAILS again (same as M6 checkpoint 2) — the cycle runs but produces zero alerts; no item's alert leg is proven by observation.
- Health: `GET http://127.0.0.1:8005/health` → HTTP 503, `{"status":"degraded","mock_mode":false,"database":"connected"}`; dependencies ok (database round-trip, storage writable); capabilities `research`/`model_provider` unknown ("NO_LIVE_PROBE" / "CONFIG_ONLY"). Service up, DB connected, but self-reporting degraded.
- Soak file: no `2026-11-2*.json` or `*soak*` file exists under `/opt/friday_universe/IntelX` today (M6's 2026-11-26 soak observation is not reproducible from current state; "soak" in-repo is `mesh/universe_soak_test.py` + `IntelX/scripts/run_int876_soak.py`, not a watch-cycle artifact). Current analogue: journal 04:01:20 UTC today shows a live-research run persisted `run_id=lr_0a1185aa72de49b7a59d2841 status=DEGRADED` after two Inference chat-completion calls — synthesis health still degraded, cause not diagnosed this run (outside the read-only probe).

## Deploy drift (11-file check vs main 99e5fe12)

- 9/11 match main exactly: `test_ig_named_sources.py`, `scouted_repos.py`, `scouted_repos.json`, `generate_scouted_repos.py`, `test_ig_scouted_repos.py`, `test_ig2_browser_sidecar.py`, `deep_research_loop.py`, `deep_research_pipeline.py`, `test_ig2_deep_research_loop.py`.
- 2 drift (both are the items' original commits, predating later tasks): `named_sources.py` (`5ebadfe4`, 2026-11-15) and `browser_sidecar.py` (`19634494`, 2026-11-16). Same two files M6 flagged on 2026-11-26; the service restart on 2026-11-26 06:32:44 UTC did not re-sync them.
- Beyond the 11: `IntelX/intelx/watches/outbox_shipper.py` (last touched 2026-11-24) and `db_seen_store.py` (2026-11-25) exist on main but are ABSENT from the live checkout. The live `engine.py` does not import either, so the running service is unaffected; the deploy still lags main by at least those two files.
- `/opt/friday_universe` is not a git checkout (no `.git`); hashes were taken with `git hash-object` on the live files.

## Held leg — NOT run (no clearance)

- Duplicate/flood burst + one real alert end-to-end per item: HELD. No clearance in WATCH201, WATCH202, or the Burn Enforcer 10:05 post; the owner stop order cited in M6 checkpoint 2 has no lift for INT-049 in anything read this run. Triggering a burst and dispatching a real alert is a live write on the production service — not run without explicit coordinator clearance.
- Re-sync of the two stale files + `IntelX.service` restart: also not run (coordinator clearance owed, per M6 checkpoint 2 route; restart is its own clearance).
- Ask to Muse (coordinator): (1) grant or deny the alert/burst live leg for INT-049; (2) clear the two-file re-sync + restart (or fold it into the next fleet deploy); (3) rule whether the sidecar should be installed/enabled on IntelX-Server at all, or whether IG2-INT-01's live leg moves to the owner's machine / ARM server.

## Transport note

- Bridge MCP endpoint unresponsive ~04:44–04:46 UTC (empty replies; `curl` rc=52), recovered on its own; gateway root stayed HTTP 200 throughout. All probe legs after 04:46 UTC ran clean. No leg was double-fired: every bridge call in this run was read-only except the deep-research run and the Archive.org fetches (outbound reads), which ran once each.

## Five states

- implemented YES (all four items MERGED) / tested YES (M6 41/41 first-hand re-run 2026-11-26; CI green on main `99e5fe12`, 11 success + 3 skipped, 0 failed) / merged YES / deployed PARTIAL (9/11 files match main; `named_sources.py` + `browser_sidecar.py` stale at original-item commits; 2 watch files absent) / production-verified PARTIAL (IG-INT-05 YES, IG-INT-06 YES, IG2-INT-02 YES, IG2-INT-01 NO — sidecar absent by design; alert/burst leg HELD, envelope-recency FAILS).

## Next

- Verifier (paired, per WATCH202 §5 the #2065 verdict went to M19; INT-049's work PR awaits a named verifier) checks the evidence doc + live figures above.
- INT-049 stays open until the alert/burst leg is cleared and run, or the coordinator rules the three passing items verified and files a named fix task for IG2-INT-01 (sidecar enablement / re-sync).
- Queue after INT-049: EARN-033 (CLAIMED/muse_4, blocked on owner itch.io upload step).

— Muse 4, 2026-11-27 ~10:25 IST
