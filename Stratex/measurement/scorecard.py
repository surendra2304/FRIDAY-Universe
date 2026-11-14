"""
measurement/scorecard.py — per-strategy scorecard from the fill ledger ONLY.

TASK-STR-PHASE2-001, build item 7. Phase 1 found performance claims all
over Stratex's docs with no reproducible source. This generator is the
opposite: every number below is computed from state/fill_ledger.jsonl
rows and nothing else. A strategy with no recorded fills scores zero
trades — stated plainly, never backfilled from backtests or priors.

Per strategy (and per engine, and in total):
  trades, wins/losses, win rate, gross P&L, fees, net P&L,
  expectancy (net per trade), average win / average loss (net),
  profit factor (sum of positive nets / |sum of negative nets|),
  max drawdown of the strategy's cumulative net-P&L curve,
  count of fills whose fees are estimates rather than broker records.

Run on demand:
    python3 -m measurement.scorecard            # write + print
    python3 -m measurement.scorecard --stdout   # print only

Output: state/scorecard.json (atomic) plus log/stdout lines. The daemon
also regenerates it weekly (maybe_regenerate_weekly) so a fresh scorecard
always exists without a human remembering to ask.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from measurement import fill_ledger
except ImportError:  # pragma: no cover - flat layout fallback
    import fill_ledger  # type: ignore

try:
    from atomic_io import atomic_write_json
except Exception:  # pragma: no cover
    atomic_write_json = None  # type: ignore

try:
    from logger import get_logger

    logger = get_logger("measurement_scorecard")
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger("measurement_scorecard")

SCORECARD_FILE = "scorecard.json"
WEEKLY_MAX_AGE_S = 7 * 86400


def scorecard_path() -> Path:
    override = os.getenv("STRATEX_SCORECARD_FILE")
    if override:
        return Path(override)
    return fill_ledger.state_dir() / SCORECARD_FILE


def _stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    rows = sorted(rows, key=lambda r: float(r.get("exit_time") or 0.0))
    nets = [float(r.get("net_pnl") or 0.0) for r in rows]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n < 0]
    gross = sum(float(r.get("gross_pnl") or 0.0) for r in rows)
    fees = sum(abs(float(r.get("fees") or 0.0)) for r in rows)
    net = sum(nets)
    # Max drawdown of the cumulative net curve (peak-to-trough, in $).
    curve = 0.0
    peak = 0.0
    max_dd = 0.0
    for n in nets:
        curve += n
        peak = max(peak, curve)
        max_dd = min(max_dd, curve - peak)
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    return {
        "trades": len(rows),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(rows), 4) if rows else 0.0,
        "gross_pnl": round(gross, 2),
        "fees": round(fees, 2),
        "net_pnl": round(net, 2),
        "expectancy_net_per_trade": round(net / len(rows), 4) if rows else 0.0,
        "avg_win_net": round(gross_profit / len(wins), 2) if wins else 0.0,
        "avg_loss_net": round(-gross_loss / len(losses), 2) if losses else 0.0,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        "max_drawdown": round(abs(max_dd), 2),
        "estimated_fee_fills": sum(
            1 for r in rows if str(r.get("fees_source") or "") != "broker"
        ),
        "first_exit": rows[0].get("recorded_at") if rows else None,
        "last_exit": rows[-1].get("recorded_at") if rows else None,
    }


def build_scorecard(fills: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    if fills is None:
        fills = fill_ledger.read_fills()
    by_strategy: Dict[str, List[Dict[str, Any]]] = {}
    by_engine: Dict[str, List[Dict[str, Any]]] = {}
    for row in fills:
        by_strategy.setdefault(str(row.get("strategy") or "UNATTRIBUTED"), []).append(row)
        by_engine.setdefault(str(row.get("engine") or "unknown"), []).append(row)
    # The governed set renders explicitly even with zero recorded fills, so
    # "0 recorded forward trades" is stated by the scorecard itself rather
    # than implied by an absent row.
    try:
        import os
        import sys

        _stratex_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _stratex_dir not in sys.path:
            sys.path.insert(0, _stratex_dir)
        from config_strategy import PRODUCTION_STRATEGY_REGISTRY

        for _name, _spec in PRODUCTION_STRATEGY_REGISTRY.items():
            if _spec.get("status") in ("VALIDATED", "OBSERVE_ONLY"):
                by_strategy.setdefault(_name, [])
    except Exception:
        pass
    try:
        boundaries = fill_ledger.read_boundaries()
    except Exception:
        boundaries = []
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": "state/fill_ledger.jsonl ONLY",
        "total_fills": len(fills),
        "strategies": {k: _stats(v) for k, v in sorted(by_strategy.items())},
        "engines": {k: _stats(v) for k, v in sorted(by_engine.items())},
        "totals": _stats(fills),
        "reset_boundaries": boundaries,
    }


def render_lines(card: Dict[str, Any]) -> List[str]:
    lines = [
        f"[SCORECARD] generated {card['generated_at']} from {card['source']} "
        f"— {card['total_fills']} recorded fill(s)"
    ]
    for b in card.get("reset_boundaries") or []:
        lines.append(
            f"[SCORECARD] RESET BOUNDARY {b.get('timestamp')} actor={b.get('actor')} "
            "— account reset: balance changes across this line are NOT profit; "
            "pre-boundary records are history, forward measurement re-baselines "
            f"at the post-reset equity. {b.get('note') or ''}".rstrip()
        )
    if not card["strategies"]:
        lines.append("[SCORECARD] No recorded fills yet: every strategy scores 0 forward trades.")
    for name, s in card["strategies"].items():
        pf = s["profit_factor"] if s["profit_factor"] is not None else "n/a"
        lines.append(
            f"[SCORECARD] {name}: trades={s['trades']} win_rate={s['win_rate']:.1%} "
            f"net=${s['net_pnl']:+.2f} expectancy=${s['expectancy_net_per_trade']:+.2f}/trade "
            f"PF={pf} maxDD=${s['max_drawdown']:.2f} fees=${s['fees']:.2f} "
            f"(estimated-fee fills: {s['estimated_fee_fills']})"
        )
    t = card["totals"]
    lines.append(
        f"[SCORECARD] TOTAL: trades={t['trades']} net=${t['net_pnl']:+.2f} "
        f"expectancy=${t['expectancy_net_per_trade']:+.2f}/trade maxDD=${t['max_drawdown']:.2f}"
    )
    return lines


def generate(write: bool = True) -> Dict[str, Any]:
    card = build_scorecard()
    for line in render_lines(card):
        logger.info(line)
    if write:
        path = scorecard_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if atomic_write_json is not None:
            atomic_write_json(str(path), card, indent=2)
        else:  # pragma: no cover
            tmp = path.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(card, fh, indent=2)
            os.replace(tmp, path)
    return card


def maybe_regenerate_weekly() -> bool:
    """Regenerate if the scorecard is missing or older than a week."""
    try:
        path = scorecard_path()
        if path.exists() and (time.time() - path.stat().st_mtime) < WEEKLY_MAX_AGE_S:
            return False
        generate(write=True)
        return True
    except Exception as e:
        logger.warning(f"[SCORECARD] weekly regeneration failed: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratex scorecard from the fill ledger")
    parser.add_argument("--stdout", action="store_true", help="print only, do not write state/scorecard.json")
    args = parser.parse_args()
    card = generate(write=not args.stdout)
    for line in render_lines(card):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
