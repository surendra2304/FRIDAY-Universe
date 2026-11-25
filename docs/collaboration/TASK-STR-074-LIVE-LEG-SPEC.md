# TASK-STR-074 — Live-leg spec

Task: TASK-STR-074 — PRODUCTION-VERIFY: Stratex corpus items IG2-STR-09, IG2-STR-10, IG2-STR-11, IG2-STR-12, IG2-STR-13 — live extreme-condition verification (wave 1)
Claim: issue #1483 comment 7140407159, 2026-11-24
Branch: musetp4/task-str-074-production-verify-wave1
Owner: Muse TP4
Filed: 2026-11-25 ~18:00 IST, in answer to coordinator WATCH097 demand ("Muse TP4: STR-074 live-leg spec still owed", 7161378423)
Status: SPEC ONLY. No live step has run. Nothing in this spec executes until Muse clears it on #1483.

Checkpoint 1 (docs/collaboration/TASK-STR-074-PRODUCTION-VERIFY-WAVE-1.md, commit 1c3481a9) verified all five items read-only from board + GitHub API. This spec is the live leg that checkpoint 1 asked clearance for, now written out per item so Muse can rule on it.

## Ground rules (apply to every leg)

- Demo only, never live trading. No orders placed, no positions opened or closed.
- No deploy, no restart, no config change, no file write outside /tmp scratch on the target host. Scratch is deleted after evidence is captured; evidence files live in the work PR.
- Free public endpoints only (the modules' own chains). No API keys, no paid tiers, no credentials of any kind.
- Read-only access requested: bridge run_shell on Stratex-Server (server 4), read-only scope — same class as the M17 STR-053 / M18 STR-051-FIX-01 live-leg read grants.
- Owner stop order is in force (WATCH096/097/098; fleet CD broken on main 18dfcbeb — S1 dirty tree, S2 .git/objects permissions). This spec asks Muse to rule (a) whether read-only probes on Stratex-Server are within the stop order, and (b) Tier A clearance. Tier B needs separate clearance per injection.
- Ledger paths on the live checkout are resolved read-only first (ls); no path is assumed. The spec names each module's default filenames; the execution run records the resolved paths.
- Host: Stratex-Server (server 4). All legs run there, against the live/demo daemon and real market data.

## Tier A — read-only observation legs (needs Muse clearance of this spec)

### Leg 0 — daemon health + load scan (allowlist sweep)

- Probe: stratex + stratex-daemon status on Stratex-Server (process state; /health if exposed); then run Legs 1–5 in sequence, recording per-leg status + wall time.
- "Full-allowlist load scan" = exactly this spec's Tier A legs, nothing outside it.
- Pass: daemon up, each leg returns a verdict; a leg that fails is recorded as failed, not retried silently.

### Leg 1 — IG2-STR-09 tax-ledger export (MERGED #688)

- Code: Stratex/reporting/tax_ledger_export.py — CLI main() with --ledger / --out / --summary / --year / --venue; reads $TESTNET_LEDGER_FILE or testnet_trade_ledger.jsonl, and/or live_trade_ledger.jsonl; emits one CSV row per closed trade + a summary JSON.
- Probe: `python -m Stratex.reporting.tax_ledger_export --ledger <resolved live ledger> --out /tmp/tp4-str074/tax_export.csv --summary /tmp/tp4-str074/tax_export.summary.json` on Stratex-Server (demo ledger).
- Evidence: row count == closed trades in the ledger; summary totals (trades, fees, realised PnL) reconcile against the ledger's own figures; CSV parses.
- Pass: export completes and counts reconcile. Fail: row/total mismatch, or the export errors on the live ledger.

### Leg 2 — IG2-STR-10 market-data fallback chain (MERGED #691)

- Code: Stratex/market_data_fallback.py — FallbackChain.get_price(kind, symbol). Chains (free, keyless): crypto_price Binance -> CoinGecko -> DexScreener; equity_price Nasdaq -> Stooq -> Yahoo; fx_price Stooq -> Yahoo; macro_series FRED fredgraph CSV. First live provider wins; else last-good (stale); else AllProvidersFailed. Last-good cache per (kind, symbol).
- Probe: get_price once per kind live — crypto BTC (bare base defaults to the USDT pair), equity AAPL, fx EURUSD, macro one FRED series (id recorded at execution) — recording which provider answered, the quote, and latency. Then, in a scratch process with no daemon change: a FallbackChain whose first provider always fails — record the fall-through to the next provider.
- Evidence: per-kind provider + latency table; fall-through trace.
- Pass: every kind returns a live quote; the dead-primary chain still returns via fallback. Fail: any kind raises AllProvidersFailed while its chain has a reachable provider, or no fall-through happens.

### Leg 3 — IG2-STR-11 economic/earnings calendar feed (MERGED #697)

- Code: Stratex/research/economic_calendar.py — EconomicCalendar.refresh(days_ahead=7) fetches the Nasdaq economic + earnings endpoints and merges into the economic_calendar.jsonl store; classify_macro_impact / classify_earnings_impact; megacap watchlist (AAPL, MSFT, NVDA, AMZN, GOOGL, GOOG, META, TSLA, AVGO, BRK/B, JPM, LLY, WMT, XOM).
- Probe: refresh(7) live; count events stored; list high-impact macro events in the next 7 days; confirm a megacap earnings date parses where one is present.
- Evidence: stored event count, high-impact list, refresh log (a failed source is skipped and last stored data keeps being served — any skip is recorded).
- Pass: refresh returns >0 events, the store parses, impacts are classified. Fail: zero events with all sources reachable, or high-impact events left unclassified.

### Leg 4 — IG2-STR-12 MCMC strategy-uncertainty modelling (MERGED #725)

- Code: Stratex/rigorous_backtest/ig/bayesian_uncertainty.py — RESEARCH-ONLY / DEMO-ONLY. posterior_from_fills(fills_r, seed=20261116, n_iter=6000, burn=2000) -> PosteriorSummary. Needs >= 10 non-scratch trades with >= 5 per side (InsufficientDataError otherwise); deterministic for given inputs. Places no orders, imports nothing from production.
- Probe: take the closed demo/forward fills' R-multiples from the live ledger; run posterior_from_fills; record the PosteriorSummary (n_trades, observed expectancy / profit factor, expectancy_ci90, profit_factor_ci90, p_expectancy_positive, p_profit_factor_at_bar) against the RD programme's promotion bar (rd/common.py PROMOTION_BAR).
- Evidence: the summary dict + the R-multiple list hash.
- Pass: posterior computed on live fills and reported; the PROMOTION_BAR comparison is stated as evidence, NOT a promotion decision. If the live ledger holds too few closed fills, the verdict is "insufficient live fills", recorded honestly — backtest fills are never substituted.
- Fail: a crash, or a posterior that does not reproduce deterministically on re-run with the same inputs.

### Leg 5 — IG2-STR-13 Box Theory closed-state confirmation (VERIFIED, backtest FAIL, family CLOSED — MERGED #729)

- Code + record: Stratex/rigorous_backtest/ig/box_theory.py, BOX_THEORY_DECLARATION.md, box_theory_declaration.json; results RESULTS_BOX_THEORY.md + box_theory_results.json + box_theory_provenance.json (per board). Declared backtest RUN COMPLETE 2026-11-16, FAIL — crypto30 @ 15m pooled walk-forward OOS 16, 842 trades, expectancy -0.218%/trade, PF 0.805. Family CLOSED per the declaration's own failing term; nothing promoted, nothing registered for forward testing, nothing trades.
- Probe: confirm on the live checkout that the declaration + results files are present and byte-match main; search the live daemon/registry for any box_theory forward registration or live trade (expect none).
- Evidence: file presence + hashes; registry search result.
- Pass: closed state holds live — no forward registration, no trades from box_theory. Fail: any live registration or trade. This leg never runs Box Theory as a live strategy.

## Tier B — failure injection (separate clearance per injection, NOT covered by Tier A)

- B1 venue disconnect: observe the daemon's behaviour with a venue unreachable. (The STR-10 chain fall-through in Leg 2 is the Tier A proxy; a daemon-level disconnect is Tier B.)
- B2 stale feed: observe behaviour on a stale feed. (The STR-10 last-good cache in Leg 2 is the Tier A proxy; daemon-level staleness is Tier B.)
- Each Tier B injection needs its own explicit Muse clearance naming the injection, the host, and the restore step; restore is verified (venue reachable again, feed fresh) before the leg closes.

## Evidence + verdicts

- Results filed as checkpoint 2+ on this branch: one verdict per item (VERIFIED / NOT VERIFIED / INSUFFICIENT DATA), with the evidence above, per leg.
- Work PR opened when the legs are done (or genuinely BLOCKED); never merge own PR. Paired verifier: M17.
- Queue: STR-074 (head) -> STR-075 (pos 2, WATCH096 / board PR #1831 merged dbc06f33) -> DB-005 (pos 3, WATCH098 — back up IntelX local research files on IntelX-Server).

## Clearance requested from Muse

1. Approve Tier A as specified, and grant read-only bridge run_shell on Stratex-Server (server 4) for the STR-074 live leg.
2. Rule whether read-only probes on Stratex-Server are within the owner stop order (no deploy / restart / config change is involved).
3. Tier B stays held for separate per-injection clearance.

— Muse TP4
