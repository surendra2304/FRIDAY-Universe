"""
research/whale_flow_tracker.py — On-chain / whale-flow research tracker (TASK-IG2-STR-07).

Pattern adopted from the claude-trading-skills catalogue (agiprolabs, MIT):
poll free public market/on-chain endpoints for large-flow anomalies and
surface them as *research inputs* for Stratex.

Scope and safety:
- FREE, no-key endpoints only: DexScreener, CoinGecko, DeFiLlama.
  (Keyed services named in the source card — Birdeye, Helius — are excluded.)
- RESEARCH ONLY. Signals produced here are never trade triggers: this module
  imports nothing from execution/risk code and exposes no order path.
  Stratex remains DEMO-ONLY.
- Lightweight: stdlib + ``requests`` (already a Stratex dependency), storage
  follows Stratex's ledger pattern (append-only JSONL + a small JSON
  baseline file; no new database backend), sized for the ~180MB
  per-service fleet cap.

Signals detected per watched symbol:
- ``DEX_VOLUME_SPIKE``   — DexScreener 1h volume is an outsized share of 24h volume.
- ``DEX_FLOW_IMBALANCE`` — DexScreener 1h buy/sell transaction imbalance.
- ``SPOT_VOLUME_SPIKE``  — CoinGecko 24h volume jumps vs the stored baseline.
- ``TVL_SHIFT``          — DeFiLlama chain TVL moved sharply in 24h (context).

All parsing/detection logic is pure and unit-tested with an injected fetcher;
no network is needed to test.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

try:  # Stratex modules run with Stratex/ on sys.path
    from logger import get_logger
except Exception:  # pragma: no cover - fallback when imported as a package
    import logging

    def get_logger(name: str):  # type: ignore
        return logging.getLogger(name)


logger = get_logger("whale_flow_tracker")

RESEARCH_ONLY = True  # signals are research inputs, NEVER auto-trade triggers

DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
COINGECKO_MARKETS_URL = "https://api.coingecko.com/api/v3/coins/markets"
DEFILLAMA_CHAINS_URL = "https://api.llama.fi/v2/chains"

DEFAULT_WATCHLIST: dict[str, str] = {
    # symbol -> CoinGecko id
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
}

# Anomaly thresholds (research heuristics, deliberately conservative).
VOLUME_SPIKE_1H_SHARE = 0.25      # 1h volume >= 25% of the whole 24h volume
FLOW_IMBALANCE_RATIO = 2.0        # buys >= 2x sells (or inverse) in 1h
MIN_TXNS_1H = 200                 # ignore thin pairs for imbalance signals
SPOT_VOLUME_JUMP_PCT = 50.0       # +50% vs stored 24h-volume baseline
TVL_SHIFT_PCT = 5.0               # chain TVL 24h move worth flagging
DEDUPE_WINDOW_S = 3600            # same (symbol, kind) suppressed for 1h


@dataclass
class DexPairStats:
    symbol: str
    pair_count: int
    volume_h24: float
    volume_h1: float
    buys_h1: int
    sells_h1: int
    liquidity_usd: float


@dataclass
class FlowSignal:
    symbol: str
    kind: str
    severity: str  # "info" | "notable" | "strong"
    detail: str
    metrics: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    observed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# Pure parsers (unit-tested without network)
# --------------------------------------------------------------------------

def parse_dexscreener_pairs(payload: dict[str, Any], symbol: str) -> DexPairStats:
    """Aggregate DexScreener search results for one base symbol."""
    volume_h24 = volume_h1 = liquidity = 0.0
    buys = sells = 0
    count = 0
    for pair in payload.get("pairs") or []:
        base = (pair.get("baseToken") or {}).get("symbol", "")
        if base.upper() != symbol.upper():
            continue
        count += 1
        vol = pair.get("volume") or {}
        volume_h24 += float(vol.get("h24") or 0.0)
        volume_h1 += float(vol.get("h1") or 0.0)
        txns = (pair.get("txns") or {}).get("h1") or {}
        buys += int(txns.get("buys") or 0)
        sells += int(txns.get("sells") or 0)
        liquidity += float((pair.get("liquidity") or {}).get("usd") or 0.0)
    return DexPairStats(symbol.upper(), count, volume_h24, volume_h1,
                        buys, sells, liquidity)


def parse_coingecko_market(payload: Any, coingecko_id: str) -> Optional[dict[str, Any]]:
    """Pick one coin out of a CoinGecko /coins/markets response."""
    rows = payload if isinstance(payload, list) else []
    for row in rows:
        if row.get("id") == coingecko_id:
            return {
                "price_usd": float(row.get("current_price") or 0.0),
                "volume_24h": float(row.get("total_volume") or 0.0),
                "change_24h_pct": float(row.get("price_change_percentage_24h") or 0.0),
            }
    return None


def parse_defillama_chains(payload: Any) -> dict[str, float]:
    """Map chain name -> 24h TVL change % from DeFiLlama /v2/chains."""
    out: dict[str, float] = {}
    rows = payload if isinstance(payload, list) else []
    for row in rows:
        name = row.get("name")
        change = row.get("change_1d")
        if name and change is not None:
            out[str(name)] = float(change)
    return out


# --------------------------------------------------------------------------
# Pure anomaly detection
# --------------------------------------------------------------------------

def detect_dex_anomalies(stats: DexPairStats, now: float) -> list[FlowSignal]:
    signals: list[FlowSignal] = []
    if stats.volume_h24 > 0 and stats.volume_h1 > 0:
        share = stats.volume_h1 / stats.volume_h24
        if share >= VOLUME_SPIKE_1H_SHARE:
            signals.append(FlowSignal(
                symbol=stats.symbol, kind="DEX_VOLUME_SPIKE",
                severity="strong" if share >= 0.4 else "notable",
                detail=(f"DEX 1h volume ${stats.volume_h1:,.0f} is {share:.0%} of "
                        f"24h volume ${stats.volume_h24:,.0f} across "
                        f"{stats.pair_count} pairs"),
                metrics={"volume_h1": stats.volume_h1, "volume_h24": stats.volume_h24,
                         "share": round(share, 4), "liquidity_usd": stats.liquidity_usd},
                source="dexscreener", observed_at=now))
    total_txns = stats.buys_h1 + stats.sells_h1
    if total_txns >= MIN_TXNS_1H and stats.buys_h1 > 0 and stats.sells_h1 > 0:
        ratio = max(stats.buys_h1, stats.sells_h1) / min(stats.buys_h1, stats.sells_h1)
        if ratio >= FLOW_IMBALANCE_RATIO:
            side = "buy" if stats.buys_h1 > stats.sells_h1 else "sell"
            signals.append(FlowSignal(
                symbol=stats.symbol, kind="DEX_FLOW_IMBALANCE",
                severity="notable" if ratio < 3.0 else "strong",
                detail=(f"DEX 1h flow imbalance {side}-heavy: {stats.buys_h1} buys vs "
                        f"{stats.sells_h1} sells ({ratio:.1f}x)"),
                metrics={"buys_h1": stats.buys_h1, "sells_h1": stats.sells_h1,
                         "ratio": round(ratio, 3)},
                source="dexscreener", observed_at=now))
    return signals


def detect_spot_volume_spike(symbol: str, current_volume_24h: float,
                             baseline_volume_24h: Optional[float],
                             now: float) -> Optional[FlowSignal]:
    if not baseline_volume_24h or baseline_volume_24h <= 0 or current_volume_24h <= 0:
        return None
    jump_pct = (current_volume_24h - baseline_volume_24h) / baseline_volume_24h * 100.0
    if jump_pct >= SPOT_VOLUME_JUMP_PCT:
        return FlowSignal(
            symbol=symbol.upper(), kind="SPOT_VOLUME_SPIKE", severity="notable",
            detail=(f"Spot 24h volume ${current_volume_24h:,.0f} is {jump_pct:+.0f}% vs "
                    f"baseline ${baseline_volume_24h:,.0f}"),
            metrics={"volume_24h": current_volume_24h,
                     "baseline_volume_24h": baseline_volume_24h,
                     "jump_pct": round(jump_pct, 2)},
            source="coingecko", observed_at=now)
    return None


def detect_tvl_shifts(chain_changes: dict[str, float], chains: list[str],
                      now: float) -> list[FlowSignal]:
    signals: list[FlowSignal] = []
    for chain in chains:
        change = chain_changes.get(chain)
        if change is not None and abs(change) >= TVL_SHIFT_PCT:
            signals.append(FlowSignal(
                symbol=chain.upper(), kind="TVL_SHIFT",
                severity="info" if abs(change) < 10 else "notable",
                detail=f"{chain} TVL moved {change:+.1f}% in 24h (DeFiLlama)",
                metrics={"tvl_change_1d_pct": change},
                source="defillama", observed_at=now))
    return signals


# --------------------------------------------------------------------------
# Default HTTP fetcher (free public endpoints, no keys)
# --------------------------------------------------------------------------

def default_fetch_json(url: str, params: Optional[dict[str, Any]] = None,
                       timeout: float = 15.0) -> Any:
    import requests  # already a Stratex dependency

    resp = requests.get(
        url, params=params, timeout=timeout,
        headers={"User-Agent": "FRIDAY-Stratex-Research/1.0 (+free public data)"},
    )
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------
# Tracker with JSONL signal log + JSON baselines (Stratex ledger pattern)
# --------------------------------------------------------------------------

class WhaleFlowTracker:
    """Polls free endpoints and records whale-flow research signals."""

    def __init__(self, signals_path: str = "whale_flow_signals.jsonl",
                 baselines_path: Optional[str] = None,
                 watchlist: Optional[dict[str, str]] = None,
                 tvl_chains: Optional[list[str]] = None,
                 fetch_json: Callable[..., Any] = default_fetch_json,
                 dedupe_window_s: int = DEDUPE_WINDOW_S):
        self.signals_path = signals_path
        self.baselines_path = baselines_path or (signals_path + ".baselines.json")
        self.watchlist = watchlist or dict(DEFAULT_WATCHLIST)
        self.tvl_chains = tvl_chains or ["Ethereum", "Solana", "Arbitrum"]
        self.fetch_json = fetch_json
        self.dedupe_window_s = dedupe_window_s

    # -- storage helpers ---------------------------------------------------
    def _read_signals(self) -> list[dict[str, Any]]:
        if not os.path.exists(self.signals_path):
            return []
        out: list[dict[str, Any]] = []
        with open(self.signals_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return out

    def _recently_emitted(self, symbol: str, kind: str, now: float) -> bool:
        latest = 0.0
        for row in self._read_signals():
            if row.get("symbol") == symbol and row.get("kind") == kind:
                latest = max(latest, float(row.get("observed_at") or 0.0))
        return latest > 0 and now - latest < self.dedupe_window_s

    def _store(self, signal: FlowSignal) -> None:
        with open(self.signals_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(signal.to_dict()) + "\n")

    def _read_baselines(self) -> dict[str, Any]:
        if os.path.exists(self.baselines_path):
            try:
                with open(self.baselines_path, encoding="utf-8") as fh:
                    return json.load(fh)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _baseline(self, symbol: str) -> Optional[float]:
        row = self._read_baselines().get(symbol)
        return float(row["volume_24h"]) if row else None

    def _set_baseline(self, symbol: str, volume: float, now: float) -> None:
        baselines = self._read_baselines()
        baselines[symbol] = {"volume_24h": volume, "updated_at": now}
        with open(self.baselines_path, "w", encoding="utf-8") as fh:
            json.dump(baselines, fh)

    def recent_signals(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._read_signals()
        rows.sort(key=lambda r: float(r.get("observed_at") or 0.0), reverse=True)
        return rows[:limit]

    # -- polling ------------------------------------------------------------
    def poll_once(self, now: Optional[float] = None) -> list[FlowSignal]:
        """One poll cycle across all sources. Source failures are isolated:
        a dead free endpoint degrades coverage, it never crashes research."""
        now = now if now is not None else time.time()
        emitted: list[FlowSignal] = []

        def _emit(signals: list[FlowSignal]) -> None:
            for sig in signals:
                if not self._recently_emitted(sig.symbol, sig.kind, now):
                    self._store(sig)
                    emitted.append(sig)

        # DexScreener per-symbol DEX flow
        for symbol in self.watchlist:
            try:
                payload = self.fetch_json(DEXSCREENER_SEARCH_URL, params={"q": symbol})
                stats = parse_dexscreener_pairs(payload, symbol)
                _emit(detect_dex_anomalies(stats, now))
            except Exception as exc:  # free endpoint down -> skip, don't crash
                logger.warning(f"[WHALE_FLOW] DexScreener poll failed for {symbol}: {exc}")

        # CoinGecko spot volume vs baseline
        try:
            ids = ",".join(self.watchlist.values())
            payload = self.fetch_json(
                COINGECKO_MARKETS_URL,
                params={"vs_currency": "usd", "ids": ids})
            for symbol, cg_id in self.watchlist.items():
                market = parse_coingecko_market(payload, cg_id)
                if not market:
                    continue
                sig = detect_spot_volume_spike(
                    symbol, market["volume_24h"], self._baseline(symbol), now)
                if sig:
                    _emit([sig])
                self._set_baseline(symbol, market["volume_24h"], now)
        except Exception as exc:
            logger.warning(f"[WHALE_FLOW] CoinGecko poll failed: {exc}")

        # DeFiLlama chain TVL context
        try:
            payload = self.fetch_json(DEFILLAMA_CHAINS_URL)
            _emit(detect_tvl_shifts(parse_defillama_chains(payload), self.tvl_chains, now))
        except Exception as exc:
            logger.warning(f"[WHALE_FLOW] DeFiLlama poll failed: {exc}")

        if emitted:
            logger.info(f"[WHALE_FLOW] {len(emitted)} new research signal(s): "
                        + ", ".join(f"{s.symbol}:{s.kind}" for s in emitted))
        return emitted
