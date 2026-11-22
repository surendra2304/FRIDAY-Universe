# TASK-OBS-008 — Health alerting re-probe (re-verify TASK-OBS-001)

**Task:** re-verify TASK-OBS-001 (crash-loop and health alerting, merged 2026-11-10):
confirm the watcher timer is enabled on the fleet, and prove one alert is
delivered end-to-end — or file the exact gap.
**Owner:** muse_7. **Branch:** `muse7/task-obs-008-health-alerting-reprobe`.
**Assignment:** coordinator watch, issue #35 comment 7074080436 (~09:46 IST 2026-11-22).
**Claim:** issue #35 comment 7074463887 (~10:27 IST), answering coordinator nudge
7074327949 (~10:13 IST). Claim PR #1316 merged 2026-11-22T05:15:05Z
(merge `12c4a70c`, ~10:45 IST).
**Work:** this document + board flip CLAIMED → IN_REVIEW. Work PR: see board record.

## Verdict

- **Watcher timer enablement: CONFIRMED on both servers** — enabled + active,
  firing every 5 minutes, state files fresh (§1).
- **One alert delivered end-to-end: PROVEN through the watcher dispatch path,
  once** — a real `SERVICE_DOWN` condition raised by the watcher on Server 1
  was forwarded by its `--alert-command` into `notify_owner()` and returned
  `NotifyResult.SENT`, exactly once (§2).
- **Two precise production gaps filed** — in production today no watcher alert
  is delivered anywhere, for two independent reasons (§3, §4). The drill proves
  the code path works when both are addressed; it does not claim production
  delivery works today.
- **No alert storm:** cooldown dedup observed live; the drill sent exactly one
  message (§5).

## 1. Timer enablement — both servers (bridge, ~11:28–11:30 IST 2026-11-22)

Server 1 (10.0.0.121) and Server 2 (10.0.0.120) both ONLINE
(`get_system_info`, bridge v1.30.0).

| Check | Server 1 | Server 2 |
| --- | --- | --- |
| `systemctl is-enabled fleet-health-watcher.timer` | `enabled` | `enabled` |
| `systemctl is-active fleet-health-watcher.timer` | `active` | `active` |
| Last trigger | 11:23:37 IST | 11:25:39 IST |
| Next trigger | 11:28:37 IST | 11:30:39 IST |
| `--status` | `fresh`, last cycle 2026-11-22T05:53:58Z, age 266s | `fresh`, last cycle 2026-11-22T05:55:40Z, age 222s |

Timer unit is the repo unit (`deploy/fleet-health-watcher.timer`: 5-minute
`OnUnitActiveSec`, `Persistent=true`). The on-disk watcher script on Server 1
hashes `226e5dc8d872d62d38acec72f962292b457c2957` — byte-identical to the main
blob; the gate `FRIDAY/src/friday/proactive/owner_notify.py` hashes
`a330a3654a6f7e790ccbb454ba2b266db671fa20` — byte-identical to main.

Open alerts at probe time (state files, cooldown-suppressed — see §5):
Server 1: `IntelX:HEALTH_UNREACHABLE`, `IntelX:SERVICE_DOWN`,
`Futuris:SERVICE_DOWN`. Server 2: `VyralX:SERVICE_DOWN`,
`VyralX-Daemon:SERVICE_DOWN`, `Sentinel:SERVICE_DOWN`. These are the sleeping
copies on the opposite host (see §6).

## 2. The drill — one alert end-to-end (Server 1, 2026-11-22 11:33:41 IST)

Drill path verified before sending (same gate as TASK-FRD-032):
`FRIDAY/src/friday/proactive/owner_notify.py` — `notify_owner(text,
severity=Severity.ALERT, event_key=...)`, kill switch `FRIDAY_OWNER_NOTIFY`
unset (grepped unit, drop-in, both `.env` files; live probe
`_kill_switch_active()` = False), gateway configured (live probe
`TelegramGateway.is_configured()` = True). Gate state before: day
`2026-11-22`, `day_count` 5/20, `last_sent_at` 1795315082.3128679 (~08:08 IST —
global 120s floor clear), fresh event key `drill:obs-008`.

Trigger: the watcher itself, run once manually with a synthetic down service
and a drill alert command — the real dispatch path, not a direct notify call:

```text
scripts/fleet_health_watcher.py --once \
  --services "DrillProbe:59999" \
  --state /tmp/muse7-obs008-state2.json \
  --alert-command "/opt/friday_universe/venv/bin/python /tmp/obs008_drill.py"
```

The alert command called `notify_owner()` with the watcher's
`$FLEET_ALERT_TEXT`, drill-marked, event key `drill:obs-008`. A separate
`/tmp` state file was used so the production state file was untouched.

- **Watcher output:** `[CRITICAL] SERVICE_DOWN DrillProbe: ActiveState=inactive
  SubState=dead; error=URLError: <urlopen error [Errno 111] Connection refused>`
  then `[CYCLE 2026-11-22 11:33:48 IST] 0/1 healthy; unhealthy: DrillProbe`.
- **Result:** `DRILL-NOTIFY: NotifyResult.SENT` at 11:33:41 IST
  (epoch 1795327425.712922).
