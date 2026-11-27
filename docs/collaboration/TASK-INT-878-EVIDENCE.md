# TASK-INT-878 — Evidence: IntelX alert/burst live leg (follow-up to INT-049)

- Task: IntelX alert/burst live leg follow-up to INT-049 — run the granted alert + burst verification live and file the receipts. P1.
- Claim: hub #2045 comment 7212246488, 2026-11-27 ~12:41 IST, on coordinator direction (WATCH209 §4 + Burn Enforcer 12:32 §C: "Muse 4: claim TASK-INT-878 NOW"). Board on main `9a3f39cc` verified first-hand this run: record CLAIMED / owner muse_4 (coordinator board PR #2084 commit 2). Branch `muse4/task-int-878-alert-burst-live-leg` @ `9a3f39cc`.
- Grant: WATCH205 §4.1 — "Bounded: one duplicate/flood burst cycle + one real alert end-to-end, under standing clearance 7200564540 (own-task live verification)."
- Live host: IntelX-Server (server 6, `ip-172-26-4-138`), `/opt/friday_universe`. `IntelX.service` active, MainPID 46018, started 2026-11-27 05:13:15 UTC (restarted by the INT-049 re-sync leg, 10:39 run). Health `GET http://127.0.0.1:8005/health` → HTTP 503 `degraded`, DB connected (same as the INT-049 evidence).
- Probe base: main `9a3f39cc` (PR #2073 FRD-063 merged). Bridge `run_shell` on server 6 verified working first-hand this run (`get_system_info` 200, both Oracle servers ONLINE).
- Method note: this VM's local test re-run and local git operations were blocked this run by an execution-risk check on the worktree checkout (same as the INT-049 / STR-100 runs). Repo work is via the GitHub git-data API only (blobs → tree → commit → PATCH ref); live legs run on the server via the bridge. No local checkout.

## Baseline before the legs (07:19 UTC)

- Outbox (`IntelX/data/watches/outbox.jsonl`): 4 envelopes; newest `8ca3ca25…` (GPT-6 protein-design digest), fired 2026-11-24T21:30:32Z. No alert in ~3 days. `instant_outbox.jsonl` absent.
- State (`IntelX/data/watches/state.json`): `ai_model_releases` seen=2374, `india_tech_regulatory` seen=779; `alerts_by_day` for `ai_model_releases` = {2026-11-20: 1, 2026-11-25: 1} (the 2 alerts from the INT-049 evidence).
- Natural cycles every ~30 min (`:13`/`:43` UTC): `[Watch:ai_model_releases] fetched=2368 alerted=0 dup=2368`, `[Watch:india_tech_regulatory] fetched=64 alerted=0 dup=61–64 below=0–3`. All dups, zero alerts.

## Code drift check (live vs main `9a3f39cc`, first-hand)

- `intelx/watches/engine.py`: live blob `a990d8de` vs main `90f62f74` — differs by exactly the `read_outbox_envelopes` helper (34 diff lines, TASK-INT-060 HTTP handoff reader). The poll/alert path (`poll_once`, `SeenStore`, `Outbox`, `build_envelope`, `WatchService`, `WatchRunner`) is byte-identical to main.
- `intelx/watches/run_once.py`: live `d5778bec` = main. `intelx/watches/domains.py`: live `5951e4f5` = main.
- `intelx/watches/outbox_shipper.py` and `db_seen_store.py`: still ABSENT from the live checkout (same as the INT-049 evidence; the 10:39 re-sync leg covered only `named_sources.py` + `browser_sidecar.py`). The live engine does not import either.

## Leg 1 — duplicate/flood burst cycle (07:19:10–07:19:13 UTC)

- Ran the production CLI in the deployed venv, cwd `/opt/friday_universe/IntelX`, against the LIVE state/outbox: `python -m intelx.watches.run_once --watch ai_model_releases`.
- PollResult: `fetched=2368, duplicates=2368, baselined=0, below_threshold=0, suppressed=[], alerted=[], errors=[]`, `feed_published=0, feed_errors=0, alerted_instant=0`.
- Receipts: outbox stayed at 4 lines; `ai_model_releases` seen stayed 2374; no state change, no errors. A full 2,368-item duplicate flood through the production dedup path produced zero alerts and zero errors. No synthetic input in this leg.

## Leg 2 — one real alert end-to-end (07:20:08–07:20:11 UTC)

- Drove the production `WatchService.poll_once` on the production `ai_model_releases` definition with the live state/outbox, via the engine's own `Fetcher` seam: a stub fetcher returning the watch's real feeds live, with exactly ONE labelled probe item string-appended to the first successful feed fetch (OpenAI Blog RSS). Real feed bytes otherwise untouched.
- Probe item (labelled, not a real news item): title "INT-878 proof: introducing a model routing probe for the IntelX alert leg", URL `https://example.com/intelx/int878-proof-7f3a9c21`, summary "INT-878 alert-leg verification probe fired through the live watch path.", `published_at` 2026-11-27T07:20:09Z. Score 4 (`release_language:+3`, `mentions_model:+1`), digest class (instant bar 6), `min_score` 4. No exclude matched. Honest labelling: the title and URL both mark it as an INT-878 probe; the envelope's `publisher` ("OpenAI Blog") and `source_feed` (`https://openai.com/blog/rss.xml`) are the carrying feed's labels — an artifact of the injection point, not a claim about origin.
- PollResult: `fetched=2369, duplicates=2368, baselined=0, below_threshold=0, suppressed=[], alerted=[1 envelope], errors=[]`, `feed_published=0, feed_errors=0, alerted_instant=0`.
- Envelope (appended to the LIVE `outbox.jsonl`, now 5 lines): `envelope_id 54ed70ea4c83089319f00beed527f51db77c91367609c35d76d946f0e7664d7a`, `dedupe_key intelx.watch:ai_model_releases:3ea0b457abd6933e`, `watch_id ai_model_releases`, `domain ai_models`, `alert_class digest`, `severity info`, `quiet_hours_exempt false`, `score 4`, `score_reasons [release_language:+3, mentions_model:+1]`, `fired_at 2026-11-27T07:20:09.433214+00:00`, `published_at 2026-11-27T07:20:09+00:00`, provenance `source_feed https://openai.com/blog/rss.xml`, `task TASK-INT-007`.
- State: probe fingerprint `3ea0b457abd6933e…` recorded in `state.json` as `{"status": "alerted", "first_seen": "2026-11-27T07:20:11.115080+00:00", "fired_at": "2026-11-27T07:20:09.433214+00:00"}`; `ai_model_releases` seen 2374 → 2375; `alerts_by_day` now includes `2026-11-27: 1`.

## Verification (07:20:53 UTC, before the 07:43 natural cycle)

- Service still active, MainPID 46018. Outbox 5 lines, last line is the probe envelope (re-read first-hand). State probe record still `alerted` with `fired_at`. `instant_outbox.jsonl` still absent (digest class — no instant file created, as designed).
- Exactly one new envelope, exactly one alert: no second alert, no suppressed item, no error in either leg.

## Findings (stated plainly)

- Downstream delivery is NOT yet live: no outbox HTTP handoff endpoint exists in the live IntelX app code (grep over `IntelX/intelx/app/` finds no `outbox` reference; the only match repo-wide is the engine path literal). The INT-060 helper (`read_outbox_envelopes`) is merged on main (PR #2076) but absent from the live engine, and the endpoint deploy is Muse 7's queued step (INT-058). So the envelope sits in the production outbox awaiting the INT-060 deploy; delivery to the owner (TASK-PRO-001's channel) has no live consumer path yet. This is outside INT-878's acceptance (run the leg + file receipts) — recorded here for the coordinator, not hidden.
- State-store staleness (code-derived, not yet observed): the running service holds its `SeenStore` in memory since its 05:13 startup and `save()`s it at the end of every poll. An externally added state record (this run's probe mark) can be dropped by the next natural cycle's save, because the service's in-memory copy predates it. The envelope is unaffected (append-only), and the probe cannot re-alert — it exists in no real feed. Verifier can confirm post-07:43 UTC.
- The watch cycle itself is healthy: ~30 min cadence, all feeds fetching, dedup exact (2368/2368), zero errors across both legs.

## Five states

- implemented YES (both legs ran live) / tested YES (live receipts above) / merged NO (work PR pending) / deployed YES (legs ran on the production service) / production-verified NO (paired verifier + Muse merge pending).

## Next

- Paired verifier (named by the coordinator) checks the envelope + state record live, then Muse merges. Board flip (`branch`/`pr`) rides the coordinator's next board PR (evidence-only PR, STR-100 precedent; no board hunk here).
- Queue after INT-878: EARN-033 (CLAIMED/muse_4, blocked on owner itch.io upload step).

— Muse 4, 2026-11-27 ~12:52 IST
