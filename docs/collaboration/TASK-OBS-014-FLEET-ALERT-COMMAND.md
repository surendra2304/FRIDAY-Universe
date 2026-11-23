# TASK-OBS-014 — Wire FLEET_ALERT_COMMAND (OBS-010 gap (a))

**Task:** wire `FLEET_ALERT_COMMAND` on both servers and verify one
controlled alert flows through it end-to-end, filed with timestamps.
**Owner:** Muse 8. **Branch:** `muse8/task-obs-014`.
**Assignment:** coordinator watch 7097385517 (~15:57 IST 2026-11-23) —
VAL-009 HOLD for the shared 401 fix + re-probe, advance to next queued
task. **Claim:** issue #1483 comment 7098519486 (~16:18 IST). Claim PR
#1492 merged 2026-11-23 17:24 IST (merge `8b7e8d74`, CI 9/9 green).

## Verdict (this run — repo slice; live leg pending clearance)

- **Repo slice DONE, work PR open:** the alert-command script
  (`scripts/fleet_alert_notify.py`, §1) + 18 unit tests (§2) are on
  the branch; CI verdict on the work PR is the next check.
- **Live leg NOT done — clearance requested:** the systemd drop-ins
  on Server 1 + Server 2 (§3) and the controlled drill alert (§4)
  need Muse's clearance for the live change (OBS-010 precedent: a
  live-fleet change needs the coordinator's decision on the command +
  hub clearance). Until it lands, production watcher alerts stay
  journal-only — same position as OBS-010 §4.

## 1. The command

The watcher (`scripts/fleet_health_watcher.py:369`) reads
`--alert-command` from `FLEET_ALERT_COMMAND` and invokes it once per
NEW alert with `FLEET_ALERT_TEXT` / `FLEET_ALERT_JSON` in the
environment. The wired command on both servers is:

```text
/opt/friday_universe/venv/bin/python /opt/friday_universe/scripts/fleet_alert_notify.py
```

Absolute paths, no shell metacharacters. The script
(`scripts/fleet_alert_notify.py`, new) forwards the raw alert text to
the owner through the fleet's single gated path,
`friday.proactive.owner_notify.notify_owner` — the @fridayuniverse_bot
credentials, the OBS-010 HTML-escape fix, the kill switch, daily cap,
per-key cooldown and text dedupe all live there. It adds no second
sender and no new credentials: the gateway resolves the token / chat
id from the process environment, then the repo-root `.env`, exactly as
the deployed FRIDAY service does.

Locked rules (tests/test_fleet_alert_notify.py, 18 tests):

- Alert text passes through RAW — the watcher hands raw text to the
  command and the gateway escapes it once (OBS-010 single-escape
  point); the script never escapes, truncates or reformats it.
- Severity is always ALERT. RECOVERED alerts never reach the command
  (the watcher prints and closes them before dispatch), so every
  alert this script sees is a real incident.
- Event key is stable per condition —
  `fleet_alert:<service>:<alert>` from `FLEET_ALERT_JSON` — so the
  gate's per-key cooldown dedupes a flapping service. Missing or
  unparsable JSON falls back to a hash of the text.
- Exit 0 = sent, or deliberately held by the gate (below bar /
  duplicate / cooldown / daily cap / kill switch off); exit 2 = the
  alert did NOT reach the owner (send failed, gateway not
  configured, FRIDAY tree unavailable, no alert text). The watcher
  invokes with `check=False` and journals the printed
  `FLEET-ALERT-NOTIFY` line either way.

**Why this command and not the curl example in the unit file:**
`deploy/fleet-health-watcher.service` comments a curl example, but
no notify HTTP endpoint exists for the watcher to curl, and a curl
would bypass the gate (kill switch, cap, cooldown, dedupe) and the
OBS-010 escape fix. The `notify_owner()` path is the one OBS-010
proved end-to-end (drill `drill:obs-010`, `NotifyResult.SENT`,
exactly once); OBS-014 wires that proven path into production.

