"""Plain-English backtest spec -> structured plan (Vibe-Trading pattern).

Upstream turns natural-language prompts into runnable backtests via an LLM
agent stack. The fleet-feasible port is a deterministic grammar — no LLM,
no network — covering the phrasing Stratex's RD notes actually use:

    backtest ma_crossover on BTC/USDT with fast=10 slow=50 lookback 365 fee 5bps

Anything outside the grammar raises ValueError naming the grammar, instead
of guessing. The output is a plan for the sweep harness / canonical engine;
parsing never executes anything.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_STRATEGIES = ("ma_crossover", "momentum", "mean_reversion", "bollinger")
_KV = re.compile(r"(fast|slow|window|lookback|fee_bps|fee)\s*=\s*(\d+(?:\.\d+)?)")


@dataclass(frozen=True)
class BacktestPlan:
    strategy: str
    symbol: str
    params: dict[str, float] = field(default_factory=dict)
    source_text: str = ""

    def sweep_grid(self) -> dict[str, tuple]:
        """Single-point grid for Stratex.research.sweep_harness.SweepGrid."""
        if self.strategy == "ma_crossover":
            return {"fast": (int(self.params.get("fast", 10)),),
                    "slow": (int(self.params.get("slow", 50)),)}
        return {"window": (int(self.params.get("window", 20)),)}


def parse_spec(text: str) -> BacktestPlan:
    if not text or "backtest" not in text.lower():
        raise ValueError("spec must start with 'backtest <strategy> on <SYMBOL> ...' "
                         f"(strategies: {', '.join(_STRATEGIES)})")
    m = re.search(r"backtest\s+([a-z_]+)\s+on\s+([A-Za-z0-9/_.\-]+)", text, re.I)
    if not m:
        raise ValueError("could not find '<strategy> on <SYMBOL>' in spec; "
                         f"strategies: {', '.join(_STRATEGIES)}")
    strategy = m.group(1).lower()
    if strategy not in _STRATEGIES:
        raise ValueError(f"unknown strategy {strategy!r}; supported: {', '.join(_STRATEGIES)}")
    params: dict[str, float] = {}
    for key, val in _KV.findall(text):
        params["fee_bps" if key == "fee" else key] = float(val)
    fee = re.search(r"fee\s+(\d+(?:\.\d+)?)\s*bps", text, re.I)
    if fee:
        params["fee_bps"] = float(fee.group(1))
    lb = re.search(r"lookback\s+(\d+)", text, re.I)
    if lb:
        params["lookback"] = float(lb.group(1))
    if strategy == "ma_crossover":
        if "fast" not in params or "slow" not in params:
            raise ValueError("ma_crossover needs fast= and slow= (e.g. fast=10 slow=50)")
        if params["fast"] >= params["slow"]:
            raise ValueError("fast window must be < slow window")
    return BacktestPlan(strategy, m.group(2).upper(), params, text.strip())
