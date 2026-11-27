# TASK-STR-078 — CHECKPOINT 6: demo-only safety audit (no real order path in scope)

- **Task:** TASK-STR-078 — REPO-IMPLEMENT: Stratex repos (FinRL, Lumibot, Vibe-Trading, AutoHedge, QATS), wave 1, P1
- **Owner:** Muse 11
- **Filed:** 2026-11-25 ~15:25 IST
- **Branch:** `muse11/task-str-078-repo-implement` (head before this file: `93d10af4`, checkpoint 5)
- **Main verified:** `c554c54f` (PR #1802 VOI-036 merged; parent `ec46d5f0`)
- **Board:** `docs/collaboration/WORK_BOARD.yaml`, blob `c5b4afb2`, 22,742 lines — STR-078 CLAIMED/muse_11, branch `muse11/task-str-078-repo-implement`, pr null. Queue STR-078 → FRG-030 → FRG-021 stands (FRG-030/FRG-021 AVAILABLE/owner muse_11).

## 1. Assignment and hub — no new direction

- Hub #1483 read through latest comment `7158821992` (Muse 8 claiming STR-084, 15:18:14 IST). **WATCH091 read in full (7158754888, ~15:16 IST): no direction to Muse 11, no live-trial/restart clearance.**
- Watch091 items noted: merges #1809 (INF-036) + #1802 (VOI-036); #1811 STR-082 HELD (CI test failure, exact string mismatch); M15 assigned FRD-054; TP7 FRD-052 read-only live probes CLEARED (failure-injection legs still need exact commands + drill window + rollback); carried: consolidated board PR, merges #1805/#1806, **M18 Lumibot standalone PR**, M20 STR-085 ruling, TP8 VYR-061 deploy clearance.
- **M18 Lumibot standalone PR is now filed: PR #1815**, branch `muse18/fix-lumibot-backtest-never-trades`, "Fix LumibotBacktest.run() never trading (signal list/dict indexing)". The item owed since checkpoint 2 / watch089 is closed on the filing side; merge is the coordinator's call. Muse 11 does not touch it (watch089 ruling stands).
- M18 claimed API-007 as head (hub 7158752515, ~15:15 IST) — Muse 11's former task; no action. M8 claimed STR-084 (7158821992); its board flip rides in M8's work PR.
- No hub post this run per owner order 7143628341 rule 7 (checkpoint only, no claim/completion/block).

## 2. Safety audit — the demo-only commitment, proven in code, not by assertion

Question answered first-hand: **can anything in the STR-078 live-wired scope place a real order on a real venue? Answer: no — every order path in scope is simulated in-memory, and no code path calls a real broker/exchange order API.**

Files read in full from main `c554c54f` via the GitHub API (blob SHAs verified, all unchanged vs checkpoint 5):

| File | SHA | Lines | Finding |
|---|---|---|---|
| `Stratex/app/trading_hub.py` | `79e51b74` | 134 | Zero order calls. `debate_trade_decision` returns advisory `"BUY"`/`"SELL"` string + Kelly fraction only. CCXT used for `fetch_ticker` / `find_arbitrage_opportunities` only. No `BrokerConfig`, no `is_paper`, no `allow_trading` in this file. |
| `Stratex/api/real_trading_routes.py` | `e4b682ba` | 637 | Only `buy`/`sell` hits (L180/182) are `BacktestEngine.buy/sell` inside `/autohedge/backtest` — an in-memory simulated ledger (`initial_capital`, `cash`, `positions`), no broker. `/autohedge/rebalance` returns a computed `"orders"` list, never executes it. No `is_paper`/`allow_trading` in this file. |
| `Stratex/app/agents/real_lumibot.py` | `505d8943` | 394 | `BrokerConfig.trading_type` defaults `"paper"` (L47); `is_paper` property (L53). `LumibotStrategy.submit_order` (L166) fills market orders **only if `is_paper`**, against in-memory cash/positions; with `trading_type="live"` the order stays `"submitted"`, cash unchanged, no position — and **no external broker API call exists anywhere in the class**. `run_live_or_simulated_backtest` (L361): "live" = Yahoo Finance price-history fetch if available, else a deterministic simulated curve; computes a price-ratio return, places no orders. |
| `Stratex/app/agents/real_ccxt.py` | `804cdb18` | 448 | `ExchangeBase.create_order` (L274–299) builds a fake order dict `{"id": "order-N", "status": "closed"}` and mutates in-memory `balances`; **it never calls `self._real_client.create_order`**. The real CCXT client is used only for read-only `fetch_balance` (L301) when credentials exist. `ExchangeConfig.api_key` defaults `""`. |
| `Stratex/api/real_engines_routes.py` | `2a3a1efc` | 932 | `POST /ccxt/order` (L575–596) calls `exchange.create_order(...)` with no paper/live gate and no auth check — **but the callee is the simulated `ExchangeBase.create_order` above, so the route cannot reach a real venue through this code**. `POST /lumibot/order` (L843) calls the simulated `strategy.submit_order`. Blueprint prefix `/api/v1/engines`. |

Standalone reproduction (exact main-branch files, run in /tmp, no clone):

- CCXT: `create_order('BTC/USDT','market','buy',0.001,50000.0)` → `{'id': 'order-1', 'status': 'closed'}`, balances `{'USDT': -50.0, 'BTC': 0.001}` in-memory; `_real_client` stays `None` (ccxt not installed here; the method body contains no real-client call in any case). Sell reverses it. No network call.
- Lumibot paper default: `submit_order('AAPL','BUY',10,'market',100.0)` → status `filled`, cash 10000 → 9000, position `(10, 100.0)`.
- Lumibot live config: same call → status `submitted`, cash unchanged 10000, positions `{}` — no fill, no external call.

Exposure note: `real_trading_bp` is registered in `Stratex/dashboard.py` (dashboard app), `real_engines_bp` prefix `/api/v1/engines`. Checkpoint 4's public-gateway probe found no `/api/v1/trading/engines/*` route (405/404) — these routes are not reachable via the public gateway. Even if reached, §2 shows every order path simulates. The demo-only property therefore holds at the engine level, not by gateway accident.

**Implication for acceptance:** the remaining unproven acceptance leg (live demo-daemon cycle + failure injection + full-allowlist load scan, results from the live ledger) is now bounded: the live trial cannot place real orders through this code, so its risk is limited to market-data and ledger behaviour. Live trading still requires Surendra's explicit authorization with a proven forward record in front of him — unchanged, and this audit does not substitute for it.

## 3. Correction to earlier records

- `real_trading_routes.py` lives at **`Stratex/api/real_trading_routes.py`**, not `Stratex/app/` as checkpoints 2–5 implied. Same file (SHA `e4b682ba` matches checkpoint 5); only the path in the record was wrong. Corrected here.

## 4. Live state re-verified this run (~15:20–15:23 IST)

- Both Oracle servers ONLINE (`get_system_info`, bridge v1.30.0; S2 git `2c960cb7`).
- FRIDAY `/health` 200 overall `"healthy"` (15:22:55 IST, friday_core v2.0.0, direct HTTPS GET).
- Memora 401 fix HOLDS: log pull requested 200 lines; bridge returned a truncated view (51 lines visible, 15:20:18–15:21:02 IST) — **0×401 in the visible window**, 4 cursor 200s, 42 /health 200s, PID `3747325` only. Partial-window honesty: the fix-hold conclusion is consistent with every prior full-window check; this run's visible window supports it but is truncated by the bridge output limit.
- Stratex.service inactive (dead) since Nov 24 13:42:11 IST, PID 3578170 TERM — no restart under the owner stop order. Last activity shadow-mode advisory, SHADOW_LOG_ONLY.
- All six STR-078 file SHAs re-verified unchanged on main `c554c54f`: Vibe-Trading `c5a184a1`, AutoHedge `5457505e`, Lumibot `505d8943`, trading_hub `79e51b74`, routes `e4b682ba`, tests `1afe1e73` (carried from checkpoint 5; the four audit files re-fetched this run, all match).

## 5. States, blockers, next

- States: implemented PARTIAL / tested PARTIAL / merged NO / deployed N/A / production-verified NO.
- Blockers unchanged: owner stop order holds the live legs (demo-daemon cycle, failure injection, load scan); live-trial/restart clearance owed.
- Next WORK run: checkpoint 7 — fold the §2 audit bounds into the live-trial design (§4–§5 of checkpoint 2/3), or run the live legs the moment clearance lands.

— Muse 11
