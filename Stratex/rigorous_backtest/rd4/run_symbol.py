"""RD-004 per-symbol worker (checkpointed execution stage 1).

  python3 -m rigorous_backtest.rd4.run_symbol --tf 15m --symbol BTCUSDT \
      --cache-dir <15m cache> --coverage <coverage.json> \
      --frag-dir results_rd4/frag

Computes ONE symbol at ONE timeframe: the 16 pre-declared configs x
{1x, 2x} costs, writing one plain-CSV fragment per config/cost under
<frag-dir>/<tf>_<signal>_<mode>_<1x|2x>/<symbol>.csv. Short-lived by
design: this VM intermittently EPERM-blocks file writes from
long-running Python processes, so the judged run is executed as
checkpointed stages (worker -> assemble -> wf -> synth), each stage
idempotent and retryable. The mathematics is exactly the monolithic
design: same data_feed datasets, same families_rd4 entries, same
sim_rd4/fastsim engines, same costs.
"""
from __future__ import annotations

import argparse, json, sys
from pathlib import Path

from ..data_feed import load_dataset
from ..rd.common import atr
from ..rd.fastsim import simulate_entries
from ..rd2.costs2 import CRYPTO, double
from ..rd2.families2 import BR24
from .families_rd4 import MODES, SIGNALS, apply_mode, base_entries, \
    regime_rank_by_bar
from .run_rd4 import resample_2h
from .sim_rd4 import simulate_scaled

HEADER = "symbol,entry_time,exit_time,side,net_return,exit_reason\n"


def _write_fragment(path: Path, trades) -> None:
    """One-shot content build + retry-hardened write (see
    run_rd4._retry_write for the EPERM episode rationale)."""
    from .run_rd4 import _retry_write
    lines = [HEADER]
    for t in trades:
        lines.append(f"{t.symbol},{t.entry_time.isoformat()},"
                     f"{t.exit_time.isoformat()},{t.side},"
                     f"{t.net_return!r},{t.exit_reason}\n")
    content = "".join(lines)

    def _w(tmp: Path) -> None:
        tmp.write_text(content, encoding="utf-8")
    _retry_write(path, _w)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tf", required=True, choices=["15m", "2h"])
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--cache-dir", required=True)
    ap.add_argument("--coverage", required=True)
    ap.add_argument("--frag-dir", required=True)
    ap.add_argument("--out-dir", default="")  # for the engine probe file
    args = ap.parse_args()
    coverage = json.loads(Path(args.coverage).read_text())
    sym = args.symbol
    start = coverage[sym]["start_month"]
    ds15 = load_dataset(sym, "15m", start, "2026-10",
                        Path(args.cache_dir))
    ds = ds15 if args.tf == "15m" else resample_2h(ds15)
    a = atr(ds.df, 14).to_numpy()
    rank = regime_rank_by_bar(ds.df)
    costs2x = double(CRYPTO)
    frag_root = Path(args.frag_dir)
    for sig in SIGNALS:
        base = base_entries(ds.df, sig)
        for mode in MODES:
            entries = apply_mode(base, mode, rank)
            t1 = simulate_scaled(ds.df, entries, a, sym, CRYPTO)
            t2 = simulate_scaled(ds.df, entries, a, sym, costs2x)
            stem = f"{args.tf}_{sig}_{mode}"
            _write_fragment(frag_root / f"{stem}_1x" / f"{sym}.csv", t1)
            _write_fragment(frag_root / f"{stem}_2x" / f"{sym}.csv", t2)
            if args.out_dir and sym == "BTCUSDT" and args.tf == "15m" \
                    and sig == "don20" and mode == "base":
                ref = simulate_entries(
                    ds.df, [(i, s) for (i, s, _f) in entries], a, BR24,
                    sym, CRYPTO)
                mine = [(t.entry_time, t.exit_time, t.net_return)
                        for t in t1]
                theirs = [(t.entry_time, t.exit_time, t.net_return)
                          for t in ref]
                ok = mine == theirs
                payload = {"probe": "BTCUSDT 15m don20 base: "
                                    "simulate_scaled (f=1) vs "
                                    "fastsim.simulate_entries BR24",
                           "trades": len(mine), "identical": ok}
                from .run_rd4 import _retry_write
                p = Path(args.out_dir) / "engine_consistency.json"
                _retry_write(p, lambda tmp: tmp.write_text(
                    json.dumps(payload, indent=2), encoding="utf-8"))
                print(f"engine probe: identical={ok} ({len(mine)} trades)",
                      flush=True)
                if not ok:
                    print("ENGINE MISMATCH — aborting", flush=True)
                    return 1
    print(f"{args.tf} {sym}: fragments written", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
