# TASK-SEN-032 — PRODUCTION-VERIFY IG2-SEN-02..06 (Sentinel, wave 3)

**Task:** PRODUCTION-VERIFY: Sentinel corpus items IG2-SEN-02, IG2-SEN-03,
IG2-SEN-04, IG2-SEN-05, IG2-SEN-06 — live approval-path verification (wave 3)
**Owner:** Muse 4 · **Branch:**
`muse4/task-sen-032-prod-verify-ig2-sen-02-06` (from main `a0a9f1ba`)
**Claim:** hub #1483 comment 7156776916, 2026-11-25 ~13:46 IST, on coordinator
assignment WATCH084 (7155464602, ~12:34 IST) + queue WATCH085 (7155781501):
SEN-032 → SEN-026 → SEN-027.
**Work PR:** (filed after this doc; board flip AVAILABLE → IN_REVIEW rides in it)

## Five states

- **implemented:** YES (repo leg) — live-probe driver
  `Sentinel/scripts/sen032_live_probes.py`, unit tests
  `tests/test_sen032_live_probes.py`, this evidence doc, CI wiring,
  board flip.
- **tested:** YES — 55 passed locally (17 new SEN-032 driver tests + the 38
  existing IG2-SEN module tests across the five modules), 0 failed; driver
  dry-run end-to-end from this VM exits 0 with full JSON output.
- **merged:** NO — work PR open, awaiting Muse's review/merge. I do not merge.
- **deployed:** NO — the driver is not deployed; it runs on demand on S1.
- **production-verified:** NO — the live leg is scoped, scripted and ready
  but NOT run: it executes code on the live S1 host and probes the live
  fleet, and the owner stop order is in force. Clearance requested below.

## Correction — the 13:24 run missed this assignment

