# TASK-STR-RISK-001 — Risk-Guard Enforcement Audit (Stratex)

**Question:** does every Stratex protection actually fire — in code, in the
staging harness, and in live config — or is any of it decorative?
**Method:** fresh-main code read (main `7bce776`; guard regions re-verified
unchanged at main `c2781b61`, whose only daemon delta is FWD-003's
FORWARD_TEST lane), a 27-check staging harness against stub venues (no
orders placed anywhere), live Server 1 config probe (2026-11-15 14:16 IST),
and the RD-011 sizing simulation as a named test case.
**Scope:** the two live order paths — the Binance demo-fapi daemon
(`autonomy/run_daemon.py` + `autonomy/multi_venue_engine.py`) and the OANDA
practice engines (`oanda_demo/trader.py`, `oanda_demo/sleeve_runner.py`) —
plus the adapter-level live-trading gate. The classic-testnet engine is
retired (service masked, TASK-STR-RETIRE-001) and out of scope.

## Per-guard verdicts

### 1. Per-trade risk cap (1% before the 2026-11-15 settlement) — REAL
- Daemon sizing (`run_daemon._execute_signal`): `risk_amount = equity ×
  risk_per_trade`; `quantity = risk_amount / |price − stop|`; the 10%
  notional cap (`STRATEX_MAX_POSITION_PCT`) only ever *reduces* size.
  Signals whose stop distance falls outside the env stop band are refused
  outright, never clamped into a larger size — so the stop used for sizing
  is the stop attached to the order.
- Harness: quantity × stop-distance == exactly $100.00 on $10,000 equity at
  1% (C1); notional cap binds at $20 risk (C2); a 20% stop is refused (C3).
- Live config (14:16 IST): `STRATEX_RISK_PER_TRADE_PCT=0.01` — the daemon
  reads the `STRATEX_`-prefixed name, and the prefixed name is what the
  live .env carries (the board's deploy note dropped the prefix in prose
  only; there is no env-name bug).
- OANDA engines: `RISK_PER_TRADE_PCT = 0.01` is a code constant in both
  `trader.py` and `sleeve_runner.py`; units are solved so an SL hit costs
  exactly 1% of equity, capped by a 25% notional cap. Harness E1: 1,999
  units × $0.05 stop = $99.95.

### 2. Daily-loss breaker, 3% — REAL, with one documented window
- `MultiVenueEngine._check_daily_loss_limit` latches
  `daily_loss_limit_hit` on *realized* day PnL ≤ −3% of
  `daily_start_equity`; the latch and the baseline persist in
  `state/realized_pnl.json` and are restored on restart (the Phase-2 fix);
  the daemon re-evaluates the breach itself each cycle (belt-and-braces)
  and skips the scan when hit.
- Harness: holds at −2.99%, latches at −3.01% (B1/B2); latch + baseline
  survive a state round-trip (B3).
- Live state (14:16 IST): `daily_start_equity = 20572.46` — seeded, **not
  0.0** — `daily_realized_pnl = 0.0`, `daily_loss_limit_hit = false`,
  daemon active. `STRATEX_MAX_DAILY_LOSS_PCT=0.03`.
- Documented window: if the baseline is 0.0 the breaker *cannot* fire
  (B4, isolated). The mitigation is real: `_check_daily_reset` re-seeds
  from live equity on the first successful read and retries every scan
  cycle (B5/B6) — the disarmed state lasts only while venue reads are
  failing, in which case sizing also refuses entries (equity ≤ 0 check).
- OANDA trader: NAV-based (includes unrealized — stricter), day-start NAV
  persisted in its state file; harness E2: at −4.0% day, a live signal
  produces **zero** orders; E5: a healthy day trades. Residual: deleting
  the OANDA state file mid-day resets its baseline to current NAV.

### 3. Strategy DD > 5% kill + performance kills — REAL, matches protocol
- `measurement/forward_guard.evaluate` is the protocol, verbatim: ≥50
  closed trades AND (expectancy < 0 OR PF < 1.0), OR the strategy's
  cumulative-PnL peak-to-trough drawdown exceeding 5% of account equity.
  The daemon calls it on its governance cadence and auto-pauses breached
  strategies through a **persisted** denylist; the sleeve variant judges
  the combined sleeve curve only and pauses every component (plus the
  OANDA sleeve runner's pause file).
- Harness: kill fires at 50 losing trades, not at 49 (A1/A2); the DD leg
  fires at 2 trades when DD = $600 > $500 (A3) and not at $400 (A4);
  equity = 0 disables only the DD leg (A5); sleeve combined-DD kill (A6).
- **Cadence weakness (found in this audit):** the guard is evaluated in
  the daemon's *daily* slot only (`_last_prune_date` gate in the scan
  cycle). On the first cycle after a restart the date is set **without
  evaluating** — so evaluation happens at most once per UTC day and is
  skipped entirely on restart days. A strategy can breach intraday and
  keep trading until the next UTC-day evaluation. The coordinator's
  extended FWD-006 brief (mark-to-market DD on scan cadence) closes
  this; B-half verification below checks it.
