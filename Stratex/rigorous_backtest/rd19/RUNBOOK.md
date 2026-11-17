# RUNBOOK — TASK-STR-RD-019 declared run (family xs_reversal_volclimax_1d)

The ONE declared backtest run for the volume-climax-conditioned
cross-sectional reversal family. **Do not run until every gate below
passes.** A declared run is executed exactly once; the runner refuses
to re-run into an output directory that already holds RESULTS.md.

Frozen declaration: `xsrev_declaration.json`
SHA-256 `a2d5f212308fdd097e968c801c175b9513da3ff24c49456590eec70d324d917b`
(amended 2026-11-17 by the PR #897 F1/F2 fix: TEMPORAL HOLDOUT v1
overlay added to the evaluation bar by coordinator ruling, before
any run; original freeze hash
`ffc3c573071ee8014d99d125cbc08551b39f47fb756696e603124b81e86f31f1`).
(workspace copies: `~/workspace/str-xsrev/xsrev_declaration.json` +
`XSREV_DECLARATION.md`; the differentiation paragraph is byte-identical
in both — paragraph SHA-256
`3adfb213394f783f4490674ed29c94c59d75be6e1a648cc724aba695773c1af3`).

## Gate A — declaration on main, hash matching

The declaring PR (a separate step, not part of the prep task) must
have merged the declaration to origin/main at:

```
Stratex/rigorous_backtest/rd19/xsrev_declaration.json
Stratex/rigorous_backtest/rd19/XSREV_DECLARATION.md
```

Verify from a FRESH checkout of origin/main (never the shared local
clone's working tree):

```
sha256sum Stratex/rigorous_backtest/rd19/xsrev_declaration.json
# must print a2d5f212308fdd097e968c801c175b9513da3ff24c49456590eec70d324d917b
```

The runner re-verifies this hash itself and aborts on any mismatch.

## Gate B — queue ahead concluded

The programme runs ONE declared run at a time — the coordinator
fires runs one at a time, in queue order. Ahead of this family in
the declared queue: **SRS** (TASK-IG2-STR-14, School Run Strategy),
then **S-RD1** (TASK-IG2-STR-19, EMA 5/11), then **RD-018**
(TASK-STR-RD-018, FX Asia-range fade). All three must have concluded
(verdict recorded) before this run starts. This family's Bonferroni
floor already charges for the SRS + S-RD1 cells ahead of it, and the
run-time ledger read picks up the RD-018 cell if it has run (see the
run command).

## Gate C — harness pinned and tests green

The harness in `~/workspace/str-xsrev/harness/` must hash to:

```
xsrev.py      48280584f5469c82b862d27b5a359b7b655e678775c469270a7a40b6a3940c9e
run_xsrev.py  e9d593672be9eb7353fb2a8a22bb866e3a994e115e30ede01b884be973611c59
test_xsrev.py ac19a8813f9852bb88042687d532fb604354d2b222d5374109b3dc3d280e1535
test_xsrev_judge_smoke.py 1de8280982e525fe6cbc911f004cb73100f78d789ebf1e30868799858d55fa1a
```

(run_xsrev.py was rewritten by the PR #897 F1 fix against the real
programme APIs; test_xsrev_judge_smoke.py is the F1 judge-path smoke
suite. xsrev.py and test_xsrev.py are byte-identical to the original
freeze.)

And the synthetic tests must pass against those exact files:

```
cd ~/workspace/str-xsrev/harness
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q test_xsrev.py test_xsrev_judge_smoke.py
# expected: 32 passed (20 signal-harness + 12 judge-path smoke;
# the smoke suite needs the full checkout layout — run it from the
# rd19 directory of the fresh origin/main checkout)
```

Any hash drift means the code no longer matches what was declared
and reviewed — stop, do not run, escalate to the coordinator.

## Panel

Default: the S-RD1 run-prep verified panel
(`~/workspace/srd1-runprep/panel/`, provenance
`~/workspace/srd1-runprep/panel_provenance.json`, SHA-256
`1eeea5cdad831cc0338c41f4cb7aaf684cf9d80fecbd6fa19f645652bb464517`).
The runner verifies every symbol against that provenance (108,192
rows, 0 missing, csv_sha256) and aborts on any mismatch, then asserts
the declared aggregation yields exactly 1,127 daily bars per symbol.

Fallback (only if the local panel is gone): regenerate with the
programme's own loader from Binance Vision (free) into the same
layout, regenerate the provenance manifest, and cross-check all 30
csv_sha256 against `Stratex/rigorous_backtest/ig/box_theory_provenance.json`
on origin/main before running. Any mismatch → stop.

## The run (exactly one)

Compute the trial floor FIRST from the global trial ledger at run
time: `N_global = max(ledger entering N, 3893) + 1` (minimum 3894;
α ≤ 0.05/N_global ≤ 1.2840e-05). Then, from a fresh origin/main
checkout:

```
cd ~/workspace/str-xsrev/harness
python3 run_xsrev.py \
  --repo <fresh origin/main checkout> \
  --trial-floor <N_global computed above> \
  --declared-run \
  --out ~/workspace/str-xsrev/run-output
```

(--panel-dir and --expected-provenance default to the S-RD1 run-prep
paths above; pass them explicitly if the panel lives elsewhere.
`--declared-run` is the TEMPORAL HOLDOUT v1 H5 attestation: the
operator attests the panel was verified first and the holdout was
never previously computed or inspected — the runner refuses to
judge without it. The runner also refuses any --trial-floor below
the declared minimum 3894, before loading anything.)

## Verdict rules (from the frozen declaration — no discretion)

- Pooled OOS trades at programme costs < 200 → the verdict is
  exactly **"insufficient OOS trades"** (neither proven nor
  disproven). This is a live structural possibility — ~212 signal
  bars total, gated subset — and was declared up front.
- PASS requires ALL of: check_bar (expectancy > 0, PF ≥ 1.2,
  ≥ 200 OOS trades, ≥ 4/5 positive folds) AND holdout_check AND
  the TEMPORAL HOLDOUT v1 overlay (H = W5 entries: |H| ≥ 20,
  expectancy_net(H) > 0, expectancy_net(D = W1–W4 entries) > 0,
  no fold > 80% of total positive fold profit; H5 burn clause —
  judged exactly once, in this run) AND Bonferroni p < α, at
  programme costs (16 bps) AND at the 2× shadow (32 bps). PASS
  means forward-test CANDIDATE only — the Phase-3 bar (≥100
  forward trades, ≥8 weeks on demo, FWD-006 sizing) still applies
  before anything trades.
- Anything else → FAIL; the family closes (strict OOS PF < 1.2
  components delete the family per the programme rule).

## Recording (after the run)

1. RESULTS.md + results.json + trades JSONs land in --out.
2. Board: TASK-STR-RD-019 updated with the verdict + evidence via
   the coordinator's board PR.
3. Issue #35: ONE completion comment with the verdict and the real
   numbers (check-before-post; body_json as a JSON string; read
   back exactly one copy).
4. The results files are proposed alongside the declaration at
   `Stratex/rigorous_backtest/rd19/` via PR. No merge without the
   coordinator's review. DEMO only; nothing here authorises live
   trading.
