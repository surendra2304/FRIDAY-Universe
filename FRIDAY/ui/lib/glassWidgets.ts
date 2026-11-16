/* TASK-IG2-WEB-07 — state/logic core for the glass start-page
   (components/GlassStartPage.tsx), adapted from the GNTD pattern
   (GNTD: Glass New Tab Dashboard, a free Chrome new-tab extension
   surfaced by IG sweep crew-13, shortcode DX7B57RM491): a browser
   start page of glass panels over a custom background, where every
   widget can be toggled on or off and the choices persist.

   Pure functions, no React, no DOM: the component renders what this
   module computes, storage is injected so the module is unit-testable
   with plain `node` (lib/glassWidgets.test.ts), and every external
   value (weather codes, map/search URLs) is built here so the
   component never invents data — a failed lookup stays a visible
   failure in the widget, not a plausible-looking number. */

export type WidgetId = "search" | "todo" | "weather" | "music" | "notes" | "map";

export interface WidgetInfo {
  id: WidgetId;
  title: string;
  blurb: string;
}

export const WIDGET_CATALOGUE: readonly WidgetInfo[] = [
  { id: "search", title: "Search", blurb: "One box out to the web." },
  { id: "todo", title: "To-do", blurb: "Today's list, kept on this device." },
  { id: "weather", title: "Weather", blurb: "Live conditions for your city (Open-Meteo, free, no key)." },
  { id: "music", title: "Music", blurb: "A stream player — preset or any audio URL you paste." },
  { id: "notes", title: "Notes", blurb: "A scratch pad, kept on this device." },
  { id: "map", title: "Map", blurb: "OpenStreetMap — search a place, see it." },
];

export const WIDGET_IDS: readonly WidgetId[] = WIDGET_CATALOGUE.map((w) => w.id);

export type BackgroundKind = "gradient" | "image";

export interface StartPageSettings {
  /** Which widgets are on the page. Every catalogue id is present. */
  enabled: Record<WidgetId, boolean>;
  background: { kind: BackgroundKind; value: string };
  /** City the weather + map widgets centre on until the user searches. */
  city: string;
}

export interface GradientPreset {
  id: string;
  label: string;
  css: string;
}

/** Built-in backgrounds: pure CSS, no image fetch, always available. */
export const GRADIENT_PRESETS: readonly GradientPreset[] = [
  {
    id: "halo-night",
    label: "Halo night",
    css: "radial-gradient(120% 90% at 20% 0%, #16224d 0%, #080b16 55%, #030409 100%)",
  },
  {
    id: "monsoon",
    label: "Monsoon",
    css: "linear-gradient(160deg, #0b3b39 0%, #0a2540 55%, #030409 100%)",
  },
  {
    id: "ember",
    label: "Ember",
    css: "linear-gradient(150deg, #3d1430 0%, #571f16 55%, #0a0605 100%)",
  },
];

export const DEFAULT_SETTINGS: StartPageSettings = {
  enabled: { search: true, todo: true, weather: true, music: true, notes: true, map: true },
  background: { kind: "gradient", value: GRADIENT_PRESETS[0].css },
  city: "Hyderabad",
};

export const SETTINGS_KEY = "friday.glassStartPage.settings.v1";
export const TODOS_KEY = "friday.glassStartPage.todos.v1";
export const NOTES_KEY = "friday.glassStartPage.notes.v1";

/** Minimal storage surface (localStorage satisfies it; tests inject a fake). */
export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function isWidgetId(value: unknown): value is WidgetId {
  return typeof value === "string" && (WIDGET_IDS as readonly string[]).includes(value);
}

/**
 * Defensively rebuild settings from untrusted parsed JSON (an old or
 * hand-edited localStorage value must never crash the page or enable a
 * widget id that does not exist). Unknown keys are dropped; missing
 * widgets default to on; a non-string city/background falls back.
 */
export function sanitizeSettings(raw: unknown): StartPageSettings {
  const out: StartPageSettings = {
    enabled: { ...DEFAULT_SETTINGS.enabled },
    background: { ...DEFAULT_SETTINGS.background },
    city: DEFAULT_SETTINGS.city,
  };
  if (typeof raw !== "object" || raw === null) return out;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.enabled === "object" && obj.enabled !== null) {
    const enabled = obj.enabled as Record<string, unknown>;
    for (const id of WIDGET_IDS) {
      if (typeof enabled[id] === "boolean") out.enabled[id] = enabled[id] as boolean;
    }
  }
  if (typeof obj.background === "object" && obj.background !== null) {
    const bg = obj.background as Record<string, unknown>;
    if ((bg.kind === "gradient" || bg.kind === "image") && typeof bg.value === "string" && bg.value.trim()) {
      out.background = { kind: bg.kind, value: bg.value };
    }
  }
  if (typeof obj.city === "string" && obj.city.trim()) out.city = obj.city.trim();
  return out;
}

/** Immutable toggle: returns a new settings object, input untouched. */
export function toggleWidget(settings: StartPageSettings, id: WidgetId): StartPageSettings {
  return { ...settings, enabled: { ...settings.enabled, [id]: !settings.enabled[id] } };
}

