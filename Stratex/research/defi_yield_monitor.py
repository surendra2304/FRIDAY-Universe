"""
research/defi_yield_monitor.py — DeFi LP/yield monitor (TASK-IG2-STR-08).

Pattern adopted from the claude-trading-skills catalogue (agiprolabs, MIT):
track liquidity-pool / yield rates for watched pools and report changes
into Stratex/Futuris research.

Scope and safety:
- ONE free public API: DeFiLlama yields (https://yields.llama.fi/pools),
  no key, no wallet, no funds — research situational awareness only,
  consistent with Stratex DEMO-ONLY discipline.
- Storage follows Stratex's ledger pattern: append-only JSONL snapshots
  (no new database backend); change detection is a pure diff over the
  last two snapshots per pool.

A pool is "watched" by DeFiLlama pool id, or by (project, symbol) pair —
e.g. ("aave-v3", "USDC") or ("uniswap-v3", "WETH-USDC").
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Optional

try:
    from logger import get_logger
except Exception:  # pragma: no cover
    import logging

    def get_logger(name: str):  # type: ignore
        return logging.getLogger(name)


logger = get_logger("defi_yield_monitor")

RESEARCH_ONLY = True

DEFILLAMA_POOLS_URL = "https://yields.llama.fi/pools"

# Change thresholds worth reporting into research notes.
APY_CHANGE_POINTS = 0.5      # absolute APY move, percentage points
APY_CHANGE_PCT = 25.0        # or relative APY move, %
TVL_CHANGE_PCT = 20.0        # TVL move, %

DEFAULT_WATCHLIST: list[dict[str, str]] = [
    {"project": "aave-v3", "symbol": "USDC"},
    {"project": "aave-v3", "symbol": "WETH"},
    {"project": "uniswap-v3", "symbol": "WETH-USDC"},
    {"project": "lido", "symbol": "STETH"},
]


@dataclass
class PoolSnapshot:
    pool_id: str
    project: str
    symbol: str
    chain: str
    apy: float
    apy_base: Optional[float]
    apy_reward: Optional[float]
    tvl_usd: float
    observed_at: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class YieldChange:
    pool_id: str
    project: str
    symbol: str
    kind: str  # "APY_MOVE" | "TVL_MOVE" | "NEW_POOL" | "POOL_GONE"
    detail: str
    previous: Optional[dict[str, Any]] = None
    current: Optional[dict[str, Any]] = None
    observed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# Pure parsing / matching / diffing (unit-tested without network)
# --------------------------------------------------------------------------

def parse_pools(payload: Any) -> list[dict[str, Any]]:
    """Normalize the DeFiLlama /pools payload into plain pool dicts."""
    rows = (payload or {}).get("data") if isinstance(payload, dict) else payload
    out: list[dict[str, Any]] = []
    for row in rows or []:
        out.append({
            "pool_id": str(row.get("pool") or ""),
            "project": str(row.get("project") or ""),
            "symbol": str(row.get("symbol") or ""),
            "chain": str(row.get("chain") or ""),
            "apy": float(row.get("apy") or 0.0),
            "apy_base": (float(row["apyBase"]) if row.get("apyBase") is not None else None),
            "apy_reward": (float(row["apyReward"]) if row.get("apyReward") is not None else None),
            "tvl_usd": float(row.get("tvlUsd") or 0.0),
        })
    return out


def select_watched(pools: list[dict[str, Any]],
                   watchlist: list[dict[str, str]]) -> list[dict[str, Any]]:
    """Pick watched pools by pool id, else by (project, symbol).

    For (project, symbol) entries with several pools (multiple chains),
    the highest-TVL pool wins — it is the liquid, representative one."""
    selected: dict[str, dict[str, Any]] = {}
    for entry in watchlist:
        pool_id = entry.get("pool_id")
        if pool_id:
            for pool in pools:
                if pool["pool_id"] == pool_id:
                    selected[pool_id] = pool
            continue
        project = (entry.get("project") or "").lower()
        symbol = (entry.get("symbol") or "").upper()
        candidates = [p for p in pools
                      if p["project"].lower() == project and p["symbol"].upper() == symbol]
        if candidates:
            best = max(candidates, key=lambda p: p["tvl_usd"])
            selected[best["pool_id"]] = best
    return list(selected.values())


def diff_snapshots(previous: Optional[PoolSnapshot], current: PoolSnapshot) -> list[YieldChange]:
    """Pure change detection between the last snapshot and the new one."""
    if previous is None:
        return [YieldChange(
            pool_id=current.pool_id, project=current.project, symbol=current.symbol,
            kind="NEW_POOL",
            detail=(f"Now watching {current.project} {current.symbol} on {current.chain}: "
                    f"APY {current.apy:.2f}%, TVL ${current.tvl_usd:,.0f}"),
            current=current.to_dict(), observed_at=current.observed_at)]
    changes: list[YieldChange] = []
    apy_delta = current.apy - previous.apy
    apy_rel = (apy_delta / previous.apy * 100.0) if previous.apy else 0.0
    if abs(apy_delta) >= APY_CHANGE_POINTS or abs(apy_rel) >= APY_CHANGE_PCT:
        changes.append(YieldChange(
            pool_id=current.pool_id, project=current.project, symbol=current.symbol,
            kind="APY_MOVE",
            detail=(f"{current.project} {current.symbol} APY {previous.apy:.2f}% -> "
                    f"{current.apy:.2f}% ({apy_delta:+.2f} pts)"),
            previous=previous.to_dict(), current=current.to_dict(),
            observed_at=current.observed_at))
    if previous.tvl_usd > 0:
        tvl_pct = (current.tvl_usd - previous.tvl_usd) / previous.tvl_usd * 100.0
        if abs(tvl_pct) >= TVL_CHANGE_PCT:
            changes.append(YieldChange(
                pool_id=current.pool_id, project=current.project, symbol=current.symbol,
                kind="TVL_MOVE",
                detail=(f"{current.project} {current.symbol} TVL ${previous.tvl_usd:,.0f} -> "
                        f"${current.tvl_usd:,.0f} ({tvl_pct:+.0f}%)"),
                previous=previous.to_dict(), current=current.to_dict(),
                observed_at=current.observed_at))
    return changes


def default_fetch_json(url: str, timeout: float = 30.0) -> Any:
    import requests  # already a Stratex dependency

    resp = requests.get(
        url, timeout=timeout,
        headers={"User-Agent": "FRIDAY-Stratex-Research/1.0 (+free public data)"})
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------------
# Monitor with JSONL snapshot history
# --------------------------------------------------------------------------

class DefiYieldMonitor:
    """Polls DeFiLlama yields for watched pools and reports rate changes."""

    def __init__(self, snapshots_path: str = "defi_yield_snapshots.jsonl",
                 changes_path: Optional[str] = None,
                 watchlist: Optional[list[dict[str, str]]] = None,
                 fetch_json: Callable[..., Any] = default_fetch_json):
        self.snapshots_path = snapshots_path
        self.changes_path = changes_path or (snapshots_path + ".changes.jsonl")
        self.watchlist = watchlist or [dict(e) for e in DEFAULT_WATCHLIST]
        self.fetch_json = fetch_json

    # -- storage ------------------------------------------------------------
    def _read_snapshots(self) -> list[PoolSnapshot]:
        if not os.path.exists(self.snapshots_path):
            return []
        out: list[PoolSnapshot] = []
        with open(self.snapshots_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    out.append(PoolSnapshot(**row))
                except (json.JSONDecodeError, TypeError):
                    continue
        return out

    def _append_jsonl(self, path: str, row: dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")

    def latest_snapshots(self) -> dict[str, PoolSnapshot]:
        latest: dict[str, PoolSnapshot] = {}
        for snap in self._read_snapshots():
            if snap.pool_id not in latest or snap.observed_at >= latest[snap.pool_id].observed_at:
                latest[snap.pool_id] = snap
        return latest

    # -- polling --------------------------------------------------------------
    def poll_once(self, now: Optional[float] = None) -> list[YieldChange]:
        """Fetch all pools once, snapshot the watched ones, diff vs history."""
        now = now if now is not None else time.time()
        try:
            payload = self.fetch_json(DEFILLAMA_POOLS_URL)
        except Exception as exc:
            logger.warning(f"[DEFI_YIELD] DeFiLlama yields poll failed: {exc}")
            return []
        watched = select_watched(parse_pools(payload), self.watchlist)
        previous = self.latest_snapshots()
        changes: list[YieldChange] = []
        seen_ids: set[str] = set()
        for pool in watched:
            snap = PoolSnapshot(observed_at=now, **pool)
            seen_ids.add(snap.pool_id)
            self._append_jsonl(self.snapshots_path, snap.to_dict())
            for change in diff_snapshots(previous.get(snap.pool_id), snap):
                changes.append(change)
                self._append_jsonl(self.changes_path, change.to_dict())
        # Pools watched by explicit id that vanished from the API are worth
        # one note. (project, symbol) entries re-match by TVL each poll and
        # may legitimately move between pools, so they are not flagged.
        for pool_id, prev in previous.items():
            if pool_id not in seen_ids:
                if any(e.get("pool_id") == pool_id for e in self.watchlist):
                    change = YieldChange(
                        pool_id=pool_id, project=prev.project, symbol=prev.symbol,
                        kind="POOL_GONE",
                        detail=f"Watched pool {prev.project} {prev.symbol} no longer "
                               f"returned by DeFiLlama yields API",
                        previous=prev.to_dict(), observed_at=now)
                    changes.append(change)
                    self._append_jsonl(self.changes_path, change.to_dict())
        if changes:
            logger.info(f"[DEFI_YIELD] {len(changes)} yield change(s): "
                        + "; ".join(c.detail for c in changes))
        return changes

    # -- reporting --------------------------------------------------------------
    def research_note(self, changes: Optional[list[YieldChange]] = None) -> str:
        """Markdown research note for the latest state (Stratex/Futuris notes)."""
        lines = ["## DeFi yield monitor — watched pools", ""]
        latest = self.latest_snapshots()
        if not latest:
            lines.append("_No snapshots yet — run a poll first._")
        for snap in sorted(latest.values(), key=lambda s: -s.tvl_usd):
            lines.append(f"- **{snap.project} {snap.symbol}** ({snap.chain}): "
                         f"APY {snap.apy:.2f}%, TVL ${snap.tvl_usd:,.0f}")
        if changes:
            lines += ["", "### Changes this poll"]
            lines += [f"- {c.detail}" for c in changes]
        lines += ["", "_Research only (DeFiLlama free API). No wallet, no funds, "
                      "demo-only discipline._"]
        return "\n".join(lines)
