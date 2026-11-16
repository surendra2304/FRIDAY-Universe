# BSE/NSE Cross-Exchange Arbitrage — Concept Note

**TASK-IG2-STR-17 · IG corpus item DXYCIhsjHKY · package S-25**

> **Status: CONCEPT NOTE ONLY.** This document records an idea from the
> owner's Instagram reference corpus and why the fleet does not pursue
> it. It is **not** a strategy, **not** an RD candidate, and carries
> **no declaration, no backtest, and no execution code**. Nothing in
> Stratex reads this note at runtime.

## 1. The concept as presented in the source

The item (@charanandfriends_trading, 2026-04-20; Dhan platform shown)
presents cross-exchange arbitrage: the same security is listed on both
Indian exchanges, BSE and NSE, and momentarily trades at slightly
different prices on each. Buy where it is cheaper, sell where it is
dearer, capture the difference. The watchlist examples shown are ITC,
Bajaj Finance, Maruti Suzuki, Tata Motors Passenger Vehicles, Sun
Pharmaceutical, and Mahindra & Mahindra.

The item's headline illustration is actually a **different** trade and
the two should not be conflated: buy Nifty spot at 24,366 and sell
Nifty futures at 24,394, capturing +28 points — that is cash–futures
(basis) arbitrage, not cross-exchange arbitrage. Two corrections from
the item's own record apply to it: 28 points on 24,366 is ≈0.11%, not
the 1.5% the video states; and an index itself is not tradable ("you
can't buy Nifty spot") — the tradable version is a stock's cash price
against its own futures, which the creator himself clarified in the
comments.

Creator claims, recorded as claims and not adopted: "10% every month
on cap"; stock arbitrage "will work if you hold stocks where banks and
institutions can make it work"; futures arbitrage "will work in Gold";
and, of the retail version, "will work but not for retailers".

## 2. What already exists from this item

Wave 1 already built the measurable core of this concept:
`Stratex/rigorous_backtest/ig/arb_scanner.py` (TASK-IG-STR-07, from
this same item) is a paper-only cross-venue quote scanner — it reports
price discrepancies that survive both sides' taker fees and a
slippage buffer, journaled to an append-only hash-chained paper log.
It has **no execution path**: no order functions, no venue clients, no
keys. That module is the fleet's entire implementation footprint for
this concept family, and this note does not modify it.

Programme context: RD-006 (pairs/statistical arbitrage) closed with
zero passers at the full bar, and the scanner's own header carries its
lesson — paper edges that ignore frictions do not survive contact
with costs.

## 3. What the concept would require on this fleet

**Data.** Synchronised tick-level quotes from *both* exchanges for the
same securities, with exchange timestamps. The discrepancy lives for
milliseconds; anything slower (snapshots, minute bars, delayed feeds)
measures stale quotes, not opportunities. Licensed BSE/NSE real-time
feeds are paid products — the fleet's free-only rule excludes them —
and no Indian market data feed exists anywhere in the fleet today.

**Execution.** Indian broker accounts with dual-exchange algo APIs,
SEBI algo-trading compliance for the account holder, and genuinely
simultaneous two-leg execution: a fill on one leg only is directional
exposure, not arbitrage. Stratex's current venues are crypto and FX
(Binance, OANDA, MT5 demo); there is no BSE/NSE venue, account, or API
in the fleet.

**Latency.** The gap is harvested by co-located HFT systems in
microseconds — the item's own comment record makes this point in
detail. The fleet runs on two ~956 MB Oracle VMs on another continent.
It is not, and cannot be made, latency-competitive for this trade.

**Costs.** Brokerage, STT, exchange transaction charges, GST, and
slippage on *both* legs, against a gross edge the item itself
illustrates at ~0.1% before costs. The item's comment record again:
"Charges are higher than spread."

**Settlement and liquidity.** T+1 settlement in Indian equities
(raised in the item's own record) constrains same-day round-trips of
delivered stock. Liquidity is asymmetric across the two exchanges —
many securities are liquid on NSE and thin on BSE — so the apparently
cheaper quote is often not fillable in size.

## 4. Why this is a concept note and not a strategy

- **There are no testable rules in the source.** No instrument
  universe, no minimum-edge threshold net of a stated cost model, no
  sizing, no handling of a one-legged fill, no exit rule. A
  pre-declaration cannot be frozen from a concept illustration, and
  this lane does not declare what the source does not contain.
- **The measurable version already exists** (the paper scanner,
  §2). Promoting it toward a strategy would require the licensed
  dual-exchange data of §3 *plus* the full RD programme bar — ≥200
  out-of-sample trades, PF ≥ 1.2, positive folds, 2× costs,
  Bonferroni, holdout — on realistically modelled fills. None of that
  can start without the data.
- **The source itself places the viable version elsewhere.** The
  creator's own assessment in the item's record is that it does not
  work for retail and works for institutions holding inventory and
  running co-located infrastructure.

## 5. What would have to change for this to be revisited

Both of the following, in order:

1. A licensed, timestamped, dual-exchange tick dataset becomes
   available to the fleet within the free-only rule, enabling an
   honest paper study of how often a net-of-cost edge exists at
   fleet-observable latency; and
2. a pre-declared RD candidate with frozen rules and a frozen cost
   model, judged at the full programme bar.

Until both hold, this stays a concept note. This note creates no
follow-up task and no standing obligation.

---

*Sources: item file `DXYCIhsjHKY.md` (connector record + browser
watch, graded FULL, 2026-11-16); package S-25 in the IG lane package
for Stratex; `arb_scanner.py` header (TASK-IG-STR-07); RD-006 closure
record. Fleet facts (venues, host size, free-only rule) are the
coordinator's standing record.*
