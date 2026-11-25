# TASK-FUT-031 — PRODUCTION-VERIFY IG-FUT-01/02 + REPO-IMPLEMENT (OpenBB, Polymarket py-sdk, Fincept Terminal, Scientific Agent Skills)

- **Task:** TASK-FUT-031 (P2, Futuris lane)
- **Owner:** Muse 4
- **Claim:** hub #1483 comment 7154355763, 2026-11-25 ~11:31 IST, on coordinator watch080 assignment (7154044918)
- **Branch:** `muse4/task-fut-031-prod-verify-ig-fut-01-02`
- **Base main:** `f6b912a6` (claim post cited `8fa84c61`; main moved before the branch was created — coordinator merges #1772, #1755, #1777, #1774 landed in between; branch verified at `f6b912a6` via the branch API)
- **Work PR:** (stamped in the board record after opening)
- **Date:** 2026-11-25

## Five states

- implemented: YES (repo leg — see below)
- tested: YES — 103 passed locally (see §4); CI on the work PR to confirm
- merged: NO — work PR open, awaiting Muse
- deployed: NO
- production-verified: NO — both corpus items' live legs are HELD (owner stop order in force, no lift in watches 077/078/079/080), and the OpenBB ARM-day leg needs hardware that does not exist yet. Nothing live is claimed here.

## 1. Production-verify — repo-side mapping (live legs HELD)

Per the VYR-074 / STR-075 checkpoint-1 precedent, this PR ships the repo-side
mapping of both corpus items to their merged artefacts on current main. The
live extreme-condition legs stay held and are named, not claimed.

### IG-FUT-01 — OpenBB-style market-data backbone (board: MERGED, PR #496 + follow-up #778)

Artefacts verified present on main `f6b912a6` (all files from the board record):

| Artefact | Present |
|---|---|
| `Futuris/futuris/market_data/` (`base.py`, `models.py`, `service.py`, `providers/`) | yes |
| `Futuris/futuris/market_data/providers/openbb_sdk.py` | yes |
| `Futuris/futuris/market_data/providers/stooq.py`, `yahoo.py` | yes |
| `Futuris/futuris/api/routers/market_data.py` (`GET /v1/market-data/providers`) | yes |
| `Futuris/futuris/infra/config.py` (`FUTURIS_OPENBB_PROVIDER`, line 178) | yes |
| `Futuris/docs/DATA_BACKBONE_IGFUT01.md` | yes |
| `Futuris/pyproject.toml` optional extra `futuris[openbb]` (`openbb>=5.0,<6.0`, `openbb-yfinance`) | yes, optional-only |

Adapt intact, verified first-hand: `sdk_available()` probes with
`importlib.util.find_spec` and never imports the SDK; `openbb` is imported
only inside `fetch_ohlcv` (lazy by design); with the SDK absent a fetch
returns `unavailable` naming that fact, never fabricated bars; the provider
is an env flip, not a hard dependency. The guardrail test (§4) pins this.

Tests (re-run first-hand this run, mock `DATABASE_URL`, `PYTHONPATH=Futuris`,
Python 3.12 venv): `tests/market_data/test_backbone.py` 12, `test_providers.py`
20, `test_api.py` 3 — **35 passed**.

**Live leg HELD — IG-FUT-01 ARM day.** The board `next_action` requires the
second tenancy's A1: re-measure the SDK on the production interpreter,
install the `openbb` extra and pin the resolved set, flip
`FUTURIS_OPENBB_PROVIDER` with `openbb_sdk` ordered last for week 1, verify
via `GET /v1/market-data/providers` then a forced SDK-only fetch with
provider/evidence labels, pass the FUT-004/FUT-006 scorecard gate before any
forecast consumes SDK data. None of that can run now: no ARM host, SDK install
and provider flip need coordinator clearance, and the owner stop order is in
force. The measured blocker stands (210.9 s import, 995.6 MB peak RSS vs
956 MB host RAM and the 180 MB service cap).

### IG-FUT-02 — geopolitical/event context in outlooks (board: DEPLOYED, PR #508)

Artefacts verified present on main `f6b912a6`:

| Artefact | Present |
|---|---|
| `Futuris/futuris/features/event_context.py` | yes |
| `Futuris/futuris/api/routers/market.py` (`build_event_context`, `EventContextPayload`, wired at line ~357) | yes |
| `Futuris/tests/features/test_event_context.py` | yes |
| `Futuris/tests/api/test_market_event_context.py` | yes |

Tests (re-run first-hand this run, same env): `test_event_context.py` 8,
`test_market_event_context.py` 4 — **12 passed**.

Coexistence with FUT-030 verified: `market.py` wires both `build_event_context`
and FUT-030's `build_calendar_context` into the same outlook payload
(`event_context` + `calendar_context` fields); the full 103-test contracts set
(§4) passes with both live.

**Live leg HELD — IG-FUT-02 forecast probe.** The board `next_action`
requires probing a market forecast with IntelX context on the deployed
Futuris and confirming the event_context block renders. That needs the
deployed Futuris service plus fleet CD plus hub clearance, all gated by the
owner stop order. Not attempted, not claimed.

**Collection gap closed.** The five IG-FUT-01/02 test files above were shipped
by PRs #496/#508/#778 but named in NO PR-triggered workflow — the REL-001
defect class. This PR adds all five to the Futuris contracts step (§4), so
they run in CI for the first time. They pass locally under the step's own
environment (mock `DATABASE_URL`, `PYTHONPATH=Futuris`).

## 2. Repo-implement — OpenBB (adapt)

The adapt is the IG-FUT-01 work itself (§1): adapter-over-data-model,
delivered by PRs #496/#778, verified intact on current main above. No new
adapter code was needed in this task; what this task adds is the verification
that the adapt is still intact and still bounded, plus the guardrail test
pinning it.

Upstream repo verified first-hand 2026-11-25 (public GitHub API + LICENSE file):

- `OpenBB-finance/OpenBB` → 302-redirects to repo id 323048702 (openbq-org
  stewardship, as the registry card states); 75,714 stars; last push
  2026-11-18; not archived.
- LICENSE file on main, first lines: "Copyright (c) 2021-2026 OpenBB Inc. /
  All files in this repository are licensed under the Apache License,
  Version 2.0." — the registry's Apache-2.0 (v5+) claim is confirmed from
  the file itself (the API's license field reads NOASSERTION; the file is
  authoritative).

## 3. Repo-implement — reference-only verdicts, with live evidence per repo

Acceptance: "a paper judgement is NOT a result — prove with live evidence
whether it works in the agent or not (live trial or guardrail proof of
absence from every production path), and file that evidence per repo."
The proof for all three is the guardrail test (§4) plus, for Polymarket, a
live read-only trial. Scope is the Futuris production path
(`Futuris/futuris/` + `Futuris/app/`), the target agent for all four repos.

### Polymarket py-sdk (`Polymarket/py-sdk`, MIT) — reference-only

- Registry verdict: the usable part is the free, unauthenticated read-only
  Gamma/Data APIs as a forecasting signal, readable with plain HTTP; no SDK
  adoption needed today; integrate nothing. Trading through the CLOB is out
  of scope (real-money venue, no demo mode, geo-restricted).
- Upstream verified first-hand 2026-11-25 (public GitHub API): MIT, Python,
  155 stars, last push 2026-11-24, not archived.
- **Live trial** — `Futuris/scripts/fut031_polymarket_gamma_trial.py`
  (stdlib-only, GETs only, no keys, no POST, no wallet/order path), run
  first-hand this run, exit 0, verbatim output:
  - 5 markets returned from `gamma-api.polymarket.com/markets?limit=5&active=true`.
  - "Xi Jinping out before 2027?" — Yes 0.0175 / No 0.9825, prob sum 1.0000.
  - "Will Gavin Newsom win the 2028 Democratic presidential nomination?" — Yes 0.0975 / No 0.9025, sum 1.0000.
  - "Will Alexandria Ocasio-Cortez win the 2028 Democratic presidential nomination?" — Yes 0.1805 / No 0.8195, sum 1.0000.
  - "Will Pete Buttigieg win the 2028 Democratic presidential nomination?" — Yes 0.0555 / No 0.9445, sum 1.0000.
  - "Will Josh Shapiro win the 2028 Democratic presidential nomination?" — Yes 0.0540 / No 0.9460, sum 1.0000.
  - Verdict: signal readable YES (5/5 markets parsed); integrated into Futuris: NO.
  - Failure case 1: malformed record `{"id": "x"}` parses to None — skipped, never repaired.
  - Failure case 2: simulated feed disconnect raises `RemoteDisconnected` — surfaces; no order path exists (read-only by construction).
- Note: the "Xi Jinping" market matches the TASK-STR-072 live Gamma trial
  (Yes 0.0165 then, 0.0175 now) — same live venue, consistent data.
- Guardrail: zero references to `polymarket` / `gamma-api.polymarket.com`
  in any Futuris production module (verified by grep and pinned by the
  guardrail test); no Polymarket package in any Futuris dependency file.

### Fincept Terminal (`Fincept-Corporation/FinceptTerminal`, AGPL-3.0) — reference-only

- Registry verdict: Qt6 desktop GUI cannot run on the headless ~956 MB
  fleet VMs; best features sit behind the paid Enterprise edition (breaks
  the FREE-only rule); AGPL-3.0 copyleft bars embedding its code into
  FRIDAY services. Keep as UI/module-layout reference only.
- Upstream verified first-hand 2026-11-25 (public GitHub API): AGPL-3.0,
  C++, 34,190 stars, last push 2026-11-19, not archived — confirms the two
  structural facts the verdict rests on (C++ desktop, AGPL-3.0).
- Guardrail: zero references to `fincept` in any Futuris production module
  or dependency file (verified by grep and pinned by the guardrail test).
- Honest scope note: Stratex-side `Stratex/app/agents/real_fincept_terminal.py`
  exists and is imported by `Stratex/api/real_trading_routes.py` — that is
  pre-existing Stratex-lane code, not a Futuris path and not this task's
  scope; it is not claimed as absent repo-wide.

### Scientific Agent Skills (`K-Dense-AI/scientific-agent-skills`, MIT) — reference-only

- Registry verdict: FRIDAY has no genomics, chemistry or clinical workload,
  so the bulk of the library has no fleet consumer. What transfers is the
  packaging discipline (versioned SKILL.md, references loaded on demand,
  skill-spec validation in CI) and a handful of research-methodology /
  data-analysis / literature-synthesis skills Futuris could cherry-pick.
  Do not install the full set.
- Upstream verified first-hand 2026-11-25 (public GitHub API): MIT, Python,
  58,396 stars, last push 2026-11-23, not archived.
- Guardrail: zero references to `scientific_agent_skills` in any Futuris
  production module or dependency file (verified by grep and pinned by the
  guardrail test).
- The transferable packaging discipline is noted, not implemented: no
  Futuris skill-spec validation exists yet, and inventing one is out of
  this task's scope.

## 4. Guardrail test + CI wiring

New: `Futuris/tests/test_fut031_reference_only_guardrail.py` (5 tests):

1. No Futuris production module imports `polymarket`, `polymarket_client`,
   `py_clob_client`, `fincept`, or `scientific_agent_skills` (AST walk of
   `Futuris/futuris/` + `Futuris/app/`).
2. No Futuris production module references `gamma-api.polymarket.com`.
3. No reference-only repo (and no `openbb`) in `requirements.txt`,
   `requirements.lock`, or `pyproject.toml` main dependencies; the `openbb`
   optional extra still exists.
4. `sdk_available()` is False here and probing never imports `openbb`.
5. With the SDK absent, `fetch_ohlcv` returns `unavailable` naming it,
   with zero bars — never fabricated data.

Re-run first-hand this run: **5 passed**.

CI wiring (`.github/workflows/owner-workflows.yml`, Futuris contracts step):
the guardrail test plus the five IG-FUT-01/02 test files are now collected
(6 additions, trailing-backslash pattern per the FUT-030 fix). Full step set
re-run first-hand this run (mock `DATABASE_URL`, `PYTHONPATH=Futuris`):
**103 passed in 79.80s** (47 IG-FUT-01/02 + 5 guardrail + 51 pre-existing
contracts files). REL-068 collection guard run locally against base
`f6b912a6` after staging: PASS.

## 5. Board flips in this PR

- TASK-FUT-030: IN_REVIEW → MERGED (PR #1776 merged by Muse 2026-11-25
  11:09:18 IST, merge `e5035288`, CI 11/11 green; owed per watch080).
- TASK-FUT-031: AVAILABLE → IN_REVIEW (owner muse_4, branch
  `muse4/task-fut-031-prod-verify-ig-fut-01-02`, pr stamped after opening).

## 6. Held / flagged

- **Live legs HELD** (both corpus items + OpenBB ARM day): owner stop order
  still in force; no live-fleet step attempted. Production-verified stays NO.
- **Paired-verification gap:** no verifier named for this task in watch080;
  flagging, as with STR-081 and FUT-030.
- **TASK-STR-074 (watch080 pos-3) NOT claimed:** already held by Muse TP4
  (hub claim of record 7140407159, branch
  `musetp4/task-str-074-production-verify-wave1` live at `1c3481a9`,
  checkpoint 1 filed). Flagged in the claim post; awaiting Muse's
  replacement pos-3.
- **Work-request job:** cancelled on claim (body step 2); hourly self-check
  stays armed. This run fired only because the 10:24 run's cancellation had
  not taken effect (job was still enabled at 11:24:39 IST); the removal is
  verified this run.
- Usage 51% (carried from watch080; not re-verified this run).

— Muse 4
