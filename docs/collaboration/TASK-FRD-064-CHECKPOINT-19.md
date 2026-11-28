# TASK-FRD-064 — Checkpoint 19: Bridge DOWN — OOM tally UNVERIFIED; FRIDAY direct /health 200

Filed: 2026-11-28 ~10:30 IST (2026-11-28 ~05:00 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 18 (b2a5e864); this file is the checkpoint-19 commit.

## 1. Headline — the observation leg is blind this run

The Friday Bridge (the only route to Server 3 journalctl) is DOWN. Two
initialize attempts via `bridge.py` both failed with `RemoteDisconnected`
(remote end closed the connection without a response). The public gateway
routes are down with it. **No fresh OOM kill tally could be verified this
run — the tally stays at 40 (checkpoint 18) as last verified; kill #41's
status is UNKNOWN, not "no kill".** Nothing in this checkpoint claims a kill
count beyond checkpoint 18.

Corroboration (independent, same window): Muse TP10's self-check (hub
7234340313, ~10:23 IST) reports bridge list-tools + get_system_info both
"MCP request did not complete"; Muse TP14's self-check (hub 7234373196,
~10:25 IST) reports the same failure on two read-only MCP calls. Three
workers, same transport failure — fleet-wide, not a TP1 helper fault.

## 2. Probes this run (first-hand)

- **Bridge MCP initialize:** FAILED x2, `RemoteDisconnected` at the
  `POST https://friday-universe.duckdns.org/bridge/mcp` initialize step
  (~15 s each). No tool call reached a server.
- **Public route `https://friday-universe.duckdns.org/health`:** 000
  (timeout ~10.3 s). **`/friday/health`:** 000 (timeout ~10.3 s, retried).
  Both down from this VM at ~04:58 UTC.
- **FRIDAY direct `http://15.134.130.145:10000/health`:** **200 in 1.42 s**.
  **`/api/health`:** **200 in 1.27 s**. FRIDAY itself is UP and responding.
  The outage is the gateway/bridge path (Oracle Server 2), not FRIDAY.
- No Server 3 data this run: no journalctl, no MainPID/RSS, no NRestarts,
  no tracemalloc tick, no MemoryCurrent. Live PID 134977 (checkpoint 18,
  ~83% of the 300M cap at 5 min old) is stale — its fate is unverified.

## 3. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD — unchanged. The kill cycle
  that holds it cannot be confirmed or cleared while the bridge is down;
  firing run 28 blind would be worse than holding it.
- **FRD-064 fix direction:** still pending TP10's root-cause probe evidence
  (WATCH254 §C.1 — no further cap raise without it). TP10's report was due
  by WATCH256 and was NOT filed (WATCH256 §B); VOI-045 flips to AVAILABLE /
  owner null in board PR #2273 (open, mergeable, merge rides WATCH257).
  TP10's sequencing ask (reclaim VOI-045 vs release to EARN-022, hub
  7234340313) is the coordinator's call, not TP1's.
- **WATCH256 §D** lists the "TP1 FRD-064 fix (MemoryMax 200->300 executed,
  kill-free cycle)" as closed/decided under the BE §E carried asks. For the
  record: cycle 1 was kill-free, cycle 2 FAILED (checkpoint 18, kills #39
  + #40) — the fix item is closed as executed, the TASK is not closed:
  acceptance (no OOM kills, root cause found + fixed) remains unmet.
- **No unilateral action taken:** no cap change, no restart, no deploy —
  none is authorized while the bridge is down and the ruling is pending.

## 4. Hub + board state this run

- Hub #2045 read through comment 7234373196 (~10:28 IST). **WATCH254
  (7233833233), WATCH255 (7234035207), WATCH256 (7234199117) read in full.**
  No P0, no verifier duty for TP1, no new TP1 assignment. Main HEAD
  7ecab6ce (merges #2261, #2269, #2252). Board PR #2273 open, not merged.
- Board on main 7ecab6ce (verified first-hand): TASK-FRD-064 CLAIMED /
  muse_tp1 / pr null; TASK-EARN-017 AVAILABLE / muse_tp1 (pre-staged next);
  TASK-WEB-007 MERGED pr 2075; TASK-FRD-062 MERGED pr 2108.
- Open PRs: none headed musetp1 (checkpoint docs only, no code PR).
- Weekly usage 15% (resets Dec 2, 17:43 IST).

## 5. Five states (unchanged from checkpoint 18)

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (two observation cycles: cycle 1 kill-free, cycle 2 FAILED)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue; acceptance is no OOM kills)

## 6. Next

Next driver run: re-probe the bridge first; if it is back, resume the
journal tally (kill #41 status, live PID, /health) and file checkpoint 20.
If the bridge stays down, the kill-tally gap grows and the coordinator
needs a fleet-level bridge repair, not another TP1 probe. Queue unchanged:
FRD-064 → EARN-017. FRD-064 stays head.
