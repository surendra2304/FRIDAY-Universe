/* TASK-IG2-WEB-07 — tests for lib/glassWidgets.ts.
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/glassWidgets.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import {
  addTodo,
  buildMapEmbedUrl,
  buildSearchUrl,
  clearDoneTodos,
  clockParts,
  DEFAULT_SETTINGS,
  enabledWidgets,
  GRADIENT_PRESETS,
  loadSettings,
  loadTodos,
  removeTodo,
  sanitizeSettings,
  sanitizeTodos,
  saveSettings,
  toggleTodo,
  toggleWidget,
  weatherCodeLabel,
  WIDGET_CATALOGUE,
  type StorageLike,
} from "./glassWidgets.ts";

function fakeStorage(seed: Record<string, string> = {}): StorageLike & { data: Map<string, string> } {
  const data = new Map(Object.entries(seed));
  return {
    data,
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => void data.set(k, v),
  };
}

// Catalogue covers exactly the six GNTD widgets named in the cluster.
assert.deepEqual(
  WIDGET_CATALOGUE.map((w) => w.id),
  ["search", "todo", "weather", "music", "notes", "map"],
);

// Defaults: everything on, gradient background, a real preset.
assert.equal(enabledWidgets(DEFAULT_SETTINGS).length, 6);
assert.ok(GRADIENT_PRESETS.some((p) => p.css === DEFAULT_SETTINGS.background.value));

// Toggle is immutable and flips only the named widget.
const off = toggleWidget(DEFAULT_SETTINGS, "music");
assert.equal(off.enabled.music, false);
assert.equal(off.enabled.search, true);
assert.equal(DEFAULT_SETTINGS.enabled.music, true);
assert.equal(enabledWidgets(off).length, 5);
assert.equal(toggleWidget(off, "music").enabled.music, true);

// Sanitize: junk in, safe settings out.
assert.deepEqual(sanitizeSettings(null), DEFAULT_SETTINGS);
assert.deepEqual(sanitizeSettings("nope"), DEFAULT_SETTINGS);
const partial = sanitizeSettings({
  enabled: { todo: false, bogus: true },
  background: { kind: "image", value: "https://example.com/bg.jpg" },
  city: "  Pune ",
});
assert.equal(partial.enabled.todo, false);
assert.equal(partial.enabled.search, true); // missing -> default on
assert.equal("bogus" in partial.enabled, false);
assert.deepEqual(partial.background, { kind: "image", value: "https://example.com/bg.jpg" });
assert.equal(partial.city, "Pune");
const badBg = sanitizeSettings({ background: { kind: "video", value: "x" } });
assert.deepEqual(badBg.background, DEFAULT_SETTINGS.background);

// Storage round-trip; corrupt stored JSON falls back to defaults.
const store = fakeStorage();
saveSettings(store, off);
assert.equal(loadSettings(store).enabled.music, false);
const corrupt = fakeStorage({ "friday.glassStartPage.settings.v1": "{not json" });
assert.deepEqual(loadSettings(corrupt), DEFAULT_SETTINGS);

// To-dos: add trims and rejects blanks; toggle/remove/clear behave.
let todos = addTodo([], "  Book the call  ", "t1", 100);
assert.deepEqual(todos, [{ id: "t1", text: "Book the call", done: false, createdAt: 100 }]);
assert.equal(addTodo(todos, "   ", "t2", 101).length, 1);
todos = addTodo(todos, "Ship it", "t2", 102);
todos = toggleTodo(todos, "t1");
assert.equal(todos[0].done, true);
assert.equal(todos[1].done, false);
assert.equal(clearDoneTodos(todos).map((t) => t.id).join(","), "t2");
assert.equal(removeTodo(todos, "t2").length, 1);
assert.deepEqual(sanitizeTodos([{ id: "a", text: "x" }, { id: 1, text: "bad" }, "junk", null]), [
  { id: "a", text: "x", done: false, createdAt: 0 },
]);
assert.deepEqual(loadTodos(fakeStorage()), []);

// Search URLs encode and refuse blanks.
assert.equal(buildSearchUrl("friday universe"), "https://duckduckgo.com/?q=friday%20universe");
assert.equal(buildSearchUrl("a&b", "google"), "https://www.google.com/search?q=a%26b");
assert.equal(buildSearchUrl("   "), null);

// Map embed carries the coordinates it was given (Hyderabad).
const embed = buildMapEmbedUrl(17.385, 78.4867);
assert.ok(embed.startsWith("https://www.openstreetmap.org/export/embed.html?bbox="));
assert.ok(embed.includes("marker=17.38500%2C78.48670"));

// Weather labels: known codes labelled, unknown codes admitted.
assert.equal(weatherCodeLabel(0), "Clear sky");
assert.equal(weatherCodeLabel(63), "Rain");
assert.equal(weatherCodeLabel(1234), "Weather code 1234");

// Clock parts are zero-padded and derived from the injected date.
const parts = clockParts(new Date(2026, 10, 16, 7, 5));
assert.equal(parts.time, "07:05");
assert.ok(parts.day.includes("16"));

console.log("glassWidgets.test.ts: all assertions passed");
