/* TASK-IG2-WEB-02 — tests for lib/ranking.ts.
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/ranking.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import { movementLabel, rankEntries, splitPodium } from "./ranking.ts";

// Descending order + competition ranking with a tie.
const board = rankEntries([
  { id: "friday", name: "FRIDAY", score: 99.1, previousRank: 2 },
  { id: "stratex", name: "Stratex", score: 97.5, previousRank: 1 },
  { id: "memora", name: "Memora", score: 97.5 },
  { id: "forge", name: "Forge", score: 91.0, previousRank: 3 },
]);
assert.deepEqual(
  board.map((e) => [e.id, e.rank]),
  [
    ["friday", 1],
    ["stratex", 2],
    ["memora", 2],
    ["forge", 4],
  ],
);
assert.equal(board[1].tied, true);
assert.equal(board[2].tied, true);
assert.equal(board[0].tied, false);
assert.equal(board[0].movement, 1); // climbed 2 -> 1
assert.equal(board[1].movement, -1); // fell 1 -> 2
assert.equal(board[2].movement, null); // no previous rank
assert.equal(board[3].movement, -1); // 3 -> 4 because the tie pushed it down

// Ascending order (e.g. latency boards, where lower wins).
const latency = rankEntries(
  [
    { id: "a", name: "A", score: 300 },
    { id: "b", name: "B", score: 120 },
  ],
  "asc",
);
assert.deepEqual(
  latency.map((e) => e.id),
  ["b", "a"],
);

// Input is not mutated.
const input = [
  { id: "x", name: "X", score: 1 },
  { id: "y", name: "Y", score: 2 },
];
rankEntries(input);
assert.deepEqual(
  input.map((e) => e.id),
  ["x", "y"],
);

// Podium split never invents entries.
const { podium, rest } = splitPodium(board);
assert.equal(podium.length, 3);
assert.equal(rest.length, 1);
assert.equal(splitPodium(rankEntries([{ id: "only", name: "Only", score: 1 }])).rest.length, 0);

// Movement labels.
assert.equal(movementLabel(board[0]), "▲ 1");
assert.equal(movementLabel(board[1]), "▼ 1");
assert.equal(movementLabel(board[2]), "new");
assert.equal(
  movementLabel(rankEntries([{ id: "s", name: "S", score: 5, previousRank: 1 }])[0]),
  "— held",
);

console.log("ranking.test.ts: all expectations passed");
