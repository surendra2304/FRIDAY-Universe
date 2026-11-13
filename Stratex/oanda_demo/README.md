# Stratex OANDA Demo Trading (oanda_demo)

Owner directive (2026-11-13): *store the OANDA demo key in credentials.md,
implement OANDA demo trading, and make Stratex take profitable trades.*

This module is the result: a credential loader, three strategy engines, a
live trading engine with a risk governor, a historical validator, and a live
selftest — all against the OANDA **practice** environment (demo funds only;
the live environment is never used without owner approval).

## Components

| File | Purpose |
|---|---|
| `credentials.py` | Resolves OANDA_API_KEY / OANDA_ACCOUNT_ID from env, else `credentials.md` (never logs values) |
| `strategy.py` | Three engines: SMT-v2 (EMA stack, TP-capped), Donchian-v3 (breakout + chandelier trail), **FX-MR-v4 (RSI-2 mean reversion — the validated default)** |
| `trader.py` | Live engine: scan → signal → size → MARKET order with native SL → manage exits → log + Telegram |
| `backtest.py` | Event-driven validator on real OANDA history (paginated to 10k bars, spread costs, conservative SL-first fills) |
| `selftest.py` | Live API proof: account, pricing, candles, precision, **1-unit order round-trip** |

## Why mean reversion is the default (evidence, 2026-11-13)

Every candidate was validated on the same 8-pair basket (EURUSD, GBPUSD,
USDJPY, AUDUSD, USDCAD, NZDUSD, EURJPY, EURGBP) with real practice-account
spreads before being allowed to trade:

| Strategy | D1, 20 years | H4, 2.9 years | Verdict |
|---|---|---|---|
| SMT-v2 (EMA-stack, TP-capped) | −8R / 62 trades | −309R / 3,240 trades (filters) | rejected |
| Donchian-v3 (breakout + trail) | −97R / 704 trades | −206R / 1,456 trades | rejected |
| **FX-MR-v4 (RSI-2 reversion)** | **+19.5R / 1,302 trades, 64.4% win, max DD ≈ 6%** | n/a (spread filter blocks H4 by design) | **live default** |

Robustness: 10y/10y holdout split is positive in BOTH halves (+11.3R first
decade, +7.2R second). The only consistently trending pair (USDJPY, PF 1.18
on Donchian D1) confirms the regime read: the basket mean-reverts.

Strategy rules (FX-MR-v4): long when RSI(2) < 10 with close > EMA200 (short
mirrored); exit when close re-crosses EMA5 or after 10 bars; 4×ATR disaster
stop attached to every order; skip entries when spread > 15% of ATR.

## Risk governor (live)

- 1% of equity risked per trade (notional-capped at 25% of equity)
- Max 4 concurrent positions, one per instrument
- −3% daily NAV circuit breaker stops new entries for the day
- 60-minute per-instrument re-entry cooldown after a close
- Kill switch: `touch Stratex/data/oanda_demo_kill_switch` halts the engine
- Every order carries a native OANDA stop (survives restarts)

## Operations

```bash
cd Stratex
python3 -m oanda_demo.selftest                      # live verification
python3 -m oanda_demo.trader --status               # account + open trades
python3 -m oanda_demo.trader --once [--dry-run]     # one scan
python3 -m oanda_demo.trader --loop --interval 300  # daemon mode
python3 -m oanda_demo.trader --flatten              # emergency close-all
python3 -m oanda_demo.backtest --strategy mr --granularity D --pages 1
```

Production runs as `Stratex-OANDA-Demo.service` on Server 1 (see
`deployment/stratex-oanda-demo.service`): 5-minute scan loop, D1 signals,
Telegram trade notifications to the owner chat.

## Credentials

The token lives in the gitignored `credentials.md` master copy (Oracle VMs +
Sync Credentials workflow) and is also exported as
`OANDA_API_KEY` / `OANDA_ACCOUNT_ID` / `OANDA_PRACTICE=true` in
`Stratex/.env`. Practice account `101-001-40988523-001` (USD 100,000 demo).
