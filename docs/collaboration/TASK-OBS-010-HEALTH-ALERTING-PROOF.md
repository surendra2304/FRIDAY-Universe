# TASK-OBS-010 — Health alerting proof (fix OBS-008 gap (b) + re-verify end-to-end)

**Task:** fix the OBS-008 gap (b) HTML-escape of alert text and verify
crash-loop/health alerting end-to-end.
**Owner:** muse_1. **Branch:** `muse1/task-obs-010-health-alerting-proof`.
**Assignment:** coordinator watch, issue #35 comment 7085918134
("Claim OBS-010 next. Queue: OBS-010 → VAL-013* → TASK-REL-080*").
**Claim:** issue #35 comment 7086800626 (~03:55 IST 2026-11-23).
Claim PR #1433 merged 2026-11-23 04:15:03 IST (merge `41ba369a`;
CI 9/9 green — 7 success, 2 skipped, 0 failed — mergeable clean).
**Work:** this document + gap (b) fix + tests + board flip CLAIMED →
IN_REVIEW. Work PR: see board record.

## Verdict

- **Gap (b) FIXED in the gateway** — alert text is HTML-escaped in
  `TelegramGateway.send_message`, the single send choke point (§1).
- **Watcher timers verified enabled and active on both servers** —
  firing every 5 minutes, state fresh (§2).
- **One controlled alert delivered end-to-end: PROVEN through the
  watcher dispatch path with the FIXED code, once** — a real
  `SERVICE_DOWN` condition raised by the watcher on Server 1, with
  the raw `<urlopen error ...>` in the text, was forwarded by its
  `--alert-command` into `notify_owner()` and returned
  `NotifyResult.SENT`, exactly once (§3).
- **Gap (a) re-verified: `FLEET_ALERT_COMMAND` is STILL unwired on
  both servers** — not wired in this task (needs Muse's decision on
  the command + hub clearance for live systemd changes); production
  watcher alerts remain journal-only until it lands (§4).
- **No alert storm:** one watcher run, one notify call, one SENT (§5).

## 1. Gap (b) fix — HTML-escape in the gateway

OBS-008 §4: the watcher's alert text contains the raw probe error
`error=URLError: <urlopen error [Errno 111] Connection refused>`, and
the gateway sends with `parse_mode=HTML` without escaping — Telegram
rejects the malformed tag, so the first drill attempt returned
`NotifyResult.FAILED` and recorded nothing.

**Fix location: the gateway, not the watcher.** File:
`FRIDAY/src/friday/proactive/telegram_gateway.py` (all line numbers
are in the work-PR file):

- line 45: `import html`
- line 209: `def send_message(self, text, chat_id=None)`
- line 229: `safe = html.escape(text, quote=False)` — escaping happens
  **before** chunking, so no chunk can ever carry a raw `<` or `>`
- line 239: the send itself is unchanged
  (`{"chat_id": target, "text": chunk, "parse_mode": "HTML"}`)

`quote=False` escapes only `&`, `<`, `>` — exactly the three
characters Telegram's HTML mode requires — so quotes stay literal.
The module docstring records the rule (lines 35–39), and the
`send_message` docstring (lines 210–227) states that callers must NOT
escape as well, or the text double-escapes (`&amp;lt;`).

**Why the gateway (the single choke point) rather than the watcher:**
every Telegram send goes through `send_message` — watcher alerts via
`notify_owner`, the G7/G8 self-report, brain replies, status lines —
so the fix covers the whole class of failure, not one instance. Code
search confirms no caller relies on HTML formatting through this
gateway: `parse_mode` appears only in this file under `FRIDAY/src`,
and the one `<b>` in the repo is a mocked LLM reply in
`FRIDAY/tests/test_delegation_fast_path.py:201`, not gateway
formatting. Trade-off, stated plainly: a well-formed `<b>...</b>` in
a brain reply now renders literally instead of bold; delivery is
guaranteed instead of the message failing outright on a malformed
tag. Delivery beats formatting for an owner-alert channel.

**Tests** (new/changed files in the work PR):

- `FRIDAY/tests/test_telegram_gateway_escape.py` (new, 8 tests):
  the exact OBS-008 failure text sends escaped (`&lt;urlopen error
  [Errno 111] Connection refused&gt;`, no raw `<`/`>` in the payload,
  `parse_mode` still `HTML`); `&` is escaped (no entity injection);
  plain text passes through unchanged; quotes stay literal;
  well-formed tags render literally (trade-off locked); long text
  chunks after escaping with no raw brackets in any chunk;
  no-chat-id still returns `False`; `send_owner_message` hands the
  RAW text to `send_message` (no double-escape).
- `tests/test_fleet_health_watcher.py` (+1 guard test in
  `TestDispatchAlerts`): `dispatch_alerts` passes `FLEET_ALERT_TEXT`
  through RAW to the alert command — locking the single-escape-point
  decision so a future watcher change cannot double-escape.

**Local test results** (this run, venv pytest 9.2.0, minimal local
tree — see Limitations): new gateway tests **8/8 pass**; watcher
tests **33/33 pass** (32 existing + 1 new). Negative control: the
same 8 gateway tests against the UNFIXED gateway file fail 4 (the
escaping tests) and pass 4 — the tests genuinely test the fix.
CI on the work PR is the authority on the real tree.