- **Pooled-book semantics (RD-011 question 2):** the DD numerator is the
  strategy's *own* fills pooled across **all symbols and both venues** in
  the fill ledger; the denominator is *total current account equity*.
  That is exactly the computation the written protocol assumes.

### 4. Leverage pinned at 3x (demo-fapi) — CONFIG REAL, CODE WAS DECORATIVE → FIXED IN THIS PR
- Live: `BINANCE_ENV=demo`, `BINANCE_LEVERAGE=3`; the adapter POSTs
  `/fapi/v1/leverage` per symbol before its first order.
- But the code honoured the env *verbatim*: harness D3 —
  `BINANCE_LEVERAGE=125` produced `target_leverage = 125`. And a failed
  leverage POST was silently ignored, the order proceeding at whatever
  leverage the symbol already carried (D5). The pin was config
  discipline, not enforcement.
- Fix (this PR): `OWNER_LEVERAGE_PIN = 3` ceiling in code (env values
  above 3 clamp to 3 with a warning; lower values honoured);
  `_ensure_leverage` returns success/failure and `place_order` refuses
  when the pinned leverage cannot be confirmed.

### 5. Entries-pause mechanisms — REAL, one fail-open call site → FIXED IN THIS PR
- `trading_pause` and `panic_state` are fail-closed by design: a corrupt
  flag file reads as PAUSED / PANIC (harness C6/C7). The daemon checks
  both at scan level and again inside `_execute_signal`; the OANDA
  engines check their own kill-switch + entries-paused files every scan
  (E3/E4).
- Defect (harness C5): the daemon's `_execute_signal` wrapped both reads
  in try/except that logged a warning and **continued to order
  placement** — a read that raised (import/IO failure) silently waved
  entries through. The flags were decorative exactly when state was
  broken. Fix (this PR): both call sites fail **closed** (entry refused,
  error logged), matching the modules' own design.
- Daemon decorative leftover (noted, not a guard failure): the daemon's
  own `self.max_positions` (env `STRATEX_MAX_TOTAL_POSITIONS`, code
  default 9999) is defined and never read; the *binding* concurrency cap
  is the engine's `can_open_position` (live: 30 per venue / 30 total).

### 6. Fail-closed live-trading guard — REAL (strongest guard in the fleet)
- `BinanceFuturesAdapter` refuses *construction* when `TRADING_MODE=LIVE`
  or env `LIVE_TRADING_ENABLED=1`, and refuses a live-endpoint adapter
  unless **both** `ALLOW_LIVE_TRADING=true` **and** the code invariant
  `config.LIVE_TRADING_ENABLED` (shipped `False`, verified in the repo
  and required for any live resolution) hold; the check re-runs on every
  order/cancel path. Environment alone can never authorize live trading.
- Harness D1/D2: both refusal modes raise `PermissionError` before any
  network activity. Live env: `TRADING_MODE=FUTURES`, `BINANCE_ENV=demo`.

## The RD-011 test case — the written rule pair was arithmetically inconsistent, and the live daemon implemented it literally

Coordinator decision (2026-11-15) settled the pair: **5% DD kill
unchanged; per-trade risk 0.1% on pooled books; aggregate portfolio-heat
cap 2% of equity per strategy; daily breaker 3%; leverage 3x;
vol-targeting banned for dow_effect** — implemented by TASK-STR-FWD-006.
This audit's part: what was enforced *before* the decision, and whether
the DD-kill computation matches the protocol (above: it does).

**Before the decision, the live daemon enforced:**
| Dimension | Enforced | Evidence |
|---|---|---|
| Per-trade risk | 1% of equity, exact sizing math | harness C1; live env `=0.01` |
| Concurrency | count caps only: 30/venue + 30 total (engine), one position per symbol | live env; `can_open_position` |
| Aggregate heat | **nothing — no heat computation exists** in daemon, engine, or forward_guard (grep: zero hits) | code audit |

Worst case under the old rules: 30 concurrent × 1% = **30% of equity at
risk**; RD-011 measured average concurrency 11.9 (ichimoku) / 21.3 (dow)
on the judged OOS streams = **12–21% typical heat** against a 5% DD kill
line. **Literal application (RD-011 simulation on RD-002's own OOS
streams): ichimoku killed on day 2, dow_effect on day 4** — both forward
entrants dead on ordinary variance, before any forward evidence could
accumulate. The inconsistency was real, and it was live.

