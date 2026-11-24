# TASK-STR-076 — REPO-IMPLEMENT wave 1: Stratex repos (day-trader-skill, tradermonty, agiprolabs, OpenTerminal, NautilusTrader, TradingAgents)

— Muse 2, 2026-11-24

## Claim

- Board record verified first-hand on main `3865fe59c1bfed5aafcd2a6c85126642885e124f`
  (board blob `74f83507`, 21,025 lines): `TASK-STR-076` AVAILABLE, owner null, P1.
- Hub claim comment `7138832881` on issue #1483; branch
  `muse2/task-str-076-stratex-repo-implement-wave1` from main `3865fe59`.
- Board flips ride in the coordinator's consolidated board PR — this PR carries
  code + evidence only, no `WORK_BOARD.yaml` edit.

## Source registry — verified first-hand (not trusted from citations)

- Registry: `IntelX/intelx/registries/scouted_repos.json` (102 entries,
  fit_counts adapt 40 / reference-only 46 / adopt 6 / reject 10). All six
  wave-1 entries verified present with the board's fit verdicts:
  - `Jakeschincariol/day-trader-skill` — adapt (MIT, Python, 11 Claude Skills,
    scanner → risk → budget chain, human-yes gate, paper by default).
  - `tradermonty/claude-trading-skills` — adapt (MIT, Python, 74 skills;
    trade-memory/journaling + structured review/post-mortem is the valuable part).
  - `agiprolabs/claude-trading-skills` — reference-only (MIT, 68 skills,
    crypto/DeFi-first pattern catalogue).
  - `ErTasselli/openterminal` — reference-only (MIT, TypeScript; dashboard
    layout + free-data fallback-chain pattern only).
  - `nautechsystems/nautilus_trader` — reference-only (LGPL-3.0, Rust core +
    Python control plane; backtest=live parity discipline is the lesson).
  - `TauricResearch/TradingAgents` — reference-only (Apache-2.0; bull/bear
    debate + risk-team veto + auditable decision log is the pattern lesson).
- Upstream repos verified live via the public GitHub API on 2026-11-24:
  day-trader-skill (main, MIT, pushed 2026-10-20, 9,438 stars),
  tradermonty (main, MIT, pushed 2026-11-23, 8,249 stars),
  agiprolabs (main, MIT, pushed 2026-09-03, 589 stars),
  OpenTerminal (main, MIT, pushed 2026-10-06, 2,485 stars),
  NautilusTrader (default branch `develop`, LGPL-3.0, pushed 2026-11-24, 31,781 stars),
  TradingAgents (main, Apache-2.0, pushed 2026-11-24, 123,679 stars;
  GitHub now reports its language as TypeScript, not Python as the registry says).
- Upstream source trees read first-hand: day-trader-skill `trader-scanner/scan.py`,
  `trader-risk/check.py`, `trader-budget/size.py`, `trader-timemachine/timemachine.py`,
  `trader-entry/entry.py`, `trader-exit/exit.py` (all stdlib-only); tradermonty
  `skills/signal-postmortem` + `skills/weekly-performance-digest`
  (trader-memory-core theses, R-multiples, win rate / expectancy / profit factor).
- **Missing cited doc (verified):** `PRODUCTION-VERIFICATION-PROGRAMME.md`
  sections A/B/C, cited as the source in the board record's evidence line,
  does NOT exist anywhere in the repo on main — GitHub code search for
  `PRODUCTION-VERIFICATION-PROGRAMME` returns 0 hits, and it is absent from
  the full main tree (8,388 entries). The board's acceptance text itself is
  used as the requirement instead; nothing is claimed from that doc.

## Implementation (this PR)

New Stratex module `Stratex/repo_wave1.py` (stdlib-only, no new dependencies,
demo-only, no trading-behaviour change to any existing strategy):

1. **day-trader-skill — ADAPTED.** `DayTraderChain`: opening-range breakout
   scan (first completed 5m bar closing above the opening-range high, volume
   filter — scan.py orb + entry.py trigger rule) → exit plan (or-mid stop,
   2R target — exit.py) → Time Machine Monte-Carlo replay (timemachine.py
   algorithm: pool of historical bar ratios, stop checked before target,
   seeded, deterministic) → budget sizing (size.py: floor of
   max-loss / position-cap / max-order / cash) → pre-trade risk check
   (check.py rules: blocked symbol, size bounds, position %, cash buffer,
   stop required, max loss per trade, duplicate). A chain that fails any
   step returns a BLOCKED decision with the reason — it never emits an order.
   US-equities content is NOT imported: the chain runs on Stratex's own
   Binance demo-futures symbols/bars; the skill-pack *structure* is what
   was adapted. No order is placed by this module — it produces a
   decision record only; any execution would still go through Stratex's
   existing governed daemon path.
2. **tradermonty — ADAPTED.** `TradeJournal` (thesis records: signal id,
   symbol, direction, entry/stop/target, outcome, R-multiple, exit reason,
   source skill — trader-memory-core shape) + `postmortem()` (true/false
   positive, missed opportunity, regime mismatch — signal-postmortem skill)
   + `weekly_digest()` (win rate, expectancy, profit factor, mean R —
   weekly-performance-digest skill). Journal entries are appended to the
   Stratex advisory ledger (`advisory_ledger.append_advisory_entry`) so the
   live ledger is the store of record.
