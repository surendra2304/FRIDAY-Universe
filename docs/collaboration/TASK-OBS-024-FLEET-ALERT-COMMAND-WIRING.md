# TASK-OBS-024 — Wire FLEET_ALERT_COMMAND (Gap 1) — checkpoint 1: repo-side scoping

**Task:** wire `FLEET_ALERT_COMMAND` on both servers and verify one
controlled alert flows through it end-to-end (Gap 1, open since OBS-008).
**Owner:** muse_17. **Branch:** `muse17/obs-024`.
**Assignment:** coordinator watch 7126818611 (2026-11-24 ~15:20 IST, queue
VYR-050 → OBS-023 → VYR-054 → OBS-024, "claim when VYR-054 merges").
**Claim:** hub #1483 comment 7130331323 (2026-11-24 ~17:07 IST).
**Checkpoint 1:** repo-side scoping, filed 2026-11-24 ~18:10 IST (this doc).
**Status:** implemented NO / tested NO / merged NO / deployed NO /
production-verified NO — checkpoint 1 is scoping only. The live leg is
HELD under the owner stop order (see §5); no server move was made or
attempted this run. All live reads below are read-only.

## 1. What Gap 1 is, and where it stands

- OBS-008 (2026-11-22, Muse 7): the watcher raises alerts, but
  `FLEET_ALERT_COMMAND` is unset on both servers, so alerts are
  journal-only — nothing leaves the server.
- OBS-010: proved the dispatch path once with a synthetic drill
  (`notify_owner()` → `NotifyResult.SENT`, exactly once) and fixed the
  HTML-escaping gap (Gap 2, closed in code).
- OBS-014 (Muse 8, claim PR #1492 merged 2026-11-23 17:24 IST, merge
  `8b7e8d74`): built the production forwarder
  (`scripts/fleet_alert_notify.py`) + unit tests. Its live leg
  (systemd drop-ins on S1+S2 + controlled drill) was never applied —
  clearance was requested and never landed.
- OBS-023 (Muse 17, 2026-11-24 11:06 IST): proved the raise path live
  on a REAL fault — Memora stopped on S1, next watcher cycle raised
  `[CRITICAL] SERVICE_DOWN Memora` in the journal + state file within
  ~6s. Delivery stayed journal-only: Gap 1 still open on both servers
  (verified 11:02 IST that day).
- OBS-024 is the close-out: apply the OBS-014 live leg and prove one
  controlled alert flows end-to-end to the owner.

## 2. Repo state — verified first-hand on main `ce5c1bd4` this run

- `scripts/fleet_alert_notify.py` (6,100 bytes): the forwarder, complete.
  Invoked with `FLEET_ALERT_TEXT` / `FLEET_ALERT_JSON` in the environment;
  forwards the raw text via `friday.proactive.owner_notify.notify_owner`
  (the @fridayuniverse_bot credentials, OBS-010 escape fix, kill switch,
  daily cap, per-key cooldown, text dedupe all live in the gateway).
  Adds no second sender and no new credentials: the gateway resolves the
  token / chat id from the process environment, then the repo-root `.env`,
  exactly as the deployed FRIDAY service does. Exit 0 = sent or
  deliberately held by the gate; exit 2 = not delivered. Never raises
  into the watcher; no secret is ever printed.
- `scripts/fleet_health_watcher.py` (413 lines): the dispatch contract.
  `--alert-command` defaults from `FLEET_ALERT_COMMAND` (line 369).
  `dispatch_alerts` (lines 311–338): RECOVERED alerts are printed and
  closed BEFORE dispatch, so they never reach the command; NEW alerts are
  printed as `[SEVERITY] ALERT service: detail`, then the command runs
  via `subprocess.run(alert_command, shell=True, env={FLEET_ALERT_TEXT,
  FLEET_ALERT_JSON}, timeout=30, check=False)`. Failures journal as
  `[ALERT-COMMAND-FAILED]`. Per-alert-key cooldown 1800 s (default).
- `tests/test_fleet_alert_notify.py` (187 lines, 8,405 bytes): present;
  the OBS-014 doc records 18 tests passing locally (raw passthrough incl.
  the exact OBS-008 failure text, event-key stability + text-hash
  fallback, exit codes for every gate result).
- `deploy/fleet-health-watcher.service`: still carries ONLY the
  commented-out curl example for `FLEET_ALERT_COMMAND`. This is
  deliberate, not an omission (OBS-014 §1): no notify HTTP endpoint
  exists to curl, a curl would bypass the gate and the OBS-010 escape
  fix, and a repo unit edit would not change the already-installed live
  units until a re-deploy. The wiring is a systemd drop-in, not a unit
  edit — the repo unit file stays unchanged.
- `docs/collaboration/TASK-OBS-014-FLEET-ALERT-COMMAND.md` (§3–§4) is
  the live plan this task executes; nothing in it is superseded.

## 3. Live pre-state — verified first-hand this run (~18:05 IST, read-only)

- **S1** (`friday-universe-vnic`, checkout HEAD `8034ab1f` — S1 HAS pulled
  since OBS-023, which recorded it at `3db55adf`):
  `systemctl show fleet-health-watcher.service -p Environment` returns
  `Environment=` EMPTY. No drop-in directory exists
  (`/etc/systemd/system/fleet-health-watcher.service.d/` absent).
  Forwarder script present:
  `/opt/friday_universe/scripts/fleet_alert_notify.py`, 6,100 bytes,
  Nov 23 20:00. Timer `fleet-health-watcher.timer` active.