## 2. Timer enablement — both servers (bridge, 2026-11-23 ~04:03–04:06 IST)

Server 1 (10.0.0.121) and Server 2 (10.0.0.120) both ONLINE
(`get_system_info`, bridge v1.30.0).

| Check | Server 1 | Server 2 |
| --- | --- | --- |
| `systemctl is-enabled fleet-health-watcher.timer` | `enabled` | `enabled` |
| `systemctl is-active fleet-health-watcher.timer` | `active` | `active` |
| Last trigger | 04:00:57 IST | 04:00:58 IST |
| Next trigger | 04:05:57 IST | 04:05:58 IST |
| `--status` | `fresh`, last cycle 2026-11-22T22:31:01Z, age 164s | `fresh`, last cycle 2026-11-22T22:31:00Z, age 182s |

Timer unit is the repo unit (`deploy/fleet-health-watcher.timer`: 5-minute
`OnUnitActiveSec`, `Persistent=true`). On-disk watcher script hashes
`226e5dc8d872d62d38acec72f962292b457c2957` on BOTH servers (git
hash-object) — byte-identical to the main blob; the gateway hashes
`ce5d044df9f02d9f2b518473b83034fc2979cdfd` and `owner_notify.py`
`a330a3654a6f7e790ccbb454ba2b266db671fa20` on Server 1 — both
byte-identical to main.

Open alerts at probe time (state files, cooldown-suppressed — see §5):
Server 1: `IntelX:HEALTH_UNREACHABLE`, `IntelX:SERVICE_DOWN`,
`Futuris:SERVICE_DOWN`, `Stratex:SERVICE_DOWN`,
`Stratex-Daemon:SERVICE_DOWN`. Server 2: `VyralX:SERVICE_DOWN`,
`VyralX-Daemon:SERVICE_DOWN`, `Sentinel:SERVICE_DOWN`. These are the
sleeping copies on the opposite host (OBS-008 §6), plus Stratex on
Server 1's map now also flags (Stratex runs on AWS) — noise, not a
storm; cooldown suppresses re-alerts.

## 3. The drill — one alert end-to-end with the FIXED code (Server 1, 2026-11-23 04:12:48–57 IST)

Drill path verified before sending (same gate as OBS-008/FRD-032):
`FRIDAY/src/friday/proactive/owner_notify.py` — `notify_owner(text,
severity=Severity.ALERT, event_key=...)`, kill switch
`FRIDAY_OWNER_NOTIFY` unset (`_kill_switch_active()` = False),
gateway configured (`TelegramGateway.is_configured()` = True). Gate
state before: day `2026-11-22`, `day_count` 8/20, `last_sent_at`
1795361871.71795 (21:07:51 IST 2026-11-22 — the G7 daily
self-report; the global 120s floor long clear), fresh event key
`drill:obs-010`.

The fixed gateway is not deployed yet (the deployed FRIDAY service
still runs the unfixed code — see Limitations), so the drill ran the
work-PR file staged at `/tmp/obs010/telegram_gateway.py` on Server 1,
sha256 `7ae95d58bc4721880f9d357d4b009504be9f5189a1eb4f23936412867a0ce422`
— verified byte-identical to the file in this PR. The drill script
(`/tmp/obs010_drill.py`, removed after the run) loaded that module
and patched its `send_owner_message` into
`friday.proactive.telegram_gateway` so `notify_owner()` sent through
the FIXED `send_message`; the alert text itself was passed UNESCAPED,
exactly as the watcher produces it — the escaping had to happen
inside the fix, nowhere else.

Trigger: the watcher itself, run once manually with a synthetic down
service and a drill alert command — the real dispatch path, not a
direct notify call:

```text
scripts/fleet_health_watcher.py --once \
  --services "DrillProbe:59999" \
  --state /tmp/muse1-obs010-state.json \
  --alert-command "/opt/friday_universe/venv/bin/python /tmp/obs010_drill.py"
```

The alert command called `notify_owner()` with the watcher's
`$FLEET_ALERT_TEXT`, drill-marked, event key `drill:obs-010`. A
separate `/tmp` state file was used so the production state file was
untouched.

- **Watcher output:** `[CRITICAL] SERVICE_DOWN DrillProbe:
  ActiveState=inactive SubState=dead; error=URLError: <urlopen error
  [Errno 111] Connection refused>` then `[CYCLE 2026-11-23 04:12:57
  IST] 0/1 healthy; unhealthy: DrillProbe`.
- **Drill script output:** `kill_switch_active: False`,
  `gateway_configured: True`, `alert_text_raw_has_brackets: True`
  (the raw `<...>` reached the gate unescaped, as designed).
- **Result:** `DRILL-NOTIFY: NotifyResult.SENT` at 04:12:56 IST
  (epoch 1795387376.230433). The OBS-008 failure case — the same raw
  `<urlopen error ...>` text that returned `FAILED` before the fix —
  now sends.
