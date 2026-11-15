"use client";

import { useEffect, useRef, useState } from "react";
import {
  ageLabel,
  clockTime,
  fetchTimeline,
  oneLine,
  openActivitySocket,
  toneFor,
  type ActivityFrame,
  type TimelineEvent,
} from "@/lib/wire";

/* ================================================================
   The chronicle, summoned — everything FRIDAY has been asked
   to do, newest first, from the unified task ledger
   (/api/tasks/timeline). While the sheet is open, the live
   activity socket adds lines as they happen; closing the sheet
   closes the socket. Read-only, like every layer here.
   ================================================================ */

interface LiveLine {
  id: number;
  agent: string;
  text: string;
  at: number;
}

export function ChronicleSheet() {
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [liveLines, setLiveLines] = useState<LiveLine[]>([]);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const snap = await fetchTimeline();
        if (!cancelled) setEvents(snap.events ?? []);
      } catch {
        if (!cancelled) setFailed(true);
      }
    })();
    const socket = openActivitySocket((frame: ActivityFrame) => {
      const text = oneLine(frame.directive || frame.action || frame.detail || frame.result || "", 130);
      if (!text) return;
      seq.current += 1;
      const line: LiveLine = { id: seq.current, agent: frame.agent || "fleet", text, at: Date.now() };
      setLiveLines((current) => [line, ...current].slice(0, 12));
    });
    return () => {
      cancelled = true;
      socket?.close();
    };
  }, []);

  return (
    <div className="chronicle">
      {liveLines.length > 0 && (
        <div className="chronicle-live" aria-label="Happening now">
          <p className="chronicle-live-head">
            <span className="live-dot" aria-hidden="true" /> Happening now
          </p>
          {liveLines.map((line) => (
            <p key={line.id} className="chronicle-live-line">
              <span className="chronicle-agent">{line.agent}</span> {line.text}
              <time className="chronicle-time">{clockTime(line.at)}</time>
            </p>
          ))}
        </div>
      )}

      {events === null && !failed && <p className="sheet-note">Reading the ledger…</p>}
      {failed && <p className="sheet-note">The ledger didn&apos;t answer — nothing here is guessed in its place.</p>}
      {events !== null && events.length === 0 && <p className="sheet-note">No delegations recorded yet.</p>}

      <ol className="chronicle-list">
        {(events ?? []).map((event, idx) => (
          <li key={event.task_id} className="chronicle-item" style={{ animationDelay: `${Math.min(idx, 12) * 45}ms` }}>
            <div className="chronicle-item-top">
              <span className="chronicle-agent">{event.owner_agent}</span>
              <span className={`pill tone-${toneFor(event.chip === "done" ? "COMPLETED" : event.chip === "failed" ? "FAILED" : event.chip)}`}>
                {event.chip}
              </span>
              <time className="chronicle-time">{ageLabel(event.updated_at) || clockTime(event.updated_at)}</time>
            </div>
            <p className="chronicle-text">{oneLine(event.description, 220)}</p>
            {event.result && <p className="chronicle-result">{oneLine(event.result, 220)}</p>}
            {event.error && <p className="chronicle-result is-error">{oneLine(event.error, 220)}</p>}
          </li>
        ))}
      </ol>
    </div>
  );
}
