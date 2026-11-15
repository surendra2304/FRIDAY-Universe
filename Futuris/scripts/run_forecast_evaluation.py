#!/usr/bin/env python3
"""Run the TASK-FUT-004 walk-forward forecast evaluation harness.

Drives the five production candidate adapters (registry ``current_active()``)
plus the harness reference baselines over the provenanced series in
``Futuris/evaluation_data/`` and writes the scorecard (JSON + Markdown).

Usage (from the Futuris/ directory):

    python3 scripts/run_forecast_evaluation.py [--data-dir PATH] [--out-dir PATH]

Defaults: data from ``Futuris/evaluation_data/``, scorecard written to
``Futuris/docs/forecast_evaluation/`` (``baseline_scorecard.json`` +
``BASELINE_SCORECARD.md``). The run is honest by construction: models that
cannot forecast in the current environment are reported NOT SCORABLE with
the refusal evidence — no number is ever substituted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from futuris.evaluation.reference_models import reference_forecasters
from futuris.evaluation.walkforward import (
    build_scorecard,
    environment_info,
    load_series,
    production_forecasters,
    render_scorecard_markdown,
    run_walk_forward,
)


def main() -> int:
    futuris_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=str(futuris_root / "evaluation_data"))
    parser.add_argument(
        "--out-dir", default=str(futuris_root / "docs" / "forecast_evaluation")
    )
    args = parser.parse_args()

    series_list = load_series(args.data_dir)
    env = environment_info()
    print(
        f"statsforecast available: {env['statsforecast_available']}"
        + ("" if env["statsforecast_available"] else f" ({env['statsforecast_import_error']})")
    )

    results = []
    for series in series_list:
        forecasters = production_forecasters(series.season_length) + reference_forecasters(
            series.season_length
        )
        for forecaster in forecasters:
            result = run_walk_forward(series, forecaster)
            results.append(result)
            m = result.metrics or {}
            print(
                f"{series.series_id:28s} {result.model:18s} {result.kind:10s} "
                f"{result.status:12s} origins {result.origins_scored}/{result.origins_attempted}"
                + (
                    f"  MAE={m.get('mae')} MASE={m.get('mase')} "
                    f"coverage90={m.get('coverage_90')}"
                    if m
                    else ""
                )
            )

    scorecard = build_scorecard(series_list, results, env)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "baseline_scorecard.json").write_text(json.dumps(scorecard, indent=2) + "\n")
    (out_dir / "BASELINE_SCORECARD.md").write_text(render_scorecard_markdown(scorecard))
    print(f"\nwrote {out_dir / 'baseline_scorecard.json'}")
    print(f"wrote {out_dir / 'BASELINE_SCORECARD.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
