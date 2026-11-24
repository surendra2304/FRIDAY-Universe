# TASK-INT-040 — S2 → S1 envelope shipper (repair the IntelX watch outbox transfer path)

**Task:** TASK-INT-040 — repair the S2→S1 envelope transfer path.
**Worker:** Muse 5. **Branch:** `muse5/task-int-040-envelope-shipper`, from main `ce5c1bd4`.
**Claim:** hub issue #1483 comment 7131961005, 2026-11-24 ~18:20 IST (coordinator watch 7130910007,
nudged 7131396444, 7131647996). Board has no TASK-INT-040 record yet — the record rides in
tomorrow's consolidated board PR; no board file in this PR.
**Scope:** repo-side only. No live move, no production server touch, no service restart.

## The finding (as reproduced from evidence)

Muse 1's TASK-INT-036 (fast-lane live proof, run 1) found the break; Muse 7's TASK-INT-038 run 2
re-verified it first-hand (recon 06:29 IST + re-probe 08:34 IST, 2026-11-24) and filed it in
`docs/collaboration/TASK-INT-038-FAST-LANE-PROOF-RUN-2.md`:

- **Producer (Server 2):** IntelX runs there and appends fired alert envelopes to its local
  outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl` (instant-class also to the
  sibling `instant_outbox.jsonl`). At the 08:34 IST re-probe the S2 outbox held 2 lines, last
  modified 2026-11-23 22:03 IST: (1) harness adapters, score 4, fired 2026-11-20 18:26 UTC;
  (2) **RBI "Stop Switch" payments-fraud proposal, score 5, fired 2026-11-23 16:33 UTC
  (22:03 IST)**. Both digest-class, both below the instant bar (6).
- **Consumer (Server 1):** FRIDAY's drainer (`FRIDAY/src/friday/proactive/intelx_watch.py`)
  tails S1-local sibling paths only (`INTELX_WATCH_OUTBOX_PATH` or the sibling IntelX
  checkout default). At the re-probe the S1 outbox held 4 lines, 3,644 bytes, last modified
  **2026-11-20 19:16 IST** — unchanged for ~4 days; drainer state `offset: 3644` (whole S1
  outbox consumed), `delivered_keys`: the 4 digest envelopes, each exactly once.
- **Consequence, verified live:** the RBI digest envelope fired on S2 on 2026-11-23 22:03 IST
  never reached S1 — absent from the S1 outbox and from the drainer's `delivered_keys` /
  `alert_log`. A digest alert fired and was never delivered. The same break applies to any
  future instant alert. **No shipper exists: no S2→S1 sync was found** (no IntelX process,
  timers, or watch cron on S1; S1 and S2 poll independently with separate seen-stores).
- The loss was silent: nothing on either server recorded that an envelope produced on S2
  never arrived on S1.

Code-level confirmation (read first-hand on branch `muse5/task-int-040-envelope-shipper`):

- Producer: `IntelX/intelx/watches/engine.py` — `Outbox.append` (line ~728) appends one JSON
  envelope per line; `build_envelope` (~734) stamps schema `intelx.watch_alert/1`,
  `envelope_id` (sha256 of `watch.id:fingerprint`), `dedupe_key`, `watch_id`, `alert_class`
  (`digest` | `instant`), `fired_at`, `score`. `default_outbox_path` (~850) honours
  `INTELX_WATCH_OUTBOX_PATH`; instant-class envelopes are ALSO appended to the sibling
  `instant_outbox.jsonl`.
- Consumer: `FRIDAY/src/friday/proactive/intelx_watch.py` — `_read_new_envelopes` (~264)
  tails by persisted byte offset, complete lines only, dedupes on `dedupe_key` across both
  lanes, tolerates a shrunk file by restarting at 0.
- The mesh transport (`mesh/transport.py`, `mesh/envelope.py`) is agent-to-agent HTTP/NATS
  for `AgentEnvelope`s — it does not move these watch-envelope JSONL files, and there is no
  endpoint that accepts outbox lines. FRIDAY's peer-URL tables (fixed by TASK-FRD-033) prove
  S1↔S2 HTTP reachability (`10.0.0.121` ↔ `10.0.0.120`), but reachability is not a shipper.

## Design — the minimal shipper

New module `IntelX/intelx/watches/outbox_shipper.py` (standard library only, imports nothing
from IntelX, so it can run as a standalone timer job on S2). No change to the producer, no
change to the S1 drainer, no new endpoint, no new credential.

- **Tail, don't copy.** The shipper tails the S2 outbox files by byte offset (same model as
  the drainer: complete newline-terminated lines only; a trailing partial line waits for the
  next run; a file that shrank below the offset restarts at 0). A whole-file copy would be
  wrong: S1's 4 lines and S2's 2 lines are disjoint sets from independent polling, so
  overwriting S1's outbox would destroy its delivered record. The shipper ships only NEW
  lines and APPENDS them to S1's outbox, preserving S1's existing lines byte-identical.
- **Transports (pluggable).** `LocalAppendTransport` appends to a destination directory on
  the same filesystem (tests + staged proof). `SshAppendTransport` is the live mechanism:
  `ssh <host> "cat >> <dest>"` with lines piped on stdin — the only command executed on S1,
  over the inter-server SSH path deploys already use; no new credential beyond that key.
  Built from `INTELX_OUTBOX_SHIPPER_DEST_HOST` / `INTELX_OUTBOX_SHIPPER_DEST_DIR`.
- **Failure visibility (the actual defect was silence).** Every hop is recorded: one JSON
  line per envelope (`shipped` / `skipped_duplicate` / `malformed` / `ship_failed`) plus a
  per-run summary, in `shipper.log.jsonl`. State (`shipper_state.json`) holds per-lane byte
  offsets and the shipped `envelope_id` set, so a restart never reships. A failed ship
  raises `ShipperError`, leaves the offset unadvanced, and is recorded in the result, the
  log, and the run summary — the next run retries the same envelope. `audit(dest_dir)`
  compares source vs destination `envelope_id` sets and reports MISSING explicitly
  (exit 1) — the exact condition that hid the 2026-11-23 RBI envelope.
- **CLI.** `python -m intelx.watches.outbox_shipper ship` (env: `INTELX_WATCH_OUTBOX_PATH`,
  `INTELX_OUTBOX_SHIPPER_DEST_HOST`/`_DEST_DIR`, `INTELX_OUTBOX_SHIPPER_STATE_PATH`,
  `INTELX_OUTBOX_SHIPPER_LOG_PATH`) and `... audit <dest_dir>`.

## Tests — 14/14 passing, stdlib only

`IntelX/tests/test_int040_outbox_shipper.py` (unittest.TestCase, also collected by pytest).
Run locally 2026-11-24 ~18:40 IST with plain `python3 -m unittest discover -s tests`
(no pytest installed on this host; no network, no servers):

- validation: valid digest/instant pass; missing field, wrong schema, unknown class rejected.
- tailing: partial tail held until newline-terminated; missing file is empty, not an error;
  shrunk file restarts at 0.
- shipping: digest + instant lanes shipped byte-identical; second run ships 0 (idempotent);
  malformed lines counted without wedging the tail; source-replaced reship deduped, not duplicated.
- failure visibility: failing transport → run `ok: false`, error recorded, offset not
  advanced, retry ships the same envelope; `audit` finds both S2 envelopes missing from the
  staged S1 outbox, then goes clean after shipping, with S1's original 4 lines preserved
  byte-identical at the head (6 lines total).
- SSH transport: command is `ssh <host> "cat >> <dest>"` only — no other remote command;
  missing host/dir rejected.

## Staged proof — produce → ship → receive (local simulation, no live servers)

Run 2026-11-24 ~18:40 IST with the real defect's facts as fixtures: staged S2 outbox with
the 2 envelopes INT-038 observed (harness adapters + RBI "Stop Switch", fired 2026-11-23
16:33 UTC); staged S1 outbox with 4 older disjoint lines:

1. `audit` BEFORE: `{"missing": [46569f15… (harness), 526d726d… (RBI)], "per_lane":
   {"outbox.jsonl": {"source": 2, "destination": 4, "missing": 2}}}` — exit 1. The RBI
   envelope is detected as missing, exactly the condition that was silent on 2026-11-23.
2. `ship`: `{"ok": true, "shipped": 2, "errors": []}` — exit 0.
3. `audit` AFTER: `{"missing": [], "per_lane": {"outbox.jsonl": {"source": 2,
   "destination": 6, "missing": 0}}}` — exit 0. S1 holds 6 lines; the RBI envelope is line 6.
4. Hop log records `shipped` for both envelope_ids, a `run_summary` (`ok: true`, shipped 2),
   and both audits.

## CI on the work PR

- First head `01a5e175`: the `contracts` job failed — not on the code, on the TASK-REL-068
  collection guard (`scripts/ci_test_collection_audit.py`, first step of the contracts job):
  `FAIL: 1 test file(s) shipped in this PR are collected by NO PR-triggered workflow. ...
  UNCOLLECTED: IntelX/tests/test_int040_outbox_shipper.py` (job log read first-hand).
  Fix (commit `cddd3534`): the new test file is now collected by the IntelX
  health-capability contracts step in `.github/workflows/owner-workflows.yml`, alongside
  the other IntelX contract tests — one line, no other workflow change.
- Final head `cddd3534`: **CI 10/10 green first-hand** (8 success, 2 skipped, 0 failed):
  `contracts` success, `test` success, fleet-layout / monorepo-policy / roster / secrets /
  entrypoints success, docker + voice-regressions skipped. The new tests therefore also
  pass in CI under the real IntelX conftest, not only standalone.

## What this task does NOT do (owed after the freeze lifts)

- **Live end-to-end verification is OWED, not claimed.** Owner stop order ~16:42 IST
  2026-11-24 froze all server moves; the partial lift 17:26 IST covers key architecture +
  bridge + Inference only. The live leg — install the shipper as a timer on S2 (SSH transport
  to S1), fire or await a real envelope, observe it land in S1's outbox, and watch the
  drainer deliver it (`delivered_keys`) — waits for the freeze lift and coordinator
  clearance. Nothing here touches a production server, a live dispatch, or a service.
- Timer/service install is a deploy-time step, not in this PR (no systemd unit is
  committed; the unit + install clearance belong to the live leg).
- The S1 outbox's 4 pre-move lines stay as they are; the shipper only ever appends.

## Files

- `IntelX/intelx/watches/outbox_shipper.py` (new, ~490 lines, stdlib only)
- `IntelX/tests/test_int040_outbox_shipper.py` (new, ~290 lines, 14 tests)
- `.github/workflows/owner-workflows.yml` (1 line: collect the new tests in the IntelX
  contracts step — REL-068 guard fix, commit `cddd3534`)
- This evidence doc: `docs/collaboration/TASK-INT-040-ENVELOPE-SHIPPER.md`

## States

- Implemented: YES (shipper + tests, repo-side only)
- Tested: YES (14/14 unit tests + staged produce → ship → receive simulation; live
  end-to-end NOT tested — owed after the freeze lifts)
- Merged: NO (work PR awaiting Muse — never merge; only Muse merges)
- Deployed: NO (timer install on S2 is the owed live leg)
- Production-verified: NO (live envelope S2 → S1 → drainer delivery not yet observed)
