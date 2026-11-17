/* Theme selection for the FRIDAY stage — TASK-WEB-003 (2026-11-17).
 *
 * Two themes ship in this app:
 *   "ultron" — the command-dashboard theme the owner picked on
 *              2026-11-17 (components/ultron/UltronStage.tsx). DEFAULT.
 *   "halo"   — the previous theme (components/stage/Stage.tsx), kept
 *              aside intact at the owner's instruction; he will say
 *              later what happens to it. It is NOT deleted, stubbed
 *              or restyled: selecting it renders the original stage
 *              exactly as it shipped under TASK-WEB-002.
 *
 * Pure and import-free, in the style of lib/wakeWord.ts: the resolver
 * is testable with plain Node (lib/theme.test.ts) and nothing touches
 * the DOM except through the storage/window guards noted per function.
 *
 * Resolution order (first hit wins):
 *   1. the ?theme= query parameter (a link can carry the choice)
 *   2. the persisted preference (localStorage "friday.theme")
 *   3. the default, "ultron"
 * An unrecognised value never resolves — it falls through to the next
 * source, so a typo'd link still lands on the default theme. */

export type ThemeName = "ultron" | "halo";

export const THEMES: readonly ThemeName[] = ["ultron", "halo"];

export const DEFAULT_THEME: ThemeName = "ultron";

export const THEME_STORAGE_KEY = "friday.theme";

/** The value as a ThemeName, or null when it names no shipped theme. */
export function parseTheme(value?: string | null): ThemeName | null {
  if (!value) return null;
  const v = value.trim().toLowerCase();
  return (THEMES as readonly string[]).includes(v) ? (v as ThemeName) : null;
}

/** Resolve the active theme from the two explicit sources. */
export function resolveTheme(queryValue?: string | null, storedValue?: string | null): ThemeName {
  return parseTheme(queryValue) ?? parseTheme(storedValue) ?? DEFAULT_THEME;
}

/* — The persisted preference ————————————————————————————————————————
   Read through useSyncExternalStore in components/ThemeRoot.tsx:
   getThemeSnapshot is the snapshot, subscribeTheme the subscription,
   and setThemePref the only writer (it persists, then notifies). */

export interface ThemeStorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function loadThemePref(storage: ThemeStorageLike): ThemeName | null {
  try {
    return parseTheme(storage.getItem(THEME_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function saveThemePref(storage: ThemeStorageLike, theme: ThemeName): void {
  try {
    storage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    /* private mode / storage disabled — the preference simply won't persist */
  }
}

let themeListeners: Array<() => void> = [];

export function subscribeTheme(callback: () => void): () => void {
  themeListeners = [...themeListeners, callback];
  return () => {
    themeListeners = themeListeners.filter((l) => l !== callback);
  };
}

export function getThemeSnapshot(): ThemeName {
  if (typeof window === "undefined") return DEFAULT_THEME;
  const query = new URLSearchParams(window.location.search).get("theme");
  return resolveTheme(query, loadThemePref(window.localStorage));
}

export function setThemePref(theme: ThemeName): void {
  if (typeof window !== "undefined") saveThemePref(window.localStorage, theme);
  for (const listener of themeListeners) listener();
}
