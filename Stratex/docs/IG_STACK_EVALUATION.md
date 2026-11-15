# IG stack evaluation — MT5 venue, OpenBB data layer, NautilusTrader, curated repos

TASK-IG-STR-12 (evaluation part). Sources: IG corpus items DYpKBKgKkoJ
(MT5 tutorial), Dc6T3_CSDSE (packaged market-data pipelines),
DcayVNzjuqQ (curated algo-trading repos), DegcLifkzmE (OpenTerminal +
OpenBB + NautilusTrader composition), DcJyszBG6VF (strategy
marketplace/stacking — code part in `strategy_stacking.py`).
Repo-card verdicts bind: OpenBB **adapt**, NautilusTrader
**reference-only**. Verified against main on 2026-11-15.

## 1. MetaTrader 5 as an execution venue — verdict: DO NOT ADOPT (now)

Facts:

- MT5's automation surface is a Windows desktop terminal; the official
  Python package drives a running terminal and is Windows-only. The
  repo already carries this shape: `Stratex/mt5_bridge/`
  (`server.py`, `requirements-windows.txt`) plus
  `docs/BINANCE_MT5_ROLLOUT.md` — scaffolding that presumes a Windows
  host the fleet does not have (two ~1 GB Linux VMs).
- Stratex's governed demo venues already cover the strategy universe
  under test: Binance demo-fapi (crypto) and OANDA practice (FX),
  both wired into the Phase-3 forward protocol with ledgers and the
  decided risk package. A third venue adds credential, reconciliation,
  and failure surface while adding no instrument the RD programme is
  currently blocked on (the known venue gap is the reverse: RD-003's
  comm7 candidates had *no* mappable venue).
- The RD bar is venue-agnostic. Nothing about MT5 exempts a strategy
  from it, and nothing about the bar requires MT5.

Revisit trigger: a strategy family passes the full bar on the existing
panels and is *only* expressible on MT5 instruments. Until then the
bridge code stays as-is — unused by the governed lanes, not extended.

## 2. OpenBB data layer — consume-side interface spec (build is Futuris's)

The corpus's "compose on an OpenBB-style data layer" idea (DegcLifkzmE)
is owned by the Futuris lane for the build; the repo also carries a
legacy Stratex-side adapter (`Stratex/stratex_openbb/`). This lane
builds **no second adapter**. What Stratex research needs from any
data layer, whoever builds it:

```
get_ohlcv(symbol, timeframe, start, end) -> {
  "candles": [{"ts", "open", "high", "low", "close", "volume"}, ...],  # ascending, gap-explicit
  "provenance": {"source", "fetched_at", "licence", "content_hash"}
}
get_funding(symbol, start, end) -> {
  "prints": [{"ts", "rate"}, ...],
  "provenance": {...}   # same shape
}
```

Contract rules (from DATA-001 discipline): panels are
provenance-verified and hash-pinned before an RD run touches them;
gaps are reported, never forward-filled silently; a series that cannot
state its source does not enter a backtest. RD-017's funding work is
the worked example of the funding half.

## 3. NautilusTrader — reference-only (card verdict, binding)

No integration. The repo's `Stratex/stratex_nautilus/` experiments
stay experiments. Rationale: the evidence engine of record is
`Stratex/rigorous_backtest/` — the promotion bar, fold structure, cost
model, and holdout check live there, and every RD verdict to date is
comparable because it was produced by that one harness. A second
engine would fork the evidence base. NautilusTrader remains useful
reading for execution-modelling ideas (event model, deterministic
runtime) if the demo daemon's fill model is ever upgraded.

## 4. Curated algo repos (DcayVNzjuqQ) + packaged data pipelines (Dc6T3_CSDSE)

The roundup's member repos are not named in our data (see
`~/workspace/ig-references/repos/INDEX.md`), so nothing is adopted
from it directly — unnamed components do not enter the stack. The
adoption method the corpus work established stands: a component gets
a verified repo card and a fit verdict first (32 cards exist), then a
lane implements against the card. Already flowing from that process:

- day-trader-skill → skill-chain structure + Time Machine pattern
  (TASK-IG-STR-04, TASK-IG-STR-05)
- tradermonty/claude-trading-skills → journaling/post-mortem structure
  (TASK-IG-STR-05)
- agiprolabs/claude-trading-skills → reference-only (no action)

Dc6T3_CSDSE's "packaged market-data products" pattern is, in FRIDAY
terms, DATA-001's provenance-verified panels plus the §2 contract —
the packaging discipline is adopted, the unnamed products are not.

## 5. What this evaluation does not do

It authorises no venue, no adapter, and no strategy. Venue changes are
governance decisions under the forward protocol; this document is the
evidence pack for one: MT5 — no; OpenBB — consume via contract,
Futuris builds; NautilusTrader — read, don't integrate.