**Why a drop-in, not a repo unit edit:** the live servers run the
already-installed unit; changing `deploy/fleet-health-watcher.service`
in the repo would not change them until a re-deploy. The drop-in
(`/etc/systemd/system/fleet-health-watcher.service.d/alert-command.conf`)
is the live wiring and survives repo re-deploys (it lives outside the
checkout). The repo unit file is left unchanged.

## 2. Repo files in the work PR

- `scripts/fleet_alert_notify.py` (new) — the forwarder above.
- `tests/test_fleet_alert_notify.py` (new, 18 tests) — raw
  passthrough incl. the exact OBS-008 failure text
  (`<urlopen error [Errno 111] Connection refused>`), event-key
  stability + text-hash fallback, exit codes for every gate result
  (sent / 5 held / failed / not-configured / raising notify /
  missing tree), FRIDAY/src path insertion. Local: 18/18 pass
  (venv pytest 9.2.0). Collected by the fleet-layout gate
  (`scripts/ci_gate_test_runner.py` runs `pytest -q tests`) — no
  workflow edit owed.
- This document.

## 3. Live leg — drop-ins (NEEDS CLEARANCE, not yet applied)

On each server, as root/ubuntu with sudo:

```text
/etc/systemd/system/fleet-health-watcher.service.d/alert-command.conf:
  [Service]
  Environment=FLEET_ALERT_COMMAND=/opt/friday_universe/venv/bin/python /opt/friday_universe/scripts/fleet_alert_notify.py
```

Then `systemctl daemon-reload`. No service restart is needed (the
watcher is `Type=oneshot`, triggered by the timer; the drop-in
applies on the next trigger). Verify with
`systemctl show fleet-health-watcher.service -p Environment` on both
servers (expect the command present) and a `--status` freshness read
on the next cycle. Pre-change state (OBS-010 §4, re-verify at drill
time): S1 `Environment=` empty, no drop-in dir; S2 fleet map only.

## 4. Live leg — controlled drill (NEEDS CLEARANCE, not yet run)

Same gate as the OBS-010 drill, after the work PR merges and the
script is on both servers (deploy or checkout update):

1. Gate check: `FRIDAY_OWNER_NOTIFY` unset, gateway configured
   (`TelegramGateway.is_configured()` True) on the drill host;
   fresh event key `drill:obs-014`.
2. Trigger: the watcher itself, run once manually with a synthetic
   down service and the WIRED command (no `--alert-command` flag —
   the drop-in supplies it), a separate `/tmp` state file so the
   production state is untouched:
   `scripts/fleet_health_watcher.py --once --services "DrillProbe:59999" --state /tmp/muse8-obs014-state.json`
3. Expect: one `[CRITICAL] SERVICE_DOWN DrillProbe` line, one
   `FLEET-ALERT-NOTIFY ...: sent` line, one `NotifyResult.SENT`,
   exactly one gate-state increment + one new key `drill:obs-014`.
4. File the timestamps, the journal lines and the gate state
   before/after here; remove the `/tmp` state file after the run.
   One drill only — no second run, no alert storm (cooldown holds
   any real repeat).

## 5. Limitations, stated plainly

- Telegram-side receipt is not visible to the script:
  `send_message` returns bool only — no Telegram `message_id` is
  captured server-side. The exactly-once claim is server-side (one
  `SENT`, one gate-state increment), same limitation as OBS-008 /
  OBS-010 / TASK-FRD-032.
- The local tests prove the forwarder logic, not the deployed send.
  The live send is proven only by the §4 drill, which is why the
  acceptance is not met until the drill runs.
- The drill as specified runs on ONE server (the drill host). The
  acceptance ("wired on both servers") is met by the drop-ins on
  both (§3) plus the end-to-end flow on one (§4); a second drill on
  the other host is a repeat of the same code path, not a new proof.
  If Muse wants both hosts drilled, say so in the clearance.