export function enabledWidgets(settings: StartPageSettings): WidgetInfo[] {
  return WIDGET_CATALOGUE.filter((w) => settings.enabled[w.id]);
}

export function loadSettings(storage: StorageLike): StartPageSettings {
  try {
    const raw = storage.getItem(SETTINGS_KEY);
    if (!raw) return sanitizeSettings(null);
    return sanitizeSettings(JSON.parse(raw));
  } catch {
    return sanitizeSettings(null);
  }
}

export function saveSettings(storage: StorageLike, settings: StartPageSettings): void {
  try {
    storage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    /* Storage full/blocked: the page still works for this session. */
  }
}

/* ---------------- To-do ---------------- */

export interface TodoItem {
  id: string;
  text: string;
  done: boolean;
  createdAt: number;
}

/** Append a trimmed, non-empty item. Blank text returns the list unchanged. */
export function addTodo(items: readonly TodoItem[], text: string, id: string, now: number): TodoItem[] {
  const clean = text.trim();
  if (!clean) return [...items];
  return [...items, { id, text: clean, done: false, createdAt: now }];
}

export function toggleTodo(items: readonly TodoItem[], id: string): TodoItem[] {
  return items.map((item) => (item.id === id ? { ...item, done: !item.done } : item));
}

export function removeTodo(items: readonly TodoItem[], id: string): TodoItem[] {
  return items.filter((item) => item.id !== id);
}

export function clearDoneTodos(items: readonly TodoItem[]): TodoItem[] {
  return items.filter((item) => !item.done);
}

export function sanitizeTodos(raw: unknown): TodoItem[] {
  if (!Array.isArray(raw)) return [];
  const out: TodoItem[] = [];
  for (const entry of raw) {
    if (typeof entry !== "object" || entry === null) continue;
    const item = entry as Record<string, unknown>;
    if (typeof item.id === "string" && typeof item.text === "string" && item.text.trim()) {
      out.push({
        id: item.id,
        text: item.text,
        done: item.done === true,
        createdAt: typeof item.createdAt === "number" ? item.createdAt : 0,
      });
    }
  }
  return out;
}

export function loadTodos(storage: StorageLike): TodoItem[] {
  try {
    const raw = storage.getItem(TODOS_KEY);
    return raw ? sanitizeTodos(JSON.parse(raw)) : [];
  } catch {
    return [];
  }
}

export function saveTodos(storage: StorageLike, items: readonly TodoItem[]): void {
  try {
    storage.setItem(TODOS_KEY, JSON.stringify(items));
  } catch {
    /* See saveSettings. */
  }
}

export function loadNotes(storage: StorageLike): string {
  try {
    return storage.getItem(NOTES_KEY) ?? "";
  } catch {
    return "";
  }
}

export function saveNotes(storage: StorageLike, notes: string): void {
  try {
    storage.setItem(NOTES_KEY, notes);
  } catch {
    /* See saveSettings. */
  }
}

/* ---------------- Outbound URLs ---------------- */

export type SearchEngine = "duckduckgo" | "google";

/** Search URL for a query, or null for a blank query (never search ""). */
export function buildSearchUrl(query: string, engine: SearchEngine = "duckduckgo"): string | null {
  const clean = query.trim();
  if (!clean) return null;
  const q = encodeURIComponent(clean);
  return engine === "google" ? `https://www.google.com/search?q=${q}` : `https://duckduckgo.com/?q=${q}`;
}

/** OpenStreetMap embed URL centred on real coordinates (from a geocode hit). */
export function buildMapEmbedUrl(lat: number, lon: number, span = 0.05): string {
  const bbox = [lon - span, lat - span / 2, lon + span, lat + span / 2].map((n) => n.toFixed(5)).join("%2C");
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${lat.toFixed(5)}%2C${lon.toFixed(5)}`;
}

export function buildMapSearchUrl(query: string): string | null {
  const clean = query.trim();
  if (!clean) return null;
  return `https://www.openstreetmap.org/search?query=${encodeURIComponent(clean)}`;
}

/* ---------------- Weather (Open-Meteo WMO codes) ---------------- */

const WMO_LABELS: Record<number, string> = {
  0: "Clear sky",
  1: "Mainly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  48: "Rime fog",
  51: "Light drizzle",
  53: "Drizzle",
  55: "Dense drizzle",
  61: "Light rain",
  63: "Rain",
  65: "Heavy rain",
  71: "Light snow",
  73: "Snow",
  75: "Heavy snow",
  80: "Light showers",
  81: "Showers",
  82: "Violent showers",
  95: "Thunderstorm",
  96: "Thunderstorm with hail",
  99: "Thunderstorm with hail",
};

/** Label for an Open-Meteo WMO weather code; unknown codes say so. */
export function weatherCodeLabel(code: number): string {
  return WMO_LABELS[code] ?? `Weather code ${code}`;
}

/* ---------------- Clock ---------------- */

/** "07:42" + "Mon 16 Nov" style parts, computed from an injected Date. */
export function clockParts(date: Date): { time: string; day: string } {
  const pad = (n: number) => String(n).padStart(2, "0");
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const day = date.toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
  return { time, day };
}

export { isWidgetId };
