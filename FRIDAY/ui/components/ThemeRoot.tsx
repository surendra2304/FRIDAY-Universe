"use client";

import { UltronStage } from "./ultron/UltronStage";

/* ================================================================
   ThemeRoot (TASK-WEB-003, amended 2026-11-17) — the stage root.

   ULTRON is the only theme. The owner picked it on 2026-11-17 and
   clarified the same day that the previous theme, Halo, was to be
   kept aside in workspace storage — not kept selectable in the
   live site. The theme switch that originally shipped here is
   removed: this root renders the ULTRON stage unconditionally.
   ================================================================ */

export function ThemeRoot() {
  return <UltronStage />;
}
