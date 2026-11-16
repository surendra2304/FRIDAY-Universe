/* TASK-IG2-WEB-02 (wiring) — tests for lib/fleetRank.ts.
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/fleetRank.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import { fleetRankEntries } from "./fleetRank.ts";

// Measured agents become entries scored by their latency.
const basic = fleetRankEntries([
  { id: "friday", name: "FRIDAY", latency_ms: 812.4 },
  { id: "stratex", name: "Stratex", latency_ms: 96.1 },
]);
assert.equal(basic.unmeasured, 0);
assert.equal(basic.entries.length, 2);
assert.deepEqual(basic.entries[0], {
  id: "friday",
  name: "FRIDAY",
  score: 812.4,
  scoreLabel: "812 ms",
});
assert.equal(basic.entries[1].scoreLabel, "96 ms");

// Unmeasured agents are counted, never scored: missing, NaN, infinite,
// negative and non-number latencies all stay off the board.
const mixed = fleetRankEntries([
  { id: "a", name: "A", latency_ms: 50 },
  { id: "b", name: "B" },
  { id: "c", name: "C", latency_ms: Number.NaN },
  { id: "d", name: "D", latency_ms: Number.POSITIVE_INFINITY },
  { id: "e", name: "E", latency_ms: -5 },
]);
assert.equal(mixed.entries.length, 1);
assert.equal(mixed.entries[0].id, "a");
assert.equal(mixed.unmeasured, 4);

// A measured 0 ms is a real measurement, not a missing one.
const zero = fleetRankEntries([{ id: "z", name: "Z", latency_ms: 0 }]);
assert.equal(zero.entries.length, 1);
assert.equal(zero.entries[0].scoreLabel, "0 ms");
assert.equal(zero.unmeasured, 0);

// Previous ranks pass through only for agents that had one.
const prev = new Map<string, number>([
  ["friday", 2],
  ["stratex", 1],
]);
const withPrev = fleetRankEntries(
  [
    { id: "friday", name: "FRIDAY", latency_ms: 100 },
    { id: "memora", name: "Memora", latency_ms: 100 },
  ],
  prev,
);
assert.equal(withPrev.entries[0].previousRank, 2);
assert.equal("previousRank" in withPrev.entries[1], false);

// Empty fleet → empty board, nothing unmeasured.
assert.deepEqual(fleetRankEntries([]), { entries: [], unmeasured: 0 });

// The input array and its agents are not mutated.
const input = [{ id: "x", name: "X", latency_ms: 12.6 }];
fleetRankEntries(input, new Map([["x", 3]]));
assert.deepEqual(input, [{ id: "x", name: "X", latency_ms: 12.6 }]);

console.log("fleetRank.test.ts: all expectations passed");
