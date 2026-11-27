# TASK-INT-877 — Evidence: INT-876 D4 enablement — production parity + one real alert cycle

- Task: IntelX: INT-876 D4 enablement — production parity + one real alert cycle (D4 judgement PASSED).
- Claim: hub #2045 comment 7210451108, 2026-11-27 ~10:45 IST. Board on live main `ea47e4be` verified first-hand this run: AVAILABLE / owner null, P1, no prior claim, branch or PR. No competing claim in hub #2045 through comment 7210389533 (TP11 passed at 10:10 IST for lack of server execution; TP9 has it — bridge `run_shell`, settled grant per Burn Enforcer 10:05 §F).
- Branch: `musetp9/task-int-877-d4-enablement` from main `ea47e4be` (verified 200 @ `ea47e4be1266386657e9ef543c36799e8940a30d`). Work-request task cancelled on this claim per its body.
- Live host: IntelX-Server (server 6, `ip-172-26-4-138`), `/opt/friday_universe`. `IntelX.service` active, MainPID 46018, started 2026-11-27 05:13:15 UTC (restart observed, unattributed — a clean stop/start at 10:43 IST, after Burn Enforcer 10:35 §F cleared the re-sync/restart leg; not done by this run). Probe window 2026-11-27 ~10:50–11:00 IST, via bridge `run_shell`/`read_text` on server 6. Local git/test work was not attempted (execution-risk flag on local checkouts; API-only path per WATCH203 §4.3).
- Basis: coordinator judgement hub #2045 comment 7209462498 (2026-11-27 ~09:35 IST): D4 PASSED — 7 entries on 7 distinct IST days, 525 fetched, 5 would-alerts, 0 false positives, engine pin sha256 `271ee4ee…392e3` verified by independent `sha256sum`. The judgement's task 1 (enablement) + task 2 (suppression-ordering follow-up) are both folded into this task's acceptance.

## 1. Production parity — EXACT: NO; BEHAVIORAL (would-alert set): YES, with bounded deltas

### 1.1 Hashes (all first-hand)

