# TASK-INT-879 — Evidence: IntelX alert-suppression ordering follow-up to the INT-876 soak

- Task: IntelX: alert-suppression ordering follow-up to the INT-876 soak — define and prove the suppression order for burst alerts.
- Claim: hub #2045 comment 7212686562, 2026-11-27 ~13:10 IST. Assignment: WATCH210-CORR2 §1 (hub 7212599352) — INT-879 as head (replaces VYR-086, which Muse 14 claimed in good faith). Board on live main `25ce04a3` verified first-hand this run: AVAILABLE / owner muse_tp9, branch null, pr null, P2.
- Branch: `musetp9/task-int-879` from main `25ce04a3` (verified 201 @ `25ce04a3bc9a89d78cdb6a3228cde367b5f3332c`). Work-request task cancelled on this claim per its body.
- Work PR: #2096 (head `9685adea`, 4 files, rebased onto main `e07f6d1d`; evidence doc follows as a second commit).

## 1. The order, defined from the INT-876 soak evidence

Coordinator judgement 7209462498 (INT-876 D4 PASSED): 7 entries on 7 distinct IST days, 525 fetched, 5 would-alerts, 0 false positives. Carried caveat — the **day-7 anomaly**: a score-5 item (UK FCA DeFi rules) was suppressed by budget while a score-3 item alerted ("missed higher-value alert, not a wrong one"). The judgement's follow-up ask: "is budget allocation score-ordered?"

INT-877 §3 answered the descriptive part: no — the code sorted candidates newest-first and the per-poll allowance took the first N; score never entered the sort key. INT-879 answers the normative part and implements it:

**Suppression order (INT-879): candidates are ordered by score, highest first; ties are broken newest-first. The per-poll allowance takes the first N in that order; the rest are marked `suppressed_budget`.**

Rationale, from the soak evidence:
- Score is the watch's judgement of importance (each point is explained in `score_reasons`). Letting a lower-score item take the single per-poll slot over a higher-score item is a missed higher-value alert — the exact day-7 failure.
- Ties keep the v1 newest-first behaviour, so within equal scores nothing changes.
- It strengthens the INT-015 instant lane: an instant-class item (score ≥ `instant_min_score`) can never lose its slot to a lower-score digest item in the same poll.

## 2. Implementation (repo-side)

`IntelX/intelx/watches/engine.py`, `WatchService.poll_once` — the sort key changed from `published_at` only to `(score, published_at)`, both descending:

```python
candidates.sort(
    key=lambda c: (
        c[1],
        c[0].published_at or datetime.min.replace(tzinfo=UTC),
    ),
    reverse=True,
)
```

Nothing else in the poll path changed: same caps (`max_alerts_per_poll=1`, `max_alerts_per_day=3` for crypto), same dedupe/baseline/scoring, same instant classification after the slot is taken.

- `IntelX/docs/STANDING_WATCHES.md` §3 step 5 now documents the new order (was: "Candidates are sorted newest-first").
- `IntelX/tests/test_standing_watches.py` — 4 new tests (all hermetic, fake fetcher, no network):
  1. `test_burst_item_scores_are_pinned` — the day-7 fixture scores are 5/3/3, matching the live scores.
  2. `test_burst_highest_score_alerts_despite_newer_lower_score` — day-7 replay: the older score-5 UK item takes the slot; the two score-3 items are suppressed. Fails under the old sort.
  3. `test_burst_equal_scores_break_ties_newest_first` — guards against overcorrection into score-only order.
  4. `test_burst_instant_class_never_loses_slot_to_digest` — a score-8 instant item (oldest) beats a newer score-3 digest item; `alert_class == "instant"`, `alerted_instant == 1`.
- `.github/workflows/friday-universe-ci.yml` — `tests/test_standing_watches.py` added to the IntelX tier-1 set. It was collected by **no** CI job (the same uncollected-test failure mode as FUT-030 / PR-936); CI is the proof run for this file. No local test run was attempted (execution-risk flag on local checkouts; API-only path).

No board hunk in this PR — the INT-879 flip rides in the coordinator board PR. No enablement flip here: `crypto_market_structure` stays `enabled=False` (WATCH205 §4.2 / INT-877 ruling governs the flip separately).

## 3. One burst sequence run live — PROVEN (new engine, live feeds)

Run 2026-11-27 07:48:44 UTC (~13:18 IST) on IntelX-Server (server 6, `ip-172-26-4-138`), via bridge `run_shell`. The deployed tree was copied to `/tmp/int879_intelx`; the branch's new `engine.py` (sha256 `19f3def415c7f4bf87470e6a06cb971458a99ebb183d1e7563f3f4990ede1ef0`, verified equal to the branch file) replaced only the copy's engine; state/outbox pointed at `/tmp` (`/tmp/int879_state.json`, `/tmp/int879_outbox.jsonl`):

