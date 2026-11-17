# RUNBOOK — TASK-STR-DISC-004 declared run (ORB/VWAP equity intraday)

The declared run executes **exactly once**, in lane order, under the
SRS TEMPORAL HOLDOUT v1 §2.3 procedure. Every gate below must pass
in order; any failure stops the sequence and is reported, never
worked around.

## Gates before any command runs

1. **Declaration merged with its hash intact** —
   `orb_vwap_declaration.json` SHA-256 must equal
   `43063a6cdf8089d7d41bd39e4b02c1c05bf5528c3837590c167f87d2907dafc9`
   (the runner re-verifies this itself; a changed declaration is a
   new declaration).
2. **Lane order** — the SRS declared run AND the S-RD1 declared run
   have concluded ahead of this family.
3. **Credentials installed** — the Alpaca key pair is installed
   (SRS execution step 1) and visible to the run environment as
   `ALPACA_API_KEY_ID` / `ALPACA_API_SECRET_KEY`. Never copy key
   values into any file, command line, or log.
4. **OPEN ITEM — adjudicate BEFORE the pull (affects SRS
   identically).** The shared `nyse_calendar.py` precedent sets
   `EARLY_CLOSE_BARS = 10` (last early-close bar-start 11:45 ET),
   and the declared panel totals (24,842 bars/symbol) follow it.
   The same file's docstring, however, describes early-close
   bar-starts as "09:30..12:45 ET" — which is 14 bars — and a
   13:00 ET close spans 210 minutes = 14 fifteen-minute bars
   (panel total would be 24,878). If the real SIP panel serves 14
   bars on the 9 early-close sessions, the pull filter as inherited
   keeps only the first 10 and check 1 passes against the truncated
   panel — fail-consistent, but the 12:00–13:00 bars of 9 sessions
   would be silently dropped. The coordinator must adjudicate the
   constant (and, if it changes, issue matching declaration errata
   for SRS and this family) **before either family's panel is
   pulled**. This prep deliberately did not diverge from the SRS
   adjudication unilaterally; the discrepancy is recorded here and
   in the prep STATE.md.

## Command sequence (run from the harness directory)

```bash
cd <repo-or-scratch>/str-orb/harness        # wherever the package lives
PANEL=/var/tmp/orb_panel                    # OUTSIDE any git tree (SIP licence)
CROSS=/var/tmp/orb_cross                    # Yahoo retrieval files

# 0. Synthetic tests must pass on the run machine, unmodified package:
python3 test_orb_vwap.py                    # expect: 25/25 passed

# 1. Access proof — one symbol-month SIP pull (AAPL, Oct 2026):
python3 pull_orb_panel.py --out /var/tmp/orb_proof --symbols AAPL \
    --start 2026-10-01T00:00:00Z --end 2026-11-01T00:00:00Z
#    Record the draft provenance (bar count, sessions, sha) in the
#    run record. Exit 2 = keys still not installed -> STOP.

# 2. Full panel pull (all 15 symbols, declared span):
python3 pull_orb_panel.py --out "$PANEL"
#    Expect per symbol: 24,842 bars kept / 961 sessions
#    (subject to gate 4's adjudication).

# 3. Retrieve the cross-source files (Yahoo Finance chart API v8,
#    interval=1d, keyless — addendum v3 instrument), one per symbol,
#    saved as $CROSS/<SYM>_yahoo_daily.json, covering 2024-07-01 ->
#    2026-11-01. Hash-pin them immediately:
sha256sum "$CROSS"/*_yahoo_daily.json > "$CROSS/pins.txt"
#    (Assemble pins.json as {symbol: sha256} from pins.txt.)
#    ALSO re-verify the declared split list (NVDA 10:1 ex 2024-06-10,
#    AVGO 10:1 ex 2024-10-14, NFLX 10:1 ex 2025-11-17) against
#    Alpaca corporate-actions data; a mismatch makes the panel
#    INCOMPLETE — stop and report, never edit the list silently.

# 4. Verify — the 5-check gate, per symbol, all must PASS:
python3 verify_orb_panel.py --panel-dir "$PANEL" --cross-dir "$CROSS" \
    --pins "$CROSS/pins.json"
#    Exit 0 + verification_report.json overall PASS + frozen
#    data_provenance.json written. Anything else -> STOP.

# 5. Read the programme trial counter from the ledger NOW
#    (entering N). Expected 3,893 if SRS + S-RD1 ran first; the
#    ledger value governs, whatever it is.

# 6. THE declared run — exactly once:
python3 run_orb_vwap.py --panel-dir "$PANEL" \
    --entering-trials <N-from-step-5> \
    --out <run-record-dir>/orb_vwap_results.json
#    The runner refuses: declaration-hash mismatch (exit 6),
#    pre-existing results (exit 7), unverified panel (exit 8),
#    panel-hash deviation (exit 9).
```

## After the run

- The results JSON carries the verdict, the pooled/per-fold/
  per-symbol metrics, the holdout and breadth legs, the trial
  accounting (final_N, alpha, p), and `trade_list_sha256` — the
  trade list is hash-pinned in the results file itself before any
  metric is quoted anywhere (§2.3 step 2 discipline).
- Report the verdict **exactly as computed** — including
  "insufficient OOS trades" or `FAIL (INSUFFICIENT_HOLDOUT_TRADES)`
  if that is what comes out. Strict OOS PF < 1.2 deletes the family
  (owner's rule); a pass makes it a forward-test **candidate** only
  (Phase-3 protocol: ≥ 100 trades AND ≥ 8 weeks on demo; sizing
  inherits FWD-006). Nothing authorises live trading.
- The raw panel is never committed (SIP licence). Committable run
  record: results JSON, verification report, `data_provenance.json`,
  the proof-pull draft provenance, and this run's board update.