My free-request comment 7156454409 (~13:25 IST) said no assignment existed.
That was wrong: WATCH084 had already assigned SEN-032 to Muse 4 at ~12:34
IST and WATCH085 had confirmed the queue. The 13:24 run failed to read
those two posts. The free request is withdrawn by the claim post
7156776916. TASK-STR-077 was NOT pulled: the Muse 17 claim conflict
stands unresolved (claim of record 7138103574; watch083 ruling: STR-077
stays Muse 17's).

## Pre-flight (read-only, verified first-hand 2026-11-25 ~13:48–13:51 IST)

- Both Oracle servers ONLINE (`get_system_info` via bridge).
- Sentinel `/health` 200: `status ok`, `kill_switch_active false`,
  `audit_chain_valid true`, `audit_chain_entries 34`, `audit_durable true`.
- Sentinel `/ready` 200: `READY`, `database connected` (oracle),
  `telegram_channel true`, `modules_active 13`.
- Live Sentinel: Oracle Server 1 (10.0.0.121), port 8008,
  `Sentinel.service` **active**, MainPID 3747427.
- S1 deployed HEAD `b51ef05f2b0290eecc4fab553e19e35c60e2110a`
  (2026-11-24 19:01 IST). Working tree has local modifications in
  Futuris (2 files) and a deleted VyralX test + untracked `.backups/` —
  none touches Sentinel.
- Deployed code is byte-identical to this repo at main `a0a9f1ba` (md5):

  | file | md5 |
  |---|---|
  | `app/services/fleet_audit_pipeline.py` | a39f57c962d76af3c3875fd0c94b8fbb |
  | `app/services/audit_baseline.py` | 8d4f9f204911e3895f9b173a6844c3f3 |
  | `app/services/media_ela.py` | de2a9fdb3b5126f53a24ede54168b87b |
  | `app/services/compromised_host_triage.py` | f382e7d3514c8ba470486526458a1a30 |
  | `app/services/extortion_mail_triage.py` | a9848cf469e36b96b9e608564b61b6a6 |
  | `sentinel/gatekeeper/approval_policy.py` | 87ca1ed136d83a53f17dec27828fc4ba |
  | `sentinel/gatekeeper/approval_dispatcher.py` | 92468726310f17dd6a1f12aadf6a5a83 |

  The two approval files match SEN-025's record exactly — the approval
  path code is unchanged since the last live proof run.
- Pillow 12.3.0 present in the S1 shared venv (`/opt/friday_universe/venv`)
  — the ELA check can run live.
- Real JPEGs exist on S1 for the ELA check (VyralX render thumbnails,
  e.g. `/opt/friday_universe/VyralX/renders/viral-u9SqE131JVY-2445bf-thumb.jpg`).
- S1 host facts: up 42 days, load 0.23 / 0.12 / 0.10, 31 running services —
  no slowness/fan/battery indicators observable on a headless server.

## Per-item scoping (repo read, this run)

All five items are MERGED library code with no production wiring: no
production code imports any of them (only their unit tests do), no HTTP
endpoint exposes them, and the only production caller of
`submit_approval` is the approvals endpoint in
`Sentinel/sentinel/apps/api/main.py`. **None of the five items touches
the approval path.** Per the acceptance's own branching rule, no
per-item approval-path legs are owed (no low-risk auto-approve and no
high-risk Telegram prompt per item); the approval path itself was
already proved live three times (SEN-023/024/025). The live check for
each item is therefore its own security check run against the real
surface, with a failure case each.

| Item | Module | Live check (driver) | Real input on S1 |
|---|---|---|---|
| IG2-SEN-02 | `app/services/fleet_audit_pipeline.py` — `FleetAuditPipeline.run()` | Full pipeline (researcher → planner → executor → reflector → report) over the corrected inventory + S2 unexpected-ports check | Live fleet hosts/services from S1; connect-only TCP, TLS-handshake, HTTP GET probes |
| IG2-SEN-03 | `app/services/audit_baseline.py` — `BaselineMemorist` | Accept SEN-02 findings as baseline (`/tmp` scratch only), re-record the same run (expect all-unchanged, zero alerts) | The live SEN-02 report |
| IG2-SEN-04 | `app/services/media_ela.py` — `analyse_image()` | ELA over a real VyralX render thumbnail on S1 | A real JPEG under `/opt/friday_universe/VyralX/renders/` |
| IG2-SEN-05 | `app/services/compromised_host_triage.py` — `evaluate()` | Triage on the indicators actually observed on S1 (host facts above: none observed → NO_SIGNS) | S1 host state as observed |
| IG2-SEN-06 | `app/services/extortion_mail_triage.py` — `triage_email()` | Triage of the corpus scenario text + benign-mail negative case | Corpus source text (see Limits) |

Failure cases (all in the driver, all verified in the dry run):
- SEN-02: `assert_in_scope("8.8.8.8")` → `OutOfScopeError` (raised ✓).
- SEN-03: same finding id with severity raised LOW → HIGH → one
  `regression` alert (fired ✓ in dry run).
- SEN-04: non-image bytes → `ElaInputError` (raised ✓); PNG input →
  `INCONCLUSIVE` by design (✓).
- SEN-05: unknown indicator id → `UnknownIndicatorError` (raised ✓);
  `["files_encrypted"]` → `LIKELY_COMPROMISED` with containment-first
  plan (✓).
- SEN-06: benign newsletter → `NOT_EXTORTION` (✓); tracking-pixel-only
  newsletter → `NOT_EXTORTION` with `tracking_pixel true` — a pixel
  alone never makes a verdict (✓).

## Finding — the pipeline's default inventory is stale (not a live failure)

`default_fleet_inventory()` still lists the pre-re-layout placement
(FRIDAY 10000, Inference 8001, Stratex 8003, Futuris 8004, IntelX 8005
on server-1; Sentinel/Cortex/VyralX on server-2). Owner order 7138538710
moved those services to their own servers on 2026-11-24. Running the
pipeline on the shipped default would emit false HIGH "port unreachable"
findings for services that simply moved. The driver therefore uses a
corrected inventory (S1: Memora 8002, Forge 8006, Sentinel 8008,
Cortex 8009) and does not present default-inventory output as findings.
**Candidate fix task (not yet filed on the board):** refresh
`default_fleet_inventory()` to the 2026-11-24 re-layout, and record the
private addresses of FRIDAY-Server / Stratex-Server / VyralX-Server /
IntelX-Server so the pipeline can audit them too. Filed here for the
coordinator to file/assign; it is a repo finding, not a live failure of
any of the five items.

## Live-leg plan + clearance request

On clearance, on S1, with the shared venv (no deploy, no restart):

```
/opt/friday_universe/venv/bin/python \
  /opt/friday_universe/Sentinel/scripts/sen032_live_probes.py \
  --image /opt/friday_universe/VyralX/renders/viral-u9SqE131JVY-2445bf-thumb.jpg
```

- SEN-05 runs with `--observe` empty: no indicator was observed on S1
  (host facts above); any indicator genuinely observed at run time is
  passed explicitly and recorded.
- The driver writes nothing outside `/tmp` (baseline scratch, deleted
  at exit), submits no approval, sends no Telegram message, and writes
  nothing to the audit ledger. Its stdout JSON is the live evidence and
  will be filed in this doc + the work PR.
- **Clearance asked of Muse on the hub:** approve the live probe run
  above (read-only fleet probing + pure-function checks on S1). The
  run is net-zero production change by construction; the only live
  effect is TCP/TLS/HTTP probe traffic to the fleet's own endpoints.
  If the coordinator reads the acceptance as still owing an
  approval-path pair for this wave, say so and I will scope the two
  legs (one low-risk auto-approve + one high-risk Telegram prompt,
  each exactly once) as a separate, explicitly cleared step — I am not
  running them unasked, because no item touches the approval path and
  a Telegram prompt messages the owner directly.

## Limits (honest)

- SEN-06 input is the corpus scenario text reconstructed from the
  module docstring (the $30,000 ransom demand, IG cluster #80,
  shortcode DU3rtSlk9mi), not a mail from the owner's live inbox — no
  inbox was read for this task. A real owner-supplied mail would
  strengthen it; the driver takes the text as input, so a supplied
  mail can be triaged the same way.
- SEN-05's real input is the absence of observed indicators on S1 plus
  the host facts above; the module evaluates observations, it does not
  gather them, so "none observed" is the honest live result.
- SEN-02's corrected inventory covers only the two Oracle hosts whose
  addresses are in the repo (10.0.0.121 / 10.0.0.120). The four new
  single-purpose servers have no recorded private addresses, so they
  are out of scope until the inventory fix lands.
- The local dry run from this VM (which cannot reach 10.0.0.121)
  produced 8 HIGH "port unreachable" findings — an artifact of running
  off-fleet, not evidence about the fleet. Live results come only from
  the S1 run.

## Tests (local, 2026-11-25 ~14:00 IST)

Venv `~/workspace/muse4-runs/sen032-venv` (pytest 9.2.0, Pillow 13.0.0,
pydantic, pydantic-settings, sqlalchemy for the Sentinel conftest):

```
pytest tests/test_sen032_live_probes.py \
  tests/test_ig2_sen_fleet_audit_pipeline.py \
  tests/test_ig2_sen_audit_baseline.py \
  Sentinel/tests/test_ig2_sen_ela.py \
  Sentinel/tests/test_ig2_sen_compromised_host_triage.py \
  Sentinel/tests/test_ig2_sen_extortion_mail_triage.py
55 passed, 0 failed
```

Note: the three `Sentinel/tests/` files initially errored at conftest
setup (missing `pydantic`, then `sqlalchemy` in the venv) — an
environment gap, not a module failure; installing the two packages
cleared it and all 55 pass. The new test is added to the owner-workflows
contracts list so the REL-068 collection guard collects it.
