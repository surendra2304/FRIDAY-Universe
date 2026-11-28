# TASK-STR-113 follow-up — US-only GDP filter: implementation evidence

- **Filed:** 2026-11-28 ~11:50 IST, by Muse 13. **Status:** implemented + tested + live re-probed; merge owed.
- **Assignment:** Burn Enforcer 11:15 §C (hub #2045 comment 7234754534) — STR-113 follow-up implementation (head), released by Muse 7 (hub 7234591410) after its checkout failed an execution-risk check. No go-ahead to process that flagged checkout; this leg used a fresh clone only.
- **Claim:** hub #2045 comment 7234813100. Branch `muse13/task-str-113-followup` @ main `300ab00c`.
- **Input:** M4's classification + scope decision, `docs/collaboration/TASK-STR-113-EVIDENCE.md` (PR #2275, IN_REVIEW): GDP high only for US releases; semantic exclusion for debt-to-GDP / %-of-GDP / current-account shapes; expected live re-probe narrowed-high 32 → 16.

## Change

`Stratex/research/economic_calendar.py` — `classify_macro_impact(name, country="")`:
- GDP keywords (`gross domestic product`, `gdp`) return HIGH only when the country is US/blank (`"", us, usa, united states`) AND the name is not a non-release shape (`debt-to-gdp`, `debt to gdp`, `% of gdp`, `current account`).
- A non-US GDP row, or a Class C shape, falls through to the remaining keyword table without the GDP keywords — so it can still be HIGH for another reason (e.g. CPI) but never on GDP alone.
- Blank country keeps the historical default (treated as US), so existing one-argument callers are unchanged.
- `parse_economic_events` now passes the row's `country` into the classifier (it already stored it, but never used it for impact).

`Stratex/tests/test_ig2_str11_economic_calendar.py` — two new tests:
- `test_classify_macro_impact_gdp_us_only`: all 16 M4-classified non-US rows demote (not high); Atlanta Fed GDPNow stays high; plain US GDP stays high; blank country stays high; Class C shapes stay low even with a US country; a non-US GDP row is still high for another keyword.
- `test_parse_economic_events_gdp_country_wiring`: French GDP → low, Atlanta Fed GDPNow → high, Current Account % of GDP → low, through the parser.

`.github/workflows/friday-universe-ci.yml` — `tests/test_ig2_str11_economic_calendar.py` added to the Stratex tier-1 invocation (REL-068 collection-guard precedent, STR-107 pattern: a PR test must run in PR CI).

## Tests — local, first-hand

Scratch venv `/tmp/str113-venv` (pytest 9.2.0), `Stratex/`:
- Baseline before the change: 7 passed.
- After the change: **9 passed** (`tests/test_ig2_str11_economic_calendar.py -q`).

## Live re-probe — Stratex-Server (S4), first-hand, 2026-11-28 ~06:00Z

- **Module under test:** branch file fetched to `/tmp/str113m13/economic_calendar.py`, sha256 `bf8a6b49…c40b7` — identical to the branch commit. The live module (`/opt/friday_universe/Stratex/research/economic_calendar.py`, sha256 `ab1da786…b310`, identical to main) was NOT edited; no restart, no env flip.
- **What ran:** fresh Nasdaq refresh via the new module into `/tmp/str113m13/calendar.jsonl` (window 2026-11-28 → 12-05), then M3's NARROW rule applied in-probe. Same event set as M3/M4: **479 events (330 macro / 149 earnings), `last_refresh_ok` true.**
- **Control (old module simulated by name on the same set):** broad high 65, narrowed high **32**, demoted 38, promoted 5 (Chicago PMI; S&P Global Manufacturing PMI; ISM Non-Manufacturing PMI; S&P Global Composite PMI; S&P Global Services PMI) — M3/M4's numbers reproduced exactly, which validates the probe method.
- **New module:** broad high **49** (65 − 16), narrowed high **16** (32 − 16). The 16 demoted are exactly M4's 16 rows (all 16 found in the store, 0 high now — listed below); Atlanta Fed GDPNow (`2026-12-02`, United States) stays high.
- **Narrowed-high 16 (new):** French Non-Farm Payrolls (11-28); Chicago PMI (12-01); Atlanta Fed GDPNow, FOMC Member Bowman Speaks, ISM Manufacturing Employment, ISM Manufacturing New Orders Index, ISM Manufacturing PMI, ISM Manufacturing Prices, S&P Global Manufacturing PMI (12-02); ADP Nonfarm Employment Change (12-03); ISM Non-Manufacturing PMI, Interest Rate Decision (India), S&P Global Composite PMI, S&P Global Services PMI (12-04); Nonfarm Payrolls, Private Nonfarm Payrolls (12-05).
- **Advisory check (M4 §Scope-4 prediction):** on 2026-12-01 the narrowed set is Chicago PMI only — the 6 non-US GDP rows no longer fire the 72h advisory. Confirmed.
- **Daemon untouched (before/after):** PID 74531 running throughout; `Stratex/state/fill_ledger.jsonl` sha256 `5e657087099259764596059b989d66191cad0fc23d90795abdde0f5bcb910a21`, 84 lines, identical. Probe dir `/tmp/str113m13` deleted after the run.
- **First probe attempt:** an earlier in-probe script applied NARROW only to broad-high rows and reported narrowed 11/11 — a probe bug (the PMI promotion clause never fires on broad-high-only input, and the old-control dicts carried new impacts). The corrected script (NARROW over all rows, impact passed explicitly) reproduces 32/16 exactly. The wrong 11/11 numbers are superseded; nothing was filed from them.

## Carried observations (not this task's scope)

- The narrowed-16 still contains `French Non-Farm Payrolls` and `Interest Rate Decision` (India): M3's NARROW clauses for NFP and central-bank decisions carry no country qualifier. The GDP filter does not touch them; any country-scoping there is a coordinator call for a later task.
- The live S4 module is still the old code (sha `ab1da786…`); the filter reaches production only via merge + the normal deploy path.

## Five states

- implemented YES (branch `muse13/task-str-113-followup` @ `1fa7b9f7`, + evidence/workflow commit)
- tested YES (9/9 local; CI on the PR head owed)
- merged NO
- deployed NO (live module untouched; deploy rides the normal path after merge)
- production-verified NO (live re-probe of the deployed module owed post-deploy)

## What remains

- Paired verification of this work PR (verifier: a different chat).
- Merge by the coordinator; deploy via the normal path; live re-probe of the deployed module owed after deploy.

— Muse 13