- **Exactly-once evidence (server side):** gate state
  `FRIDAY/.data/owner_notify/state.json` after the drill: day
  `2026-11-22` → `2026-11-23`, `day_count` 8 → 1 (day rollover reset,
  then exactly one increment), exactly one new key `drill:obs-010` =
  1795387376.230433, exactly one new text hash, `last_sent_at` =
  1795387376.230433. One `notify_owner` call produced one `SENT`,
  one state increment, one `sendMessage`. No second drill was run.
- **Text offered to the gate (verbatim, raw):**
  `[DRILL - TASK-OBS-010] Watcher alert-path drill (gap (b) fix):
  [CRITICAL] SERVICE_DOWN DrillProbe: ActiveState=inactive
  SubState=dead; error=URLError: <urlopen error [Errno 111]
  Connection refused> Planned drill, not a real incident - please
  ignore. Event key drill:obs-010.` The gateway sent the escaped
  form (`&lt;urlopen error [Errno 111] Connection refused&gt;`).

## 4. Gap (a) re-verified — still unwired, NOT fixed here

`FLEET_ALERT_COMMAND` is **still unset on both servers** (checked
this run, 2026-11-23 ~04:03–04:05 IST):

- Server 1: `systemctl show fleet-health-watcher.service -p Environment` →
  `Environment=` (empty). No drop-in directory exists.
- Server 2: `Environment=FLEET_WATCH_SERVICES=Sentinel:8008,Cortex:8009,
  VyralX:8010,VyralX-Daemon:-` — fleet map only, no alert command.

Per the board record, gap (a) is NOT in this record — it was included
only if found unwired during the run. It IS unwired, and it is
reported here as a carried-forward open item, NOT wired in this task:
wiring it is a live-fleet change (systemd drop-ins on both servers +
`daemon-reload`) needing Muse's decision on which notify
command/endpoint to wire and hub clearance for the live change, and
this run holds neither. Until gap (a) lands, production watcher
alerts stay journal-only — the drill proves the code path works when
both gaps are addressed; it does not claim production delivery works
today. (Same position as OBS-008 §3.)

## 5. No alert storm

- Drill discipline: one watcher run, one `notify_owner` call, one
  `SENT`. The production watcher state file was not touched (drill
  state lived in `/tmp/muse1-obs010-state.json`); the drill script
  and staged gateway were removed from Server 1 `/tmp` after the
  run (`/tmp/obs010`, `/tmp/obs010_drill.py`, `/tmp/obs010_probe.py`,
  `/tmp/muse1-obs010-state.json` — all removed, verified absent).
- The gate's own anti-spam held: per-key 6h cooldown (fresh key),
  120s global floor (last send 7h earlier), daily cap 20 (first send
  of the new day). No other alert fired during the run.

## 6. Secondary observations (not in the acceptance criteria)

- **Fleet-map overlap (OBS-008 §6, unchanged):** each host's watcher
  flags the other host's services down every cycle. Server 1's map
  now also flags `Stratex:SERVICE_DOWN` and
  `Stratex-Daemon:SERVICE_DOWN` (Stratex runs on AWS). Cooldown
  suppresses re-alerts, so this is noise, not a storm — but each
  watcher's map should cover only its own host's services. Follow-up,
  not fixed here.
- Server 1 checkout is on `main` (`3f9cec0c`); Server 2 checkout is on
  `muse10/task-frd-037-chat-live-runs` (`db933cfc`) — read-only note,
  not touched.
- One transient bridge failure during the run (`BRIDGE_NO_DATA` on a
  Server 2 `run_shell` call, ~04:04 IST); the identical call retried
  successfully immediately after. No data lost.

## 7. Limitations, stated plainly

- Telegram-side receipt is not visible to me: `send_message` returns
  bool only — no Telegram `message_id` is captured server-side. The
  exactly-once claim is server-side (one `SENT`, one gate-state
  increment), same limitation as OBS-008 and TASK-FRD-032.
- **The drill proved the FIXED code, not the deployed code.** The
  fixed gateway ran from `/tmp` on Server 1; the deployed FRIDAY
  service still runs the unfixed gateway from main. The fix reaches
  production through the normal deploy after this work PR merges —
  until then, a real `<...>` alert would still fail exactly as in
  OBS-008.
- Local tests ran in a minimal tree (venv pytest 9.2.0 + `requests`)
  with stubbed `friday/proactive/__init__.py` and
  `friday/core/__init__.py` — the real ones import `morning_brief`
  and `friday.core.config`, which were not present locally. The module
  under test (`telegram_gateway.py`) is byte-identical to the PR
  file (sha256 `7ae95d58...`), and the watcher tests load the repo
  script directly; CI on the work PR is the authority on the real
  tree.

## Next

- Muse review/merge of this work PR. (Claim PR #1433 merged
  2026-11-23 04:15:03 IST, merge `41ba369a`; the branch was rebased
  onto main `65dffccf` before this work PR opened — no force-push.)
- Muse decisions still owed: wire `FLEET_ALERT_COMMAND` on both
  servers (which endpoint/command) + hub clearance for the live
  change — gap (a), carried forward. Until it lands, watcher alerts
  stay journal-only.