| File | sha256 | |
|---|---|---|
| Live `IntelX/intelx/watches/engine.py` (S6) | `2a4fe3d045fa0a96762d96366fb26f71fedb2eff4bee88201aa79f55d705f35c` | = main, ≠ pin |
| Main `IntelX/intelx/watches/engine.py` (ea47e4be) | `2a4fe3d045fa0a96762d96366fb26f71fedb2eff4bee88201aa79f55d705f35c` | |
| Pinned engine (judgement pin `271ee4ee…392e3`) | `271ee4ee151e3c7d17d3f03d3f24d94cc15c79e9be16ea6b867ba5ff212392e3` | = `engine.py` at commit `d5a99c3ad8ad` (2026-11-17, F1 withdrawal-block fix, PR #876) |
| Live `IntelX/scripts/run_int876_soak.py` (S6) | `11bd8aadd206588b1455f91b6cc4b3ea6fcd42140b1ad1f442cc0474cb4925d2` | = main |

The pin resolves to exactly one commit in the file's history: `d5a99c3a`. The live engine is three commits newer (INT-013 domains, INT-014 Universe intel feed, INT-015 instant alert policy, all 2026-11-18). The soak evidence was therefore produced by an engine version that was already three commits behind main when the soak window opened (2026-11-21) and was never the deployed version during the window. Live file mtime 2026-11-18 17:13:45 UTC; the running process started 2026-11-27 05:13:15 UTC, after the file's last change — the running code is the file hashed above.

### 1.2 What changed pinned → live (full diff, 381 lines)

- INT-013: three new watch definitions (`platform_policy`, `fleet_tools`, `world_events`) + a `domain` field on every watch (crypto gets `domain="markets"`) + domain-scoped runner.
- INT-014: Universe intel feed hook (`_publish_to_feed`), gated by `INTELX_WATCH_FEED_ENABLED` (default off).
- INT-015: `instant_min_score` field (crypto = 6) + instant-class envelope classification + instant-outbox write for alerts scoring ≥ 6.
- **Unchanged:** the crypto watch definition except the two added lines (`domain`, `instant_min_score`) — verified by direct diff of the definition block: same 4 `ScoreRule`s, same excludes (incl. D1/D3 guards), `min_score=3`, `max_alerts_per_poll=1`, `max_alerts_per_day=3`, `baseline_max_age_hours=72`, `poll_interval_seconds=1800`, `enabled=False`. Same `score_item`, `parse_feed`, `SeenStore`, dedupe, baseline, newest-first sort and budget code — no diff in those regions.

### 1.3 Production config (live, first-hand)

- `INTELX_ENABLE_STANDING_WATCHES=true` in `IntelX/.env` — the background `WatchRunner` is on in production; the two enabled watches poll every 30 min (journal 05:04:33 UTC today: `ai_model_releases` fetched=2368 alerted=0, `india_tech_regulatory` fetched=64 alerted=0).
- `INTELX_WATCH_FEED_ENABLED` is **unset** in `IntelX/.env` — the INT-014 feed hook is OFF in production, so that delta is inert.
- Production outbox (`IntelX/data/watches/outbox.jsonl`): 4 envelopes, newest `8ca3ca25…` (GPT-6 protein-design digest), fired 2026-11-24T21:30:32Z — matches M4's INT-049 reading exactly. No crypto envelope has ever fired in production. Production `state.json` has no `crypto_market_structure` section (the 4 `crypto` string hits in it are seen-item URLs from the india watch).
- Carried drift (INT-049, unchanged by the 05:13 UTC restart): `IntelX/intelx/watches/` still lacks `db_seen_store.py` and `outbox_shipper.py` (present on main, absent live). The restart did not re-sync them. Not this task's scope; carried.

### 1.4 Parity verdict

**Exact parity FAILS** — live `2a4fe3d0…35c` ≠ pinned `271ee4ee…392e3`. **Behavioral parity for the soak's would-alert set HOLDS** — scoring, budget and ordering are identical, so the same 5 items would fire with the same scores under the live engine. The deltas that do bite: (a) an alert scoring ≥ 6 is now **instant-class** (severity `high`, quiet-hours exempt, copy in the instant outbox) instead of digest — a delivery change for big breaks; (b) envelopes gain `"domain": "markets"` and `"alert_class"` keys. Whether any of the 5 would-alerts scored ≥ 6 is **unverifiable from any file readable here** — the coordinator's soak files are not on S6 (no file under `IntelX/data/` or `/var/lib/friday-universe/` mentions `crypto_market_structure`); the coordinator holds them.

**Consequence: the enable flip is HELD, not filed in this PR.** The acceptance orders parity confirmation *before* flipping, and exact parity failed. The flip (one line: `enabled=False` → `True` for `WATCH_CRYPTO_MARKET_STRUCTURE`) is a named follow-up gated on a coordinator ruling: proceed on behavioral parity, or re-soak against the current engine first. Ask carried in §5.

## 2. One real alert cycle, end-to-end — DONE (live, production untouched)

Run 2026-11-27 05:25:12 UTC (~10:55 IST) on IntelX-Server, via the deployed service's own venv (`/opt/friday_universe/venv/bin/python`, cwd `/opt/friday_universe/IntelX`):

```
python -m intelx.watches.run_once --watch crypto_market_structure \
  --state /tmp/int877_state.json --outbox /tmp/int877_outbox.jsonl
```

State and outbox were pointed at `/tmp` on purpose: the production `state.json`/`outbox.jsonl` are untouched (verified after — production outbox still 4 lines, 0 crypto envelopes; no crypto section in production state). The watch is still `enabled=False` in code; `run_once` polls the named watch directly, so no code change was needed for the proof. Everything else is production: the live engine file, the live feeds, live scoring and budget.

Result (`PollResult`, verbatim fields):

- `fetched=75` (The Block + CoinDesk + CoinTelegraph — exactly the soak's 75/day), `duplicates=0`, `baselined=0`, `below_threshold=71`, `errors=[]`, `feed_published=0`, `feed_errors=0`, `alerted_instant=0`.
- **Alerted (1):** "Binance says customer withdrawals are fully restored, four weeks after the $6.3 billion hack" — CoinDesk, published `2026-11-27T04:45:47Z`, score **3** (`venue_incident:+3`), digest, `severity info`, `quiet_hours_exempt false`, envelope `de328ac1ca55c655bbd437a5693be1599776c219a5e3abcee23fe14c7233ef9c`, `dedupe_key intelx.watch:crypto_market_structure:bd81bbe12d5e0864`, fired `2026-11-27T05:25:12.367399+00:00`. Written to `/tmp/int877_outbox.jsonl` (1 line). No instant-outbox file was created (no instant alert).
- **Suppressed by budget (3):** "Binance completes withdrawal recovery four weeks after $6.3B hack" (CoinTelegraph, score 3); "UK regulator plans tighter DeFi rules, citing $6.3B Binance hack: Report" (CoinTelegraph, score **5**); "South Korean crypto exchange Bithumb warns of phishing after deeper October breach probe" (CoinDesk, 2026-11-25, score 3).
- `baselined=0` on a fresh state: all 75 fetched items were published within the 72 h baseline window.

The cycle is real end-to-end: live feeds → parse → dedupe → score → newest-first budget → envelope → outbox write. The only non-production aspects are the temp state/outbox paths and the watch not yet being in the standing loop.

## 3. Day-7 suppression-ordering question — ANSWERED: budget is newest-first, NOT score-ordered

**Answer: No — budget allocation is not score-ordered.** Candidates are sorted by `published_at`, newest first, and the per-poll allowance takes the first N; score plays no role in the ordering. The score-5 item lost to a newer score-3 item by design, not by a bug.

Evidence, three independent legs:

1. **Code (pinned and live, identical):** `engine.py` — `candidates.sort(key=lambda c: c[0].published_at or datetime.min.replace(tzinfo=UTC), reverse=True)` (pinned lines 688–691; main lines 934–937), then `allowance = max(0, min(watch.max_alerts_per_poll, budget_left))` and the first `allowance` candidates alert while the rest are marked `suppressed_budget`. Score is computed before the sort but never enters the sort key. Design doc (`IntelX/docs/STANDING_WATCHES.md` §3 step 5) states it in prose: "Candidates are sorted newest-first."
2. **Live reproduction (§2, same items as the judgement's day-7 anomaly):** the score-5 UK FCA DeFi item was `suppressed_budget` while the score-3 CoinDesk Binance-restoration item (published `2026-11-27T04:45:47Z` — the newest candidate) took the single per-poll slot and alerted. The Bithumb phishing item (score 3, 2026-11-25) was also suppressed. Ordering by recency, not score, is visible in the live result.
3. **Design intent:** the newest-first rule is the documented v1 behaviour; nothing in the pinned or live engine sorts by score anywhere.

**Consequence:** a higher-score older item can lose its slot to a newer lower-score item whenever ≥ 2 candidates arrive in one poll (cap is 1/poll, 3/day). If score-ordering is wanted, that is an engine change (sort key `(-score, published_at)` or a score-priority allowance) — a follow-up task for the coordinator, not a defect in this one. The day-7 anomaly is explained, not a miscount: the score-5 item was genuinely suppressed by budget, and the score-3 alert was genuine.

## 4. Scope notes (honest limits)

- The coordinator's 7-day crypto soak corpus (7 entries, 525 fetched, 5 would-alerts) was **not re-verified** — its files are not on S6 and the judgement's figures are taken as given. The on-server soak day records that DO exist (`/var/lib/friday-universe/intelx-soak/2026-11-25/26/27.json`) belong to the *research-live* soak (`run_int876_soak.py`, query "latest AI model releases"), a different soak: all three are `DEGRADED`, `pass: false`, `synthesis_status: failed` (Nov 25 ran 02:42 IST, off-schedule; Nov 26/27 ran 09:30 IST as timed). That synthesis failure is the known `synthesis_entailment_unverified` class from INT-023/INT-035, outside this task — recorded here so nobody mistakes those records for the crypto watch soak.
- The 5 would-alerts' scores are unknown here (see §1.4) — whether any would now be instant-class is for the coordinator, who holds the soak files.
- No service restart, no file change, no outbox/state write was made on production by this run. The only writes on S6 are `/tmp/int877_state.json` and `/tmp/int877_outbox.jsonl` (probe artifacts).

## 5. Asks to Muse (coordinator)

1. **Parity ruling (flip gate):** exact parity failed on the INT-013/014/015 delta; behavioral parity for the would-alert set holds. Rule: flip `crypto_market_structure` to `enabled=True` on behavioral parity (one-line follow-up PR, then deploy + restart under standing clearance 7200564540), or re-soak against the current engine first?
2. **Score-ordering follow-up:** confirm whether the newest-first budget rule stands (day-7 anomaly = by design, no change) or file a task to make budget allocation score-ordered.
3. Paired verifier for this work PR owed (evidence-only PR; no board hunk, no code change).

## Five states

- implemented NO (no code change — flip held per §1.4) / tested YES (parity hashes first-hand on S6 + main + history; live alert cycle §2; sort verified in pinned + live code and reproduced live) / merged NO / deployed NO / production-verified PARTIAL (alert cycle proven end-to-end on the production host with temp state/outbox; the production-outbox cycle awaits the flip + deploy).

## Next

- Coordinator ruling on §5.1, then the one-line enable flip PR (or a re-soak task).
- Queue after INT-877: TASK-LAP-002 (queue position 3, watch203 §4.2 — real-device legs need the owner laptop/phone path; not executable from this worker as it stands).

— Muse TP9, 2026-11-27 ~11:05 IST
