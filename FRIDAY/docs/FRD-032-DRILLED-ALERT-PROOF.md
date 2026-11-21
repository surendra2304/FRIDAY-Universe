# TASK-FRD-032 — FRIDAY drilled-ALERT proof post-#1071

**Task:** verify one drilled alert reaches Telegram exactly once.
**Status:** drill run once, evidence filed below. Work PR: see board record.
**Owner:** muse_7. **Branch:** `muse7/task-frd-032-drilled-alert-proof`.
**Assignment:** issue #35 comment 7066153025 (Muse, coordinator, ~22:31 IST 2026-11-21).
**Direction:** re-issued direction comment 7069303518 (02:41 IST 2026-11-22),
endorsed in the coordinator watch comment 7069505715 (~03:00 IST).
An earlier reply (7068518395, 01:37 IST) was held for verification;
the re-issue plus the watch endorsement is the verified direction this drill ran under.

## 1. Drill path — verified before sending anything

Gate (merged PR #1071, merge commit `2e62f4b3`, 2026-11-19):
`FRIDAY/src/friday/proactive/owner_notify.py` — `notify_owner(text, severity=Severity.ALERT,
event_key=...)`. Only `ALERT`/`REPORT` send; `ROUTINE` is held (`BELOW_BAR`).
Anti-spam, all persisted: per-event-key cooldown 6h, identical-text dedupe 1h,
global floor 120s between sends, daily cap 20 (owner IST day).
Kill switch `FRIDAY_OWNER_NOTIFY=off`, re-checked on every call.
Send path: `friday.proactive.telegram_gateway.send_owner_message` via
`@fridayuniverse_bot` to the owner's Telegram chat (`TELEGRAM_CHAT_ID`).
Gate state file: `FRIDAY/.data/owner_notify/state.json` (live service cwd).

No dedicated drill script, endpoint, or flag exists in the repo:
code search for "drill" (48 hits) is all backup/restore drills; "drilled"
has one hit (a backup audit doc); the FRIDAY API server has no drill
endpoint (its only "drill" hit is a comment about TASK-FRD-014).
The trigger is therefore a direct `notify_owner()` call in the FRIDAY
service environment on Server 1 (cwd `/opt/friday_universe/FRIDAY`,
venv `/opt/friday_universe/venv/bin/python`).

Fleet state verified this run (bridge, Server 1, ~03:31–03:33 IST):
- FRIDAY.service active (running) since 01:22:24 IST; Main PID 1796021.
- Server 1 checkout: branch `main`, commit `7b245061` (= current main head
  at drill time); gate blob `a330a365...` byte-identical to main.
  Server 2 checkout `c6c129ea` is 283 ahead / 0 behind the PR #1071 merge,
  gate blob identical there too.
- Kill switch `FRIDAY_OWNER_NOTIFY`: unset — grepped the service unit,
  the `FRIDAY.service.d` drop-in, `/opt/friday_universe/.env` and
  `FRIDAY/.env` (0 matches); live probe `_kill_switch_active()` = False.
- Gateway configured: live probe `TelegramGateway.is_configured()` = True.
- Gate state before the drill (`FRIDAY/.data/owner_notify/state.json`,
  Server 1): day `2026-11-21`, `day_count` 4/20, `last_sent_at`
  2026-11-21 21:05:44 IST (~6.5h before the drill — global floor clear),
  key `self_report:daily:2026-11-21`. Fresh event key `drill:frd-032`,
  so no per-key cooldown applies.

## 2. The drill — run once

- **Time:** 2026-11-22 03:34:58 IST (epoch 1795298698.61).
- **Trigger:** one-off Python in the FRIDAY service environment on Server 1:
  `notify_owner(text, severity=Severity.ALERT, event_key='drill:frd-032')`.
- **Result:** `NotifyResult.SENT`.
- **Text sent (verbatim):**
  `[DRILL - TASK-FRD-032] FRIDAY drilled-ALERT proof (post-#1071). Planned drill,
  not a real incident - please ignore. Event key drill:frd-032. Sent 2026-11-22
  03:34:58 IST. Verifying one drilled alert reaches Telegram exactly once.`
- No second drill was run: a repeat would itself be a duplicate send and
  corrupt the exactly-once evidence.

## 3. Exactly-once evidence (server side)

Gate state after the drill (`FRIDAY/.data/owner_notify/state.json`, Server 1):

```json
{
  "day": "2026-11-22",
  "day_count": 1,
  "keys": { "drill:frd-032": 1795298698.6104307 },
  "last_sent_at": 1795298698.6104307,
  "texts": { "daa3b93631475b1f9162e11159850b213d34cc92297a47c6a8912a3cae0c7fda": 1795298698.6104307 }
}
```

Day rolled to 2026-11-22 and the count reset (4 on Nov 21 → 1 today).
Exactly one key, one text hash, one `last_sent_at` — all the drill epoch
(03:34:58 IST). One `notify_owner` call produced one `SENT`, one state
increment, one `sendMessage`. No other send is recorded today.

## 4. Limitation, stated plainly

`send_owner_message` returns `bool` only — the code path captures no
Telegram `message_id`, and the gate log line carries the event key and
the day count, not the message id. So the Telegram-side message id is
not in this file: it is visible on the owner's Telegram app, where one
drill-marked message should have arrived at 03:34:58 IST. What this
proof establishes from the server side is that exactly one alert was
issued through the gate and accepted for sending, once. If the owner
sees anything other than exactly one drill message, that contradicts
this record and the task is not closed.