- **S2** (`friday-universe-vnic-2`, checkout HEAD `09603dff`):
  `Environment=FLEET_WATCH_SERVICES=Sentinel:8008,Cortex:8009,VyralX:8010,VyralX-Daemon:-`
  — no `FLEET_ALERT_COMMAND`. Drop-in directory exists with ONLY
  `server2.conf` (the fleet-map override, Nov 10). Forwarder script
  present: 6,100 bytes, Nov 23 21:19. Timer active.
- **Gap 1 is still open on both servers.** The forwarder script is
  present on both checkouts, so the drop-in command will resolve on
  both hosts once applied; no checkout update is needed for the wiring.
- **Correction (honest record):** my first two probe calls this run
  passed `server_num` to the bridge `run_shell` tool. That tool takes
  `server`, not `server_num` (the `server_num` name belongs to other
  bridge tools, e.g. `oracle_memory_by_process`), so both calls silently
  hit the default server 2 and I briefly read S2 twice. Corrected to
  `server: 1` and re-ran: S1 confirmed as above (hostname + HEAD differ,
  Environment empty, no drop-in dir). The S2 readings stand; the S1
  reading is from the corrected call only.

## 4. The live leg — exact steps, HELD until §5 clears

Per OBS-014 §3–§4, on EACH server (S1 + S2), as root/ubuntu with sudo:

```text
/etc/systemd/system/fleet-health-watcher.service.d/alert-command.conf:
  [Service]
  Environment=FLEET_ALERT_COMMAND=/opt/friday_universe/venv/bin/python /opt/friday_universe/scripts/fleet_alert_notify.py
```

Then `systemctl daemon-reload`. No service restart is needed (the watcher
is `Type=oneshot`, triggered by the timer; the drop-in applies on the next
trigger). Verify with `systemctl show fleet-health-watcher.service
-p Environment` on both servers (expect the command present) and a
`--status` freshness read on the next cycle.

Controlled drill (OBS-014 §4, after the work PR merges and the script is
on both servers — it already is, §3 above):

1. Gate check on the drill host: `FRIDAY_OWNER_NOTIFY` unset, gateway
   configured (`TelegramGateway.is_configured()` True); fresh event key
   `drill:obs-024`.
2. Trigger: the watcher itself, run once manually with a synthetic down
   service and the WIRED command (no `--alert-command` flag — the drop-in
   supplies it), a separate `/tmp` state file so production state is
   untouched:
   `scripts/fleet_health_watcher.py --once --services "DrillProbe:59999" --state /tmp/muse17-obs024-state.json`
3. Expect: one `[CRITICAL] SERVICE_DOWN DrillProbe` line, one
   `FLEET-ALERT-NOTIFY ...: sent` line, one `NotifyResult.SENT`, exactly
   one gate-state increment + one new key `drill:obs-024`.
4. File the timestamps, journal lines and gate state before/after here;
   remove the `/tmp` state file after the run. One drill only — no second
   run, no alert storm (cooldown holds any real repeat).

Acceptance for OBS-024 is the drop-ins on both (§3) plus the end-to-end
flow on one host (§4), per OBS-014 §5 — a second drill on the other host
repeats the same code path. A real-fault re-proof after wiring (OBS-023
style: stop a real service, watch the raise + delivery, restore) would be
stronger evidence but needs its own clearance and a fault window; it is
NOT part of this acceptance unless Muse directs it.

## 5. Decisions / clearance owed from Muse

- **Freeze lift or explicit clearance for the live leg.** The owner stop
  order (coordinator 16:37 watch) froze ALL server moves; the 17:26 IST
  partial lift (coordinator 17:17 watch 7130910007) covers ONLY (1) the
  key architecture work, (2) bridge work, (3) the Inference move — and
  that watch rules explicitly: "M17 OBS-024 live leg: HELD." The drop-ins
  + drill are server moves, so they wait for the freeze to lift or for a
  directed clearance naming this task.
- **Drill host choice** (S1 or S2) — OBS-014 says one host suffices.
- **Gate state at drill time:** confirm `FRIDAY_OWNER_NOTIFY` kill-switch
  state + gateway configured on the drill host (OBS-014 §4 step 1).

## 6. Board

No OBS-024 record on main yet. Verified by chain: the 17:00 run read the
board on main `428a0ea5` first-hand (18,864 lines, no OBS-024 record,
VYR-054 still AVAILABLE); the only merge since is #1667 (STR-063), whose
board hunk the coordinator reviewed first-hand as a single new STR-063
record; board blob on main `ce5c1bd4` is `82a51aa8` (coordinator 17:37
watch, verified first-hand there). A direct board read was not possible
this run — the file is 2,491,951 bytes, above the contents-API limit.
Board flips (VYR-054 MERGED, OBS-024 CLAIMED→IN_REVIEW) ride in
tomorrow's consolidated board PR per the watch011-spec one-per-day rule;
no separate board PR from me.

## 7. Next

Wait for the freeze lift / clearance (§5); then apply the drop-ins,
run the drill, file checkpoint 2 with the timestamps + journal lines +
gate state, and open the work PR (this doc + board flip).
