"use client";

/* TASK-IG2-WEB-02 — RankBoard: the leaderboard/ranking pattern for the
   FRIDAY website, adapted from the toprank spec card (nowork-studio's
   ranking-audit plugin, MIT).

   The transferable pattern from toprank is a board whose ranks are earned
   from a measured score and re-audited on a cadence — never a static list
   someone typed once. This component is that pattern as a website surface:
   it takes scored entries (agent uptime, strategy forward score, page
   health — whatever the caller measured), ranks them with the honest
   competition ranking in lib/ranking.ts, and shows movement against the
   previous snapshot so a climb or a fall is visible at a glance.

   Optional component: it is NOT mounted on the live stage and changes no
   existing surface. A caller mounts it inside a sheet or page and feeds it
   measured entries; with no entries it renders an explicit empty state
   rather than inventing a board. Styles are inline and read the Halo CSS
   variables from app/globals.css, so the component carries no stylesheet
   of its own and cannot disturb the live design. */

import { useMemo, useState } from "react";
import {
  movementLabel,
  rankEntries,
  type RankEntry,
  type RankOrder,
} from "@/lib/ranking";

export interface RankBoardProps {
  /** Board heading, e.g. "Fleet reliability — last 7 days". */
  title: string;
  /** What the score is, e.g. "uptime %". Shown in the header so the rank is never unexplained. */
  scoreCaption: string;
  /** Measured entries. previousRank, when supplied, drives the movement column. */
  entries: readonly RankEntry[];
  order?: RankOrder;
  /** How many rows to show before "show all". Default 10. */
  pageSize?: number;
}

const mono = "var(--font-mono)";
const display = "var(--font-display)";

function movementColor(movement: number | null): string {
  if (movement === null) return "var(--faint)";
  if (movement > 0) return "var(--good)";
  if (movement < 0) return "var(--bad)";
  return "var(--dim)";
}

export function RankBoard({ title, scoreCaption, entries, order = "desc", pageSize = 10 }: RankBoardProps) {
  const [expanded, setExpanded] = useState(false);
  const ranked = useMemo(() => rankEntries(entries, order), [entries, order]);
  const visible = expanded ? ranked : ranked.slice(0, pageSize);

  return (
    <section
      aria-label={title}
      style={{
        background: "var(--sheet)",
        border: "1px solid var(--hair)",
        borderRadius: 12,
        padding: "18px 20px",
        color: "var(--ink)",
        fontFamily: "var(--font-body)",
      }}
    >
      <header
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "baseline",
          gap: 16,
          marginBottom: 12,
        }}
      >
        <h2 style={{ fontFamily: display, fontSize: 17, fontWeight: 600, margin: 0 }}>{title}</h2>
        <span style={{ fontFamily: mono, fontSize: 11, color: "var(--faint)", letterSpacing: "0.08em" }}>
          RANKED BY {scoreCaption.toUpperCase()}
        </span>
      </header>

      {ranked.length === 0 ? (
        <p style={{ color: "var(--dim)", fontSize: 14, margin: "8px 0" }}>
          No measured entries yet — this board only ranks real measurements.
        </p>
      ) : (
        <>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
            <thead>
              <tr style={{ color: "var(--faint)", fontFamily: mono, fontSize: 11, letterSpacing: "0.08em" }}>
                <th scope="col" style={{ textAlign: "left", padding: "6px 8px", fontWeight: 500 }}>RANK</th>
                <th scope="col" style={{ textAlign: "left", padding: "6px 8px", fontWeight: 500 }}>NAME</th>
                <th scope="col" style={{ textAlign: "right", padding: "6px 8px", fontWeight: 500 }}>
                  {scoreCaption.toUpperCase()}
                </th>
                <th scope="col" style={{ textAlign: "right", padding: "6px 8px", fontWeight: 500 }}>MOVE</th>
              </tr>
            </thead>
            <tbody>
              {visible.map((entry) => (
                <tr
                  key={entry.id}
                  style={{
                    borderTop: "1px solid var(--hair-soft)",
                    background: entry.rank === 1 ? "rgba(99, 102, 241, 0.10)" : "transparent",
                  }}
                >
                  <td
                    style={{
                      padding: "8px",
                      fontFamily: mono,
                      fontWeight: entry.rank <= 3 ? 600 : 400,
                      color: entry.rank === 1 ? "var(--ink)" : "var(--dim)",
                    }}
                  >
                    {entry.rank}
                    {entry.tied ? " =" : ""}
                  </td>
                  <td style={{ padding: "8px", fontWeight: entry.rank <= 3 ? 600 : 400 }}>{entry.name}</td>
                  <td style={{ padding: "8px", textAlign: "right", fontFamily: mono }}>
                    {entry.scoreLabel ?? entry.score}
                  </td>
                  <td
                    style={{
                      padding: "8px",
                      textAlign: "right",
                      fontFamily: mono,
                      color: movementColor(entry.movement),
                    }}
                  >
                    {movementLabel(entry)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {ranked.length > pageSize && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              style={{
                marginTop: 12,
                background: "none",
                border: "1px solid var(--hair)",
                borderRadius: 8,
                color: "var(--dim)",
                fontFamily: mono,
                fontSize: 12,
                padding: "6px 12px",
                cursor: "pointer",
              }}
            >
              {expanded ? "SHOW FEWER" : `SHOW ALL ${ranked.length}`}
            </button>
          )}
        </>
      )}
    </section>
  );
}