- **Exactly-once evidence (server side):** gate state
  `FRIDAY/.data/owner_notify/state.json` after the drill: `day_count` 5 → 6,
  exactly one new key `drill:obs-008` = 1795327425.712922, exactly one new text
  hash, `last_sent_at` = 1795327425.712922. One `notify_owner` call produced
  one `SENT`, one state increment, one `sendMessage`. No second drill was run.
- **Text sent (verbatim, after the escaping noted in §4):**
  `[DRILL - TASK-OBS-008] Watcher alert-path drill: [CRITICAL] SERVICE_DOWN
  DrillProbe: ActiveState=inactive SubState=dead; error=URLError: &lt;urlopen
  error [Errno 111] Connection refused&gt; Planned drill, not a real incident
  - please ignore. Event key drill:obs-008.`

## 3. Gap 1 (production, filed precisely): no alert command is wired

`FLEET_ALERT_COMMAND` is **unset on both servers**:

- Server 1: `systemctl show fleet-health-watcher.service -p Environment` →
  `Environment=` (empty). No drop-in directory exists.
- Server 2: `Environment=FLEET_WATCH_SERVICES=Sentinel:8008,Cortex:8009,
  VyralX:8010,VyralX-Daemon:-` — fleet map only, no alert command.
- The installed unit carries only the commented-out example
  (`deploy/fleet-health-watcher.service`:
  `# Environment=FLEET_ALERT_COMMAND=curl -s -X POST .../notify -d
  "$FLEET_ALERT_TEXT"`).

Code path: `scripts/fleet_health_watcher.py:331` — `if alert_command:` guards
the forward in `dispatch_alerts` (lines 311–338). With no command set, a NEW
alert is only printed to the journal (`print(line, ...)`) and recorded in the
state file; **nothing leaves the server**. The 11:13:40 IST `[CRITICAL]
SERVICE_DOWN Futuris` on Server 1 today is journal-only evidence of this: it
was raised, logged, and delivered nowhere.

Fix needs a Muse decision (which notify endpoint/command to wire); not
implemented in this re-verification task.

## 4. Gap 2 (delivery path, proven by a failed first attempt): unescaped `<...>` breaks the Telegram send

First drill attempt (11:31:56 IST) returned `NotifyResult.FAILED` and recorded
nothing (gate state unchanged: `day_count` stayed 5, no `drill:obs-008` key).
Cause: the watcher's alert text contains the raw probe error
`error=URLError: <urlopen error [Errno 111] Connection refused>`, and the
gateway sends with `parse_mode=HTML` without escaping
(`FRIDAY/src/friday/proactive/telegram_gateway.py`, `send_message` →
`_api("sendMessage", {..., "parse_mode": "HTML"})`; a non-`ok` response
returns `None` → `False` → `FAILED`). Telegram rejects the malformed tag.
The second attempt, identical except for HTML-escaping the alert text in the
drill script, returned `SENT` — confirming the diagnosis.

Any real `SERVICE_DOWN`/`HEALTH_UNREACHABLE` alert whose probe error contains
`<...>` would fail the same way even after Gap 1 is fixed. The fix belongs in
the gateway (`send_message` should escape) or in the watcher dispatch — a Muse
decision, not implemented here.

## 5. No alert storm

- Cooldown dedup observed live in the Server 1 journal today: repeated
  `[SUPPRESSED] IntelX:SERVICE_DOWN within 1800s cooldown` and
  `[SUPPRESSED] Futuris:SERVICE_DOWN within 1800s cooldown` lines across the
  11:03–11:23 IST cycles; the 1800s `--cooldown` default is honoured.
- Drill discipline: attempt 1 `FAILED` (nothing recorded, nothing sent);
  attempt 2 `SENT` exactly once with the fresh key `drill:obs-008`. Two
  watcher runs, one Telegram message total. Drill state files lived in `/tmp`
  (`muse7-obs008-state.json`, `muse7-obs008-state2.json`); the production
  state files were not touched. Drill script `/tmp/obs008_drill.py` removed
  after the run.

## 6. Secondary observations (not in the acceptance criteria)

- **Fleet-map overlap:** each host's watcher flags the other host's services
  down every cycle — Server 1 watches IntelX/Futuris (run on Server 2),
  Server 2 watches VyralX/VyralX-Daemon/Sentinel (sleeping copies there).
  Cooldown suppresses re-alerts, so this is noise, not a storm — but each
  watcher's map should cover only its own host's services. Follow-up, not
  fixed here.
- Server 2 checkout is on stale branch `muse7/task-str-fwd-035-daemon-timeframe-label`
  (`c6c129ea`); read-only note, not touched.
- `tedTorus` posted an unsolicited architecture suggestion on issue #35
  (comment 7074604230, ~10:41 IST, Git-based atomic locks) — not addressed to
  Muse 7, no action taken.

## 7. Limitations, stated plainly

- Telegram-side receipt is not visible to me: `send_message` returns bool
  only — no Telegram `message_id` is captured server-side. The exactly-once
  claim is server-side (one `SENT`, one gate-state increment), same limitation
  as TASK-FRD-032.
- The FRIDAY service journal showed no `[TG-GATEWAY]` lines around the drill
  window (failed sends log at debug level); the SENT/FAILED contrast above is
  the evidence for Gap 2.

## Next

- Muse review/merge of this work PR.
- Muse decisions: (a) wire `FLEET_ALERT_COMMAND` on both servers (which
  endpoint/command); (b) HTML-escape alert text in the gateway or the watcher.
  Until both land, watcher alerts stay journal-only.
