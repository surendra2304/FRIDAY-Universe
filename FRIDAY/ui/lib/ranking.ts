/* TASK-IG2-WEB-02 — ranking engine for the FRIDAY website's leaderboard
   surfaces (ADAPT of the toprank pattern: a ranked board is only useful if
   the ranking itself is honest — explicit score, explicit movement, ties
   handled in the open).

   Pure functions, no React, no I/O: the board component below renders what
   this module computes, and the module is unit-testable on its own
   (lib/ranking.test.ts, run with plain `node`). */

export interface RankEntry {
  /** Stable identity across snapshots (agent id, strategy id, page slug…). */
  id: string;
  /** Display name. */
  name: string;
  /** The score being ranked by. Higher is better unless `order` says otherwise. */
  score: number;
  /** Optional human label for the score, e.g. "98.2% uptime" or "+$134.79". */
  scoreLabel?: string;
  /** Rank in the previous snapshot, 1-based, when known. */
  previousRank?: number;
}

export interface RankedEntry extends RankEntry {
  /** 1-based competition rank ("1224" style: tied scores share a rank). */
  rank: number;
  /** previousRank - rank when both are known: +n climbed, -n fell, 0 held. */
  movement: number | null;
  /** True when another entry shares this rank. */
  tied: boolean;
}

export type RankOrder = "desc" | "asc";

/**
 * Rank entries by score. Ties share a rank and the next rank skips
 * (competition ranking). Input order is preserved inside a tie so the
 * board is stable across re-renders. The input array is not mutated.
 */
export function rankEntries(entries: readonly RankEntry[], order: RankOrder = "desc"): RankedEntry[] {
  const sorted = [...entries].sort((a, b) => {
    const delta = order === "desc" ? b.score - a.score : a.score - b.score;
    return delta !== 0 ? delta : 0;
  });
  const ranked: RankedEntry[] = [];
  let lastScore: number | null = null;
  let lastRank = 0;
  sorted.forEach((entry, index) => {
    const rank = lastScore !== null && entry.score === lastScore ? lastRank : index + 1;
    lastScore = entry.score;
    lastRank = rank;
    ranked.push({
      ...entry,
      rank,
      movement: entry.previousRank != null ? entry.previousRank - rank : null,
      tied: false,
    });
  });
  const counts = new Map<number, number>();
  for (const entry of ranked) counts.set(entry.rank, (counts.get(entry.rank) ?? 0) + 1);
  for (const entry of ranked) entry.tied = (counts.get(entry.rank) ?? 0) > 1;
  return ranked;
}

/** Split a ranked board into podium (top `n`) and the rest — the board
    renders the podium with editorial emphasis, never a fake "top 3 cards"
    when fewer than `n` entries exist. */
export function splitPodium(ranked: readonly RankedEntry[], n = 3): { podium: RankedEntry[]; rest: RankedEntry[] } {
  return { podium: ranked.slice(0, n), rest: ranked.slice(n) };
}

/** One-line movement glyph + label for a ranked entry, e.g. "▲ 2", "▼ 1",
    "— held", "new". Kept here so every surface phrases movement the same way. */
export function movementLabel(entry: RankedEntry): string {
  if (entry.movement === null) return "new";
  if (entry.movement > 0) return `▲ ${entry.movement}`;
  if (entry.movement < 0) return `▼ ${-entry.movement}`;
  return "— held";
}