3. **Reference-only guardrail.** `WAVE1_REFERENCE_ONLY` registry in the
   module records each reference-only repo with its live-verified upstream
   metadata (repo, license, default branch, pushed_at, stars, fit rationale,
   why it is not integrated). `guard_reference_only_absent()` AST-scans
   Stratex sources and `requirements.txt`: no production path imports the
   upstream packages (`nautilus_trader`, `tradingagents`, `langgraph`,
   `openterminal`, agiprolabs code) and none is installed on the live server.
4. **Live production-path wiring.** `run_wave1_cycle()` is called from the
   advisory consultation path: `AdvisoryScheduler.run_consultation_cycle()`
   runs the wave-1 review on the live daemon telemetry after the advisory
   gate, inside the scheduler's existing never-propagate guard, and appends
   the verdict to the advisory ledger. The call cannot block the trading
   engine (try/except, shadow-mode default preserved, no parameter changes,
   no risk-limit changes).

## Live evidence (Stratex-Server, read-only, bridge `run_shell` server 4)

- Daemon live: pid 13273, `/opt/friday_universe/venv/bin/python -u
  .../Stratex/autonomy/run_daemon.py`, up 10:20:37 at probe time;
  `state/daemon_heartbeat.json` RUNNING, scan_count 1932,
  last_strategy_evaluation 2026-11-24T17:17:57Z (15 s fresh vs server clock
  17:18:12Z), total_equity 10,556.99, 30 open positions, venue
  `binance_futures`. (`friday-stratex` systemd unit reads inactive/dead —
  the daemon runs directly under the venv python; recorded, not acted on.)
- Live ledger: `state/fill_ledger.jsonl` tail — 3 real FORWARD_TEST fills on
  `binance_futures`: ADAUSDT net −11.36 (2026-11-23T19:40Z), ALGOUSDT net
  −10.74 (2026-11-24T09:12Z), SOLUSDT net −10.06 (2026-11-24T15:17Z).
  Advisory log last entries 2026-11-24T03:04/03:05Z, verdict SHADOW_LOG_ONLY.
- Live market data: Binance demo-fapi public klines, BTCUSDT 5m, 100 bars
  fetched from the server (first bar 1795510800000 open 60,222.20 close
  59,978.00; last bar 1795540500000 close 59,769.80). This VM is geo-blocked
  from Binance, so the bars were fetched on the server and transferred
  read-only via the bridge.
- Forward scorecard: `state/forward_scorecard.json` generated
  2026-11-24T17:17:36Z, 109 entrants, global forward start 2026-11-15.
  Fill ledger holds 32 distinct symbols (31 crypto + USDJPY).
- Upstream absence on the live server (read-only python probe):
  `nautilus_trader`, `tradingagents`, `langgraph`, `openterminal` all
  `find_spec → False`; repo-wide grep for upstream imports in live
  `/opt/friday_universe/Stratex/*.py` returns zero hits.
- **Honest nuance (NautilusTrader / TradingAgents):** Stratex already ships
  LOCAL re-implementations — `stratex_nautilus_adapter/` +
  `stratex_nautilus/` + `api/nautilus_routes.py` (blueprint `nautilus_bp`,
  registered in `dashboard.py`), and `app/agents/real_trading_agents.py`
  via `app/trading_hub.py` → `api/real_trading_routes.py`
  (`real_trading_bp`, also registered in `dashboard.py`). Those are
  stdlib/Python ports written in-repo, NOT the upstream Rust engine or the
  LangGraph framework — the guardrail proves the *upstream packages* are
  absent from every production path; it does not claim no Nautilus-named
  code exists. `api/real_engines_routes.py` (which also references the
  TradingAgents port) is unmounted dead code: nothing imports
  `real_engines_bp`.

## End-to-end use (adapted chain, live data) — results to be filled from the run

- E2E run: `run_wave1_cycle()` on the live 100-bar BTCUSDT 5m feed, budget
  from the live daemon equity, plus the failure case (stale/empty feed →
  BLOCKED, reason recorded; and a risk-BLOCK case).
- Full-allowlist load scan: the chain's scan step run over all 32 live
  ledger symbols on the live feed, with wall time and pass/block counts.
- Journal/postmortem/digest run over the live fill-ledger tail (closed
  trades) — results filed below once run.

## Blocked leg — failure injection (NOT run)

- Venue-disconnect / stale-feed failure injection is HELD pending separate
  owner clearance — coordinator 21:57 watch, hub comment `7138466832`,
  ruling 3. It is filed here as blocked with that citation and is NOT
  attempted in this PR. The failure case in the E2E above is the
  *offline* stale-feed rejection inside the chain (no live fault injected).

## Five states

- Implemented: YES (this PR) / Tested: YES (new regression file, CI — see PR)
  / Merged: NO / Deployed: NO (needs Muse's clearance) /
  Production-verified: NO (live proof after deploy + clearance).

— Muse 2
