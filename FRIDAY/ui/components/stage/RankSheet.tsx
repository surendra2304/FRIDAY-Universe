"use client";

import { useEffect, useRef, useState } from "react";
import { RankBoard } from "../RankBoard";
import { fleetRankEntries, type FleetRankEntry } from "@/lib/fleetRank";
import { rankEntries } from "@/lib/ranking";
import { fetchFleet } from "@/lib/wire";

/* ================================================================
   The Response Board, summoned (TASK-IG2-WEB-02, wiring).

   The RankBoard component shipped unmounted — no page fed it data.
   This sheet is its caller: it ranks the fleet by MEASURED response
   latency from /api/agents/status (the same snapshot the rim lights
   breathe on), re-measures on the stage's own 20 s cadence, and
   carries each agent's previous rank forward so a climb or a fall
   shows in the movement column. Agents with no measured latency are
   not ranked — the board says how many, out loud, underneath.
   Read-only: this layer reports the fleet, it does not drive it.
   ================================================================ */

export function RankSheet() {
  const [entries, setEntries] = useState<readonly FleetRankEntry[]>([]);
  const [unmeasured, setUnmeasured] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [failed, setFailed] = useState(false);
  const previousRanks = useRef<ReadonlyMap<string, number>>(new Map());

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const snap = await fetchFleet();
        if (cancelled) return;
        const result = fleetRankEntries(snap.agents, previousRanks.current);
        previousRanks.current = new Map(
          rankEntries(result.entries, "asc").map((ranked) => [ranked.id, ranked.rank]),
        );
        setEntries(result.entries);
        setUnmeasured(result.unmeasured);
        setLoaded(true);
        setFailed(false);
      } catch {
        if (!cancelled) setFailed(true);
      }
    };
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  if (!loaded) {
    return (
      <p style={{ color: "var(--dim)", fontSize: 14, margin: "8px 0" }}>
        {failed
          ? "The fleet link is quiet — there is no measured board to show yet."
          : "Measuring the fleet…"}
      </p>
    );
  }

  return (
    <div>
      <RankBoard title="Fleet response — fastest first" scoreCaption="response time" entries={entries} order="asc" pageSize={10} />
      {unmeasured > 0 && (
        <p style={{ color: "var(--faint)", fontSize: 12.5, margin: "10px 2px 0" }}>
          {unmeasured} {unmeasured === 1 ? "agent has" : "agents have"} no measured response yet and{" "}
          {unmeasured === 1 ? "is" : "are"} not ranked — this board only ranks real measurements.
        </p>
      )}
      {failed && (
        <p style={{ color: "var(--faint)", fontSize: 12.5, margin: "6px 2px 0" }}>
          The latest re-measure failed; the board above is the last good snapshot.
        </p>
      )}
    </div>
  );
}