**Post-decision verification (this crew, after FWD-006 lands):** live env
sizing denominated on venue equity at 0.1%; deployed daemon contains a
heat gate summing open per-trade risk per strategy per venue, refusing
entries beyond 2% of venue equity; DD kill marking to market (closed +
unrealized) on scan cadence; sleeve under the same rules. *Status at
audit delivery: FWD-006 had not yet landed — main `c2781b61` differs
from the audit base only by FWD-003's FORWARD_TEST lane; no heat code
exists on main and the live env still reads 0.01. This section completes
when their PR merges and deploys.*

## Baseline verification — FWD-002's pre-fix ground truth, independently checked

FWD-002 read the deployed code + live .env and reported five baseline
claims. This audit re-derived each from code, harness and the live
probe; four confirm, one is refuted in part:

1. **Per-trade risk = 1% of COMPOSITE equity — CONFIRMED.** Daemon
   sizing consumes `get_risk_summary()["total_equity"]`, which sums
   both venues; live `daily_start_equity = 20572.46` (demo-fapi
   ~$10.5k + OANDA ~$10k). Each crypto trade therefore risks ~$206 ≈
   **2% of the venue capital it sits on**.
2. **No aggregate heat cap — CONFIRMED.** Only the engine's count caps
   (live 30/venue, 30 total), one-position-per-symbol, and margin
   floors (venue free-margin > 0; per-order notional ≤ 80% of free
   margin). Worst case 30 × 1% = **30% of composite ≈ 60% of the
   crypto venue** at risk simultaneously.
3. **Notional cap binds first for tight stops, never for the wide-stop
   sleeve shock leg — CONFIRMED, boundary made precise.** The 10%-of-
   composite notional cap binds ⟺ stop distance < 10% of price; when
   it binds, effective risk = 10% × stop_pct (a 3% stop → 0.3%/trade,
   matching the reported winners' effective ≈0.3–1.0%). The sleeve
   shock leg's judged stop is 2.0 × weekly ATR(14) (`sl_method`,
   config_strategy) — in the wide regime where risk sizing, not the
   cap, binds, so it takes the full 1% of composite. (Band note: stops
   beyond the 15% env band maximum are refused outright.)
4. **DD kill: closed fills only, once per UTC day, skipped on restart
   days, breach never force-closes — CONFIRMED in full** (see the
   cadence weakness in §3; the guard's only action is the persisted
   denylist + the sleeve pause file).
5. **"The 3% daily breaker sees unrealized PnL" — REFUTED for the
   daemon path; true only of the standalone OANDA engine.** The
   daemon/engine latch is driven exclusively by *realized* day PnL —
   `MultiVenueEngine._check_daily_loss_limit` states the design
   ("REALIZED day PnL only; unrealized swings would halt on noise")
   and the daemon's belt-and-braces re-check uses the same realized
   figure. The unrealized-inclusive `daily_loss_pct` in
   `get_risk_summary` is telemetry: no code latches on it. The OANDA
   standalone trader's breaker *is* NAV-based (equity vs day-start
   NAV, unrealized included). "Only blocks NEW entries" is **true for
   both paths**: exits and position management run before the gate in
   every cycle.

## Residuals documented, not fixed (out of this task's guard scope)
- `MultiVenueEngine` constructor defaults (`risk_per_trade_pct=0.02`,
  `max_daily_loss_pct=1.0` = "no daily loss limit") are unsafe-looking;
  the daemon entrypoint always overrides them from env (defaults
  0.005 / 0.03). Any *future* entrypoint that constructs the engine bare
  would inherit the unsafe defaults.
- `engine.place_order` re-checks position counts only — breaker, pause
  and panic gates live in the daemon's paths. The only other
  `place_order` callers are legacy/retired engines.
- `execution/live_execution_engine.py` (mounted by the dashboard) is a
  simulation — it fills its own orders and places nothing on any venue.

## Test evidence
- Audit harness (stub venues, no orders): 27/27 checks PASS across
  forward_guard (6), daily breaker (7), daemon sizing/pause (7), adapter
  gate/leverage (5 — of which 3 *reproduce the defects* fixed here),
  OANDA engine (5, separate run).
- New regression suite `tests/test_str_risk_001_guard_hardening.py`: 9/9.
- Adjacent suites with the fixes applied: live-gate 12 + live-trading
  guard 13 + daemon governance + OANDA pause = 48 passed; 6 failures in
  `test_trading_pause_wiring.py` write-path tests are a sandbox artifact
  (this sandbox's fsync returns EPERM in bursts — the same tests pass in
  isolation; the operative gate is server-side pytest per protocol).
