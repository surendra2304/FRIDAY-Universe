# TASK-FRD-061 — BUILD VERIFY: lead-gen verify-then-outreach step

**Task:** FRIDAY: lead-gen verify-then-outreach step — verify each lead's contact details before the outreach list is final.
**Source:** friday package F-28 (item DPGp5CbDJ-v — the Yello-directory local-business pattern). **Priority:** P3. **Worker:** Muse TP9.
**Claim:** hub #1483 comment 7164861800 (2026-11-25 ~19:47 IST). **Branch:** `musetp9/task-frd-061`.
**Merge-base:** main `3b8c03075464ddfb7fe7478a6d832e4217b7170b`.

## Five states

| State | Value | Evidence |
|---|---|---|
| Implemented | YES | Verification module + engine wiring + tool, all on branch (see below) |
| Tested | PARTIAL | 12 hermetic tests written, collected in FRIDAY tier-1 (REL-068); CI verdict pending on this PR |
| Merged | NO | PR open, awaiting peer merge |
| Deployed | NO | Needs merge + deploy to FRIDAY-Server |
| Production-verified | NO | Done = one real lead list produced with a verification status recorded for every lead |

## Baseline (read first-hand)

- **Lead-gen errand** (`FRIDAY/src/friday/autonomous/lead_generation.py`, TASK-IG2-FRD-03): `Lead` (name/phone/email/website/address/category/source_url), `_ListingParser` (tel:/mailto: + regex extraction), `dedupe_leads`, `render_table` (markdown/CSV), `run_lead_generation` (SSRF-guarded fetch, same-host pagination, MAX_PAGES 5, MAX_LEADS 200). **No verification step existed** — no status field, no check date, no liveness check of any kind.
- **Tool** `lead_generate` (SENSITIVE) in `FRIDAY/src/friday/tools/builtin/lead_gen_tools.py`: runs the errand, returns the table. No outreach surface by design ("The table is the deliverable").
- **Cross-reference EARN-029** (board record): Yello directory + AI contact extraction for Dubai/UAE businesses, 50-lead list with "verified public contact routes" under `earning/`, pitches human-sent by the owner. Rules: public business contact data only; no scraping behind logins; no automated mass outreach.
- **Existing tests** (`FRIDAY/tests/test_ig2_frd03_lead_generation.py`): assert `render_table`'s shape by substring and that the engine has no outreach surface (`send`/`smtp`/`call_` names). Both constraints respected — `render_table` untouched, no outreach names added.

## What was built

- **New module `FRIDAY/src/friday/autonomous/lead_verification.py`** — `verify_lead` / `verify_leads` / `finalize_outreach_list` / `render_verification_table`. Statuses: `verified` (every route on file checks out), `stale` (a route provably fails: website 4xx/5xx, email domain unresolvable, bad format), `unverifiable` (no routes on file, or a check could not run — network/DNS error is "could not tell", never "dead"). Every lead gets `status` + `checked_at` (IST) + `verification_note`.
  - Website: liveness via the errand's fetcher, SSRF-guarded (`check_url_allowed`).
  - Email: format + domain resolution only. A mailbox is never probed.
  - Phone: format plausibility only. Nobody is dialled.
  - No outreach surface anywhere in the module (no send/smtp/call names).
- **Engine wiring** (`lead_generation.py`): `Lead` gains `status` (`"unchecked"` default), `checked_at`, `verification_note` — defaults keep every existing construction and test unchanged. `run_lead_generation(..., verify: bool = False, dns_resolver=None)` runs the pass over deduped leads when asked; off by default so existing callers see exactly the old behaviour.
- **Tool** (`lead_gen_tools.py`): `lead_generate` now runs verification by default (`verify=True`, `drop_stale=True` params to change it). Final outreach list = verified + unverifiable (flagged); stale leads are dropped and named in the report, never silently lost. `verify=False` behaves exactly as before.
- **Tests `FRIDAY/tests/test_ig_frd_061_lead_verification.py`** — 12 hermetic tests (all three statuses, could-not-tell vs dead, finalize counts/drop/keep, verified table markdown + CSV, engine opt-in + default-off, tool verified + tool verify-off). Collected in FRIDAY tier-1 (REL-068).

## What is NOT done (Done blockers)

Done = **one real lead list produced with a verification status recorded for every lead**. That needs: (1) this PR merged, (2) deploy to FRIDAY-Server, (3) one real directory errand run on production (e.g. a Yello category page) with the verification pass on, producing a list where every lead carries its status + check date. No deploy has happened; nothing here claims otherwise.

## Verification notes

- Code diagnosed by READING only (execution-risk restriction on the local clone: no git/package commands, no running repo code). PR CI is the test runner.
- The roster validator will fail on this PR until roster PR #1843 merges (board owner `muse_tp9` not yet a registered collaborator) — expected sequencing, same as PRs #1848/#1849/#1850/#1852.
- No outreach was added anywhere: this task is verify-then-outreach, and the "outreach" half stays the owner's human action (per EARN-029's rules and the errand's own hard boundary).
