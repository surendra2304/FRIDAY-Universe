/* Theme tests for lib/theme.ts.
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/theme.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import {
  DEFAULT_THEME,
  loadThemePref,
  parseTheme,
  resolveTheme,
  saveThemePref,
  THEME_STORAGE_KEY,
  type ThemeStorageLike,
} from "./theme.ts";

// The default is the theme the owner picked on 2026-11-17.
assert.equal(DEFAULT_THEME, "ultron");

// Only shipped themes parse; case and surrounding space never matter.
assert.equal(parseTheme("ultron"), "ultron");
assert.equal(parseTheme("halo"), "halo");
assert.equal(parseTheme(" HALO "), "halo");
assert.equal(parseTheme("Ultron"), "ultron");
assert.equal(parseTheme("aurora"), null);
assert.equal(parseTheme(""), null);
assert.equal(parseTheme(null), null);
assert.equal(parseTheme(undefined), null);

// Resolution order: query beats storage beats default; junk falls through.
assert.equal(resolveTheme("halo", "ultron"), "halo");
assert.equal(resolveTheme("ultron", "halo"), "ultron");
assert.equal(resolveTheme(null, "halo"), "halo");
assert.equal(resolveTheme("bogus", "halo"), "halo");
assert.equal(resolveTheme("bogus", "also-bogus"), "ultron");
assert.equal(resolveTheme(null, null), "ultron");
assert.equal(resolveTheme(), "ultron");

// The persisted preference round-trips through the one storage key.
{
  const backing = new Map<string, string>();
  const storage: ThemeStorageLike = {
    getItem: (k) => backing.get(k) ?? null,
    setItem: (k, v) => void backing.set(k, v),
  };
  assert.equal(loadThemePref(storage), null);
  saveThemePref(storage, "halo");
  assert.equal(backing.get(THEME_STORAGE_KEY), "halo");
  assert.equal(loadThemePref(storage), "halo");
  saveThemePref(storage, "ultron");
  assert.equal(loadThemePref(storage), "ultron");
}

// A storage that throws (private mode) reads as "no preference" and
// never makes saving throw either.
{
  const hostile: ThemeStorageLike = {
    getItem: () => {
      throw new Error("denied");
    },
    setItem: () => {
      throw new Error("denied");
    },
  };
  assert.equal(loadThemePref(hostile), null);
  saveThemePref(hostile, "halo");
}

console.log("theme.test.ts: all assertions passed");
