"use client";

import { useSyncExternalStore } from "react";
import { Stage } from "./stage/Stage";
import { UltronStage } from "./ultron/UltronStage";
import { DEFAULT_THEME, getThemeSnapshot, subscribeTheme } from "@/lib/theme";

/* ================================================================
   ThemeRoot (TASK-WEB-003) — the one place the stage's theme is
   chosen.

   Default: ULTRON, the theme the owner picked on 2026-11-17.
   Halo — the previous theme — is preserved aside intact at his
   instruction: its stage, sheets, halo and stylesheet are
   unmodified, and it renders exactly as before when selected
   (?theme=halo, or the persisted preference, set from the ULTRON
   control panel's "Switch to Halo theme" control). He will say
   later what happens to it; until then both themes are live.

   The choice is read through useSyncExternalStore with the
   server snapshot pinned to the default, so the static export
   and the first client render agree (the same pattern the wake
   word preference uses in the Halo stage).
   ================================================================ */

export function ThemeRoot() {
  const theme = useSyncExternalStore(subscribeTheme, getThemeSnapshot, () => DEFAULT_THEME);
  return theme === "halo" ? <Stage /> : <UltronStage />;
}
