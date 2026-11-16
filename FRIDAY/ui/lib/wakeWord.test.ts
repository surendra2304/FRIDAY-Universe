/* Wake-word tests for lib/wakeWord.ts.
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/wakeWord.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import {
  extractAfterWake,
  loadWakeArmed,
  matchWakePhrase,
  normalizeTranscript,
  saveWakeArmed,
  WAKE_PHRASES,
  WAKE_STORAGE_KEY,
} from "./wakeWord.ts";

// Normalization: case, punctuation and spacing never matter.
assert.equal(normalizeTranscript("  Hey,  FRIDAY! "), "hey friday");
assert.equal(normalizeTranscript("what's the time?"), "what s the time");

// Every default phrase matches, mid-sentence too (interim results are
// partial), and the matched phrase is returned normalized.
for (const phrase of WAKE_PHRASES) {
  assert.equal(matchWakePhrase(phrase), phrase);
}
assert.equal(matchWakePhrase("um hey friday are you there"), "hey friday");
assert.equal(matchWakePhrase("Okay FRIDAY, listen"), "okay friday");

// Near-misses must NOT fire: a bare "friday", a different name, a phrase
// glued inside another word, and empty input.
assert.equal(matchWakePhrase("friday"), null);
assert.equal(matchWakePhrase("tell me about friday's roadmap"), null);
assert.equal(matchWakePhrase("hey fridays"), null);
assert.equal(matchWakePhrase("hey siri"), null);
assert.equal(matchWakePhrase(""), null);

// The would-be command after the wake phrase.
assert.equal(extractAfterWake("hey friday what time is it"), "what time is it");
assert.equal(extractAfterWake("hey friday"), "");
assert.equal(extractAfterWake("no wake here"), null);

// The preference round-trips through a Storage-shaped object, defaults
// to off, and survives a storage backend that throws (private mode).
class FakeStorage {
  data = new Map<string, string>();
  getItem(k: string) {
    return this.data.get(k) ?? null;
  }
  setItem(k: string, v: string) {
    this.data.set(k, v);
  }
}
const store = new FakeStorage();
assert.equal(loadWakeArmed(store), false);
saveWakeArmed(store, true);
assert.equal(store.data.get(WAKE_STORAGE_KEY), "on");
assert.equal(loadWakeArmed(store), true);
saveWakeArmed(store, false);
assert.equal(loadWakeArmed(store), false);
const broken = {
  getItem(): string | null {
    throw new Error("denied");
  },
  setItem(): void {
    throw new Error("denied");
  },
};
assert.equal(loadWakeArmed(broken), false);
saveWakeArmed(broken, true); // must not throw

console.log("wakeWord.test: all expectations passed");
