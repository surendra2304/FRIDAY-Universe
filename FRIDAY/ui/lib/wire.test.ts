/* Clock-rendering tests for lib/wire.ts (TASK-FRD-029).
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/wire.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import { activityFrameTime, clockTime, clockTimeOrBlank } from "./wire.ts";

// A full ISO instant renders as the fleet-zone wall clock either way.
// 2026-11-19T11:13:05Z is 16:43:05 in Asia/Kolkata (UTC+5:30).
assert.equal(clockTime("2026-11-19T11:13:05.000Z"), "16:43:05");
assert.equal(clockTimeOrBlank("2026-11-19T11:13:05.000Z"), "16:43:05");

// Epoch milliseconds (the activity socket's Date.now() fallback) parse.
assert.equal(clockTimeOrBlank(0), "05:30:00");

// The autonomous log's old bare time-of-day string has no date, so
// Date cannot parse it: clockTime keeps its placeholder for the
// callers that rely on it, clockTimeOrBlank renders nothing — the
// activity log must show no time rather than "--:--:--" (FRD-029).
assert.equal(clockTime("16:43:05"), "--:--:--");
assert.equal(clockTimeOrBlank("16:43:05"), "");

// Missing values: placeholder from clockTime, blank from the OrBlank.
assert.equal(clockTime(""), "--:--:--");
assert.equal(clockTime(null), "--:--:--");
assert.equal(clockTime(undefined), "--:--:--");
assert.equal(clockTimeOrBlank(""), "");
assert.equal(clockTimeOrBlank(null), "");
assert.equal(clockTimeOrBlank(undefined), "");

// TASK-FRD-030: the live-append clock for activity socket frames. A
// frame's recorded_at wins over its timestamp — in particular a frame
// whose timestamp is the backlog's bare time-of-day fallback still
// renders its real time when recorded_at rides along (the FRD-030 bug
// was live rows rendering blank while the seed path showed the time).
assert.equal(
  activityFrameTime({ recorded_at: "2026-11-19T11:13:05.000Z", timestamp: "16:43:05" }),
  "16:43:05",
);
assert.equal(activityFrameTime({ timestamp: "2026-11-19T11:13:05.000Z" }), "16:43:05");
// A legacy frame (no recorded_at, bare timestamp) honestly shows no time.
assert.equal(activityFrameTime({ timestamp: "16:43:05" }), "");
assert.equal(activityFrameTime({ recorded_at: "", timestamp: "16:43:05" }), "");
// A frame carrying no time at all falls back to its arrival time.
assert.match(activityFrameTime({}), /^\d{2}:\d{2}:\d{2}$/);

console.log("wire.test.ts: all expectations passed");
