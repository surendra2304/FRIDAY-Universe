"use client";

import { Activity, CheckCircle2, Clock3, Waypoints, Zap } from "lucide-react";
import {
  AutonomySnapshot,
  LiveActivityEvent,
  TaskTimelineSnapshot,
  cleanDirective,
  istTime,
} from "@/lib/api";

/* ============================================================
   The Record — everything the crew has done, in the open.

   Two ledgers, both fed by real data only:
   - "As it happens": the live activity socket's events merged
     with the autonomy ledger's recent actions, de-duplicated
     and newest-first.
   - "Work you've handed out": the unified delegation timeline
     with its status counts — every dispatch FRIDAY has made on
     the owner's behalf, with the outcome it came back with.
   ============================================================ */

export function LiveLedger({
  autonomy,
  liveActivity,
}: {
  autonomy: AutonomySnapshot | null;
  liveActivity: Record<string, LiveActivityEvent>;
}) {
  const rows: Array<{ agent: string; directive: string; result: string; success: boolean; at: string }> = [];

  for (const [key, event] of Object.entries(liveActivity)) {
    rows.push({
      agent: event.agent || key,
      directive: cleanDirective(event.directive || `${event.action ?? "activity"} ${event.target ?? ""}`.trim()),
      result: cleanDirective(event.result, 140),
      success: Boolean(event.success),
      at: event.timestamp ?? "",
    });
  }
  for (const action of autonomy?.recent_actions ?? []) {
    rows.push({
      agent: action.target || action.action_type || "system",
      directive: cleanDirective(action.directive || action.action_type || "action"),
      result: cleanDirective(action.result, 140),
      success: action.success !== false,
      at: action.recorded_at ?? action.timestamp ?? "",
    });
  }
  const seen = new Set<string>();
  const unique = rows
    .filter((r) => {
      const k = `${r.agent}|${r.directive}|${r.at}`;
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    })
    .sort((a, b) => new Date(b.at || 0).getTime() - new Date(a.at || 0).getTime())
    .slice(0, 14);

  if (unique.length === 0) {
    return (
      <div className="blank">
        <Zap size={20} />
        <p>Quiet so far. The moment anyone in the crew moves, it is written here — live.</p>
      </div>
    );
  }

  return (
    <div className="ledger">
      {unique.map((row, i) => (
        <div className="ledger-row" key={`${row.agent}-${row.at}-${i}`} style={{ animationDelay: `${Math.min(i * 40, 240)}ms` }}>
          <span className={`ledger-mark ${row.success ? "ok" : "err"}`}>
            {row.success ? <CheckCircle2 size={14} /> : <Activity size={14} />}
          </span>
          <div className="ledger-body">
            <span className="ledger-agent">{row.agent}</span>
            <p className="ledger-text">{row.directive}</p>
            {row.result && <p className="ledger-result">{row.result}</p>}
          </div>
          <span className="ledger-time">{row.at ? `${istTime(row.at)} IST` : "live"}</span>
        </div>
      ))}
    </div>
  );
}

export function DelegationLedger({ timeline }: { timeline: TaskTimelineSnapshot | null }) {
  if (!timeline) {
    return (
      <div className="ledger" aria-hidden="true">
        {Array.from({ length: 3 }).map((_, i) => (
          <div className="skel-row" key={i}>
            <div className="skel-line w40" />
            <div className="skel-line w80" />
          </div>
        ))}
      </div>
    );
  }
  if (timeline.events.length === 0) {
    return (
      <div className="blank">
        <Waypoints size={20} />
        <p>
          Nothing handed out yet. Give FRIDAY a job in the conversation — every dispatch is written here with the
          answer it brought back.
        </p>
      </div>
    );
  }
  const counts = timeline.chip_counts ?? {};
  return (
    <div className="ledger">
      <div className="ledger-counts">
        <span className="tag tag-queued">waiting {counts.queued ?? 0}</span>
        <span className="tag tag-running">running {counts.running ?? 0}</span>
        <span className="tag tag-done">done {counts.done ?? 0}</span>
        <span className="tag tag-failed">failed {counts.failed ?? 0}</span>
      </div>
      {timeline.events.map((ev, i) => (
        <div className="ledger-row" key={ev.task_id || i} style={{ animationDelay: `${Math.min(i * 30, 180)}ms` }}>
          <span className={`ledger-mark ${ev.chip === "failed" ? "err" : ev.chip === "done" ? "ok" : "wait"}`}>
            {ev.chip === "done" ? <CheckCircle2 size={14} /> : ev.chip === "failed" ? <Activity size={14} /> : <Clock3 size={14} />}
          </span>
          <div className="ledger-body">
            <span className="ledger-agent">{ev.owner_agent || "unassigned"}</span>
            <p className="ledger-text">
              <span className={`tag tag-${ev.chip}`}>{ev.chip}</span> {cleanDirective(ev.description, 120)}
            </p>
            {ev.error ? (
              <p className="ledger-result bad">{cleanDirective(ev.error, 140)}</p>
            ) : ev.result ? (
              <p className="ledger-result">{cleanDirective(ev.result, 140)}</p>
            ) : null}
          </div>
          <span className="ledger-time">{istTime(ev.updated_at)} IST</span>
        </div>
      ))}
    </div>
  );
}
