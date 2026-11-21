# TASK-STR-DAEMON-001 — Stratex daemon Telegram triple-send watch

- **Task:** Stratex daemon Telegram triple-send watch — if a triple-send recurs, root-cause it; otherwise file the monitoring evidence for the silent period since 2026-11-19.
- **Assignment:** issue #35 comment 7066625408 (Muse, coordinator, ~23:07 IST 2026-11-21). Board record: `TASK-STR-DAEMON-001`, status AVAILABLE, owner `muse_2` (Muse's board PR #1243, merged 23:16 IST as `909f00de`).
- **Claim:** issue #35 comment 7066704834 (Muse 2, 23:14 IST 2026-11-21). Branch: `muse2/task-str-daemon-001`. Base: main `909f00de`.
- **Outcome: the triple-send DID recur — in its per-restart form — and is root-caused below.** No repeating (every-8–9-minute) triple was observed in this watch window.

## 1. Verdict

The daemon sent exactly **5 Telegram messages** between the 2026-11-21 21:27:40 IST restart and the last probe (23:25:46 IST), and **0 before that restart in the live journal's reach**. All 5 are classified, with exact template-length matches against the live code:

| # | Sent (IST) | Chars | Message | Trigger |
|---|-----------|-------|---------|---------|
| 1 | 2026-11-21 21:29:12 | 392 | 🚀 Stratex Online — Multi-Venue | Daemon start, unconditional |
| 2 | 2026-11-21 21:29:14 | 132 | 📡 Stratex Started (balance/positions) | Daemon start, unconditional |
| 3 | 2026-11-21 21:32:26 | 371 | 📊 DAILY SUMMARY — 2026-11-21 | First scan cycle after restart |
| 4 | 2026-11-21 21:33:45 | 369 | 🟢 TRADE EXECUTED — BTCUSDT BUY 0.0025 @ 59889.32 | Demo order filled 21:33:44 |
| 5 | 2026-11-21 21:33:49 | 365 | 🟢 TRADE EXECUTED — ETHUSDT BUY 0.111 @ 1681.3 | Demo order filled 21:33:48 |

No sends after 21:33:49 through the last probe (23:25:46 IST). Zero failed sends (`SendMessage failed` count: 0) in the window. The daemon kept scanning every 15 s with no further Telegram output.

## 2. Root cause of the per-restart triple (sends 1–3)

Every Stratex-Daemon start emits the same three messages **by design**:

1. **Startup pair — unconditional.** `Stratex/autonomy/run_daemon.py` `main()` sends two messages on every start, with no dedupe or once-per-day gate:
   - `telegram.send_message("🚀 Stratex Online — Multi-Venue" …)` (call at line 3974; template literal at 3975) — computed template length **392 chars, exact match** to send 1.
   - `telegram.send_message("📡 Stratex Started" …)` (call at line ~3996; template at 3997) — computed length **132–133 chars** depending on balance digits, matching send 2 (132).
   - Both fire right after `telegram.start_listening()` registers the webhook (`[TELEGRAM] Webhook registered …` logged 21:29:11, one second before send 1) and before `Trading engine started` (21:29:15).
2. **Daily summary — re-sent because its throttle is in-memory.** `StratexTradingEngine._maybe_send_daily_summary` (`run_daemon.py:1125-1172`) sends the 📊 daily summary once per UTC day *per process*: `_last_summary_date` is initialised to `""` in `__init__` (`run_daemon.py:353`) and set to today at line 1133. A restart resets it, so the first scan cycle of the new process re-sends that day's summary even though the previous process already sent it. The first scan after this restart completed at ~21:32:26 (engine started 21:29:15; a full scan takes ~3 min) — exactly when send 3 fired. Computed template length **370–371 chars** depending on equity digits, matching send 3 (371).

**That is the "same triple per restart"** recorded in the earlier investigation. Any restart — deploy, manual restart, or crash-loop — re-emits it.

## 3. Sends 4–5 are legitimate per-trade alerts, not the triple

`Stratex/autonomy/multi_venue_engine.py:866-885` sends one inline `🟢 TRADE EXECUTED` message per filled order (`result.status == "FILLED"`). The journal shows a strict 1:1 pairing:

- `21:33:44 Order placed: binance_futures BTCUSDT BUY 0.0025 @ 59889.32` → `21:33:45 Message sent (369 chars)`; template computed with an 11-digit ticket = **369, exact**.
- `21:33:48 Order placed: binance_futures ETHUSDT BUY 0.111 @ 1681.3` → `21:33:49 Message sent (365 chars)`; template computed with an 11-digit ticket = **365, exact**.

Both orders are demo (`BINANCE_FUTURES Environment: demo`, `https://demo-fapi.binance.com`, logged at engine start 21:29:07). Exactly 2 `Order placed` lines exist since the restart, each with exactly 1 notification. No order went un-notified and no notification went un-ordered.

## 4. The restart that broke the silence

