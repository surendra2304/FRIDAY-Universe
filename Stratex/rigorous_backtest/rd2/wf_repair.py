"""Repair wf-select entries lost when a grid run died mid-flight.

The grid writes wf-select summaries at the end of a run from the
trades of cells evaluated IN THAT RUN; a killed run loses the
procedures for families it completed. This script recomputes the
missing (family, panel, tf) procedures from the configs directly
(same eval path as grid.py) and merges them into grid_wf_select.json.
Existing entries are never overwritten. The recomputed procedures
count as trials exactly like the originals.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from ..rd.common import dump_json, wf_select_judge
from .families2 import build_configs
from .families3 import build_configs3
from .grid import AUX_TF, CANON, eval_pairs, eval_single, eval_xs
from .panels import PANEL_TFS, load_panel


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()
    out_dir = Path(args.out_dir)
    rows_dir = out_dir / "grid_rows"
    present: dict[tuple, set] = defaultdict(set)
    for p in rows_dir.glob("*.json"):
        r = json.loads(p.read_text())
        present[(r["family"], r["panel"], r["timeframe"])].add(r["variant"])
    sel_path = out_dir / "grid_wf_select.json"
    summary = json.loads(sel_path.read_text()) if sel_path.exists() else {}

    cfg_index = {(c["family"], c["variant"]): c
                 for c in build_configs() + build_configs3()}
    panel_cache: dict[tuple[str, str], dict] = {}

    def get_panel(panel, tf):
        if (panel, tf) not in panel_cache:
            panel_cache[(panel, tf)] = load_panel(panel, tf)
        return panel_cache[(panel, tf)]

    fixed = 0
    for (fam, panel, tf), variants in sorted(present.items()):
        if len(variants) < 2:
            continue
        key = f"{fam}__{panel}__{tf}"
        if key in summary:
            continue
        datasets = get_panel(panel, tf)
        if not datasets:
            continue
        vt: dict[str, list] = {}
        for var in sorted(variants):
            cfg = cfg_index[(fam, var)]
            if cfg["kind"] == "single":
                aux = None
                if fam == "mtf_confluence" and tf in AUX_TF:
                    aux = get_panel(panel, AUX_TF[tf])
                vt[var] = eval_single(cfg, panel, tf, datasets, aux)
            elif cfg["kind"] == "xs":
                vt[var] = eval_xs(cfg, panel, tf, datasets)
            else:
                vt[var] = eval_pairs(cfg, tf, datasets)
        sel = wf_select_judge(vt)
        summary[key] = {"family": fam, "panel": panel, "timeframe": tf,
                        "variants_tried": len(vt), "wf_selection": sel,
                        "repaired": True}
        fixed += 1
        po = sel["procedure_pooled_oos"]
        print(f"[wf-repair] {key}: trades={po['trades']} "
              f"exp={po['expectancy_net']} pf={po['profit_factor_net']}",
              flush=True)
        dump_json(sel_path, summary)
    print(f"[wf-repair] done: {fixed} procedures repaired", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
