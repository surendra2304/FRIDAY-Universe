"use client";

import { Orb } from "../Orb";
import type { VoicePhase } from "../VoiceCall";

/* ================================================================
   The Orb, summoned (TASK-IG2-WEB-03, wiring).

   The ULTRON orb component shipped unmounted — a voice face with
   nowhere to live. It lives here, as a summoned layer driven by the
   stage's REAL voice phase: the same phase the Halo breathes with,
   so the orb spins up when a call opens, listens when FRIDAY
   listens, and thinks when FRIDAY thinks.

   The Halo stays the stage's face — the live design is the owner's
   and does not change uninvited (the orb face itself remains one of
   the stored design candidates for his pick). This sheet is the
   orb's working surface in the meantime: present, honest about what
   drives it, and gone when the sheet sinks.
   ================================================================ */

const PHASE_LINES: Record<VoicePhase, string> = {
  resting: "At rest — start the voice line and the orb wakes with it.",
  opening: "Opening the voice line…",
  listening: "Listening — the orb is hearing the room.",
  thinking: "Thinking — the orb is working on it.",
  speaking: "Speaking — the orb is answering out loud.",
  down: "The voice line is down — the orb shows it as it is.",
};

export function OrbSheet({ phase }: { phase: VoicePhase }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 18,
        padding: "16px 0 8px",
      }}
    >
      <Orb phase={phase} size={320} />
      <p style={{ color: "var(--dim)", fontSize: 14, margin: 0, textAlign: "center" }}>{PHASE_LINES[phase]}</p>
    </div>
  );
}