- `21:27:24 IST` systemd began stopping the old process (PID 1656282); it ignored SIGTERM (`Shutdown signal received`, then `stop-sigterm timed out`, SIGKILL 21:27:39); the unit restarted at `21:27:40 IST` as PID 1684339 (`NRestarts=0`, so this was an issued restart, not a crash-loop auto-restart).
- **Trigger (timing-consistent, not proven):** PR #1225 (TASK-REL-064/065 batch B, incl. the Stratex-Daemon unit interpreter flip in declared state) merged at 21:25:23 IST (`03378ba4`); the daemon stop began 2 min 1 s later — the expected Fleet CD deploy latency. The live unit still runs `/opt/friday_universe/venv/bin/python` (old venv), matching REL-065's "declared state only; live unit drift recorded" note. CD deploy logs were not inspected; the trigger is inferred from timing only.

## 5. The silent period, and the limit of what the live journal can prove

- **Silent period 2026-11-19 01:04 → 2026-11-21 21:27:40 IST: 0 sends.** This rests on the board's prior journal verification (WORK_BOARD.yaml, TASK-STR-DAEMON-001 parent record: "zero sends since 2026-11-19 01:04"). It is **not re-verifiable from the live journal now**, because the Server 1 journal retains only ~2 hours of this unit's output:
  - At the 23:23 IST probe the earliest retained `Stratex-Daemon.service` line was `2026-11-21T21:32:52`; the journal holds 212 MB total and the daemon logs hundreds of lines per minute (strategy scan lines every 15 s).
  - The same retention slide was observed live during this watch: a probe at ~23:16 IST still saw all 5 sends; by 23:22 IST the 21:29:12 / 21:29:14 / 21:32:26 lines had already rotated out (the re-count then showed only the 2 trade notifications). The 5-send capture in this run's probe files is the surviving record.
- **The 2026-11-18 episode** (3-message set every ~8–9 min, 20:24–22:31, 46 sends/48h) is likewise not re-verifiable from the live journal. The code-verified per-restart triple explains a repeating triple **if the daemon was restarting on that cadence that evening** (~15 restarts × 3 messages ≈ 46 sends fits the count); the 11-18 restart cadence itself is not provable from any source available in this run and remains an inference, not a verified fact. The 11-18 episode as observed stands on the earlier board record.

## 6. Probe log (all read-only, bridge MCP `run_shell`, server 1)

| Probe (IST) | Command / check | Result |
|---|---|---|
| 23:15 | `systemctl show/status Stratex-Daemon.service` | active/running since 21:27:40, MainPID 1684339, NRestarts=0 |
| ~23:16 | `journalctl -u Stratex-Daemon.service --since 2026-11-18 19:34` — `TELEGRAM.*Message sent` count | 5 (21:29:12, 21:29:14, 21:32:26, 21:33:45, 21:33:49) |
| ~23:16 | Restarts since 11-19 01:04 | 1 — 21:27:40 IST only |
| 23:2x | Journal 21:27–21:34 (stop/start, startup sequence) | Stop 21:27:24, SIGKILL 21:27:39, start 21:27:40; webhook registered 21:29:11; engine started 21:29:15 |
| 23:2x | Journal 21:32–21:34 (sends 3–5 context) | Send 3 at end of first scan; sends 4–5 1 s after each `Order placed` |
| 23:22 | Re-count + journal horizon | Count now 2 (retention slide — see §5); earliest retained line 21:32:52 |
| 23:23 | `journalctl --disk-usage`, earliest line | 212 MB; earliest retained Stratex-Daemon line 21:32:52 IST |
| 23:25 | `Order placed` vs `Message sent` since restart; failed sends | 2 orders / 2 notifications, 1:1; 0 failed sends |

Bridge note: the MCP stream cut out transiently on `initialize` three times during this watch (IncompleteRead / RemoteDisconnected); read-only retries succeeded. No live change was made at any point.

## 7. Follow-ups for Muse (not done in this task)

1. **Persist the daily-summary throttle.** `_last_summary_date` is in-memory (`run_daemon.py:353`); persisting it (e.g. in `Stratex/state/`) would stop a restart re-sending the day's summary — removing the third leg of the per-restart triple.
2. **Consider gating the startup pair** (once per UTC day, or a single combined startup message) if restarts stay frequent; as-is, every restart costs the owner 2 messages plus the summary.
3. **Journal retention is too short for a multi-day watch.** The daemon's scan logging fills the journal in ~2 h; a watch like this needs either persistent send logging (e.g. a `telegram_sends.jsonl` append) or longer journal retention before the next recurrence can be caught with its full history intact.
4. **Board record:** `TASK-STR-DAEMON-001` is AVAILABLE / owner `muse_2` on the board (Muse's PR #1243); this PR files the monitoring evidence only and does not touch the board — Muse owns the board transition.

## 8. Sources

- Live journal, Server 1, `Stratex-Daemon.service` (bridge MCP `run_shell`, read-only). Raw probe outputs preserved in the worker workspace, `~/workspace/muse2/task-str-daemon-001/` (`daemon_*.json`).
- Live code at main `909f00de`: `Stratex/autonomy/run_daemon.py` (§2 refs), `Stratex/autonomy/multi_venue_engine.py:866-885`, `Stratex/notifications/telegram_bot.py:337-388` (`send_message`, 120 s identical-message dedupe).
- Template-length verification computed from the live code in this run (Online 392 exact; Started 132–133; Daily summary 370–371; TRADE EXECUTED 369/365 with 11-digit tickets).

— Muse 2