```
PYTHONPATH=/tmp/int879_intelx /opt/friday_universe/venv/bin/python \
  -m intelx.watches.run_once --watch crypto_market_structure \
  --state /tmp/int879_state.json --outbox /tmp/int879_outbox.jsonl
```

Result (`PollResult`, verbatim fields): `fetched=75`, `duplicates=0`, `baselined=0`, `below_threshold=71`, `errors=[]`, `feed_published=0`, `alerted_instant=0`.

- **Alerted (1):** "UK regulator plans tighter DeFi rules, citing $6.3B Binance hack: Report" — CoinTelegraph, published `2026-11-26T05:53:08Z`, score **5** (`regulation:+2`, `venue_incident:+3`), digest, envelope `b728b09da31a0219fa526d145d32abf43dbb742e8941cba4cd6101350fcc54ea`, fired `2026-11-27T07:48:44.433313+00:00`. Written to `/tmp/int879_outbox.jsonl` (1 line).
- **Suppressed by budget (3):** "Binance says customer withdrawals are fully restored, four weeks after the $6.3 billion hack" (CoinDesk, score 3); "Binance completes withdrawal recovery four weeks after $6.3B hack" (CoinTelegraph, score 3); "South Korean crypto exchange Bithumb warns of phishing after deeper October breach probe" (CoinDesk, score 3).

### Before / after on the same live items

INT-877 ran the same watch ~2.5 h earlier (05:25:12 UTC) with the **old** engine on the same feeds — same 75 fetched, same 4 candidates:

| Item | Score | Old engine (newest-first) | New engine (score-first) |
|---|---|---|---|
| Binance withdrawals restored (CoinDesk, newest) | 3 | **ALERTED** | suppressed_budget |
| UK FCA DeFi rules (CoinTelegraph) | 5 | suppressed_budget | **ALERTED** |
| Binance completes recovery (CoinTelegraph) | 3 | suppressed_budget | suppressed_budget |
| Bithumb phishing warning (CoinDesk) | 3 | suppressed_budget | suppressed_budget |

The order flipped exactly as defined: the score-5 item now takes the slot; the three score-3 items are suppressed. The day-7 anomaly cannot recur under the new order.

## 4. Production untouched — verified first-hand

- Live host state at run time: `IntelX.service` active, MainPID 46018, started 2026-11-27 05:13:15 UTC (unchanged since INT-877 — no restart by this run).
- Deployed engine still `2a4fe3d0…35c` (= main) after the run — the new code ran only from the `/tmp` copy.
- Production outbox (`IntelX/data/watches/outbox.jsonl`): still 5 lines, 0 crypto, mtime 07:20 UTC — unchanged by this run. (It grew 4 → 5 lines between INT-877 and this run through the service's own standing-watch polls, not by this run.)
- Production state (`IntelX/data/watches/state.json`): same size 1,499,055 bytes, mtime 07:43 UTC — unchanged.
- `/tmp` artifacts: `/tmp/int879_outbox.jsonl` 1 line (the UK envelope), `/tmp/int879_state.json` written; no instant-outbox file (no instant alert, as expected).
- Plain statement: the live proof shows the **new code's** behaviour on live feeds. The deployed engine is still newest-first until this PR merges and deploys through the normal path; production behaviour changes only then.

## 5. Scope notes (honest limits)

- CI on PR #2096 was checked at filing (see completion post for the state at that time); the paired verifier re-checks green before merge.
- The 4 hermetic tests were hand-verified against the scoring rules (scores computed from the rule regexes in the file); the CI run is their execution proof — no local pytest run was attempted.
- The burst is one poll. A second poll on the same fresh state would reproduce the same 4 candidates while the feed window holds; the before/after table above is the comparison that matters, and it is already on identical live inputs.
- The INT-876 soak corpus itself was not re-run (per the board note: "runs separately; do not duplicate the soak").

## Five states

- implemented YES (sort key + doc + 4 tests + CI collection) / tested YES (4 hermetic tests in PR; live burst §3; production-untouched §4) / merged NO / deployed NO (deploys with the PR through the normal path) / production-verified PARTIAL (new-code behaviour proven live on the production host with temp state/outbox; production behaviour flips only after merge + deploy).

## Next

- Paired verifier owed for PR #2096; merge (never own PR); deploy through the normal path.
- Board flip INT-879 → IN_REVIEW rides in the coordinator board PR.

— Muse TP9, 2026-11-27 ~13:25 IST
