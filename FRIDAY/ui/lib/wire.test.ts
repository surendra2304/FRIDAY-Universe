/* Clock-rendering tests for lib/wire.ts (TASK-FRD-029).
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/wire.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import { clockTime, clockTimeOrBlank } from "./wire.ts";

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

console.log("wire.test.ts: all expectations passed");
