"use client";

import {
  Activity,
  ArrowUpRight,
  BarChart2,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Eye,
  Gauge,
  Globe2,
  HardDrive,
  Layers,
  LineChart,
  MessageSquareText,
  Network,
  ShieldCheck,
  Terminal,
  TrendingUp,
  Waypoints,
  Wifi,
  Zap,
} from "lucide-react";
import { useId } from "react";
import {
  Agent,
  AutonomySnapshot,
  FleetSnapshot,
  HostTelemetry,
  LiveActivityEvent,
  AgentsLiveSnapshot,
  TaskTimelineSnapshot,
  cleanDirective,
  freshness,
  istTime,
  statusTone,
} from "@/lib/api";
import { CountUp, Reveal } from "./effects";

/* ============================================================
   Fleet constellation, activity feed and system instruments.
   Owner directives honored here (2026-11-11 IST):
   - no raw "owner-approved FRIDAY Universe task" boilerplate —
     cards show the human intent, cleaned;
   - every agent shows WHEN it last did something (freshness),
     so stale data can't masquerade as live work;
   - timestamps are IST, the single project clock.

   Reactor Deck edition (2026-11-14, rebuild #2): the fleet is
   a horizontal CONSTELLATION RAIL of agent nodes (orb + status
   ring) the owner flicks through and taps to ask/assign; the
   system readouts are machine-room instruments. All data
   wiring below is unchanged from the Aurora edition.
   ============================================================ */

const AGENT_ORDER = ["stratex", "inference", "cortex", "forge", "intelx", "vyralx", "memora", "futuris", "sentinel"] as const;

const AGENT_ICONS: Record<string, React.ReactNode> = {
  stratex: <TrendingUp size={17} />,
  inference: <Network size={17} />,
  cortex: <Database size={17} />,
  forge: <Terminal size={17} />,
  intelx: <Eye size={17} />,
  vyralx: <Layers size={17} />,
  memora: <HardDrive size={17} />,
  futuris: <LineChart size={17} />,
  sentinel: <ShieldCheck size={17} />,
};

const ROLE_LABELS: Record<string, string> = {
  stratex: "Algorithmic trading",
  inference: "AI gateway",
  cortex: "Web operations",
  forge: "Software engineering",
  intelx: "Macro research",
  vyralx: "Video production",
  memora: "Persistent memory",
  futuris: "Forecasting",
  sentinel: "Cyber defense",
};

export function Sparkline({ values, color, width = 130, height = 38 }: { values: number[]; color: string; width?: number; height?: number }) {
  const gid = useId().replace(/[^a-zA-Z0-9]/g, "");
  if (values.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${100 - ((v - min) / span) * 90}`);
  const d = `M${pts.join(" L")}`;
  const area = `${d} L100,100 L0,100 Z`;
  const last = pts[pts.length - 1].split(",");
  return (
    <svg width={width} height={height} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id={`spark-${gid}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.35" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#spark-${gid})`} stroke="none" />
      <path d={d} fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r={3} fill={color} />
    </svg>
  );
}

/** Shimmer placeholders while the first fleet probe is in flight. */
function FleetSkeleton() {
  return (
    <div className="constellation" aria-hidden="true">
      {Array.from({ length: 6 }).map((_, i) => (
        <div className="skel-node" key={i} style={{ animationDelay: `${i * 90}ms` }}>
          <div className="skel-line w40" />
          <div className="skel-line w70" />
          <div className="skel-line w55" />
          <div className="skel-line w80" />
        </div>
      ))}
    </div>
  );
}

export function FleetGrid({
  fleet,
  autonomy,
  liveActivity,
  now,
  onAsk,
}: {
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
  liveActivity: Record<string, LiveActivityEvent>;
  now?: AgentsLiveSnapshot | null;
  onAsk: (agent: Agent) => void;
}) {
  const agents = fleet?.agents ?? [];
  const nowById = new Map((now?.agents ?? []).map((a) => [a.id, a] as const));
  const sorted = [...agents].sort((a, b) => {
    const ai = AGENT_ORDER.indexOf(a.id as (typeof AGENT_ORDER)[number]);
    const bi = AGENT_ORDER.indexOf(b.id as (typeof AGENT_ORDER)[number]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  if (!fleet) {
    return <FleetSkeleton />;
  }

  if (sorted.length === 0) {
    return (
      <div className="deck-empty">
        <Globe2 size={22} style={{ marginBottom: 8 }} />
        The fleet has not reported yet. The status probe refreshes every 30 seconds.
      </div>
    );
  }

  return (
    <div className="constellation">
      {sorted.map((agent, index) => {
        const live = liveActivity[agent.id];
        const ledger = nowById.get(agent.id);
        const working = ledger?.in_flight
          ? {
              task_id: ledger.in_flight.task_id,
              description: cleanDirective(ledger.in_flight.description, 120),
              status: ledger.in_flight.status,
              at: ledger.in_flight.since,
            }
          : null;
        const record = live
          ? {
              directive: cleanDirective(live.directive || `${live.action ?? "activity"} ${live.target ?? ""}`.trim()),
              result: cleanDirective(live.result, 120),
              success: Boolean(live.success),
              at: live.timestamp,
            }
          : (() => {
              const a = autonomy?.agent_activity?.[agent.id];
              if (!a) return null;
              return {
                directive: cleanDirective(a.directive),
                result: cleanDirective(a.result, 120),
                success: Boolean(a.success),
                at: a.recorded_at ?? a.timestamp,
              };
            })();
        const isActive = autonomy?.active_agent?.toLowerCase() === agent.id || Boolean(working);
        const tone = statusTone(agent.status);
        return (
          <Reveal key={agent.id} delay={Math.min(index * 60, 360)} as="article" className="node-cell">
            <div className={`agent-node tone-${tone}${isActive ? " active" : ""}`}>
              <div className="node-top">
                <div className={`node-orb tone-${tone}`}>{AGENT_ICONS[agent.id] ?? <Database size={17} />}</div>
                <span className={`status-pill ${tone}`}>{agent.status.toLowerCase()}</span>
              </div>
              <div className="node-name">
                {agent.name}
                {isActive && <span className="dot good pulse" aria-label="active" />}
              </div>
              <div className="node-role">{ROLE_LABELS[agent.id] ?? agent.role ?? "Specialist agent"}</div>
              <div className="node-meta">
                <span>{typeof agent.latency_ms === "number" ? `${Math.round(agent.latency_ms)} ms` : "latency n/a"}</span>
                <span>
                  {working
                    ? `working ${freshness(working.at) || working.status}`
                    : record?.at
                      ? freshness(record.at)
                        ? `active ${freshness(record.at)}`
                        : "active"
                      : `probe ${freshness(agent.last_checked) || "pending"}`}
                </span>
              </div>
              {working && (
                <div className="node-work working">
                  <strong>Working now:</strong> {working.description}
                  <span className="work-bar" aria-hidden="true" />
                </div>
              )}
              <div className="node-work">
                {record?.directive ? (
                  <>
                    <strong>Last work:</strong> {record.directive}
                  </>
                ) : working ? (
                  <>
                    {working.task_id} — {working.status}
                  </>
                ) : (
                  <>Idle — awaiting your directive</>
                )}
              </div>
              {record?.result && (
                <div className={`agent-result ${record.success ? "good" : "bad"}`}>
                  {record.success ? (
                    <CheckCircle2 size={13} style={{ flex: "none", marginTop: 2 }} />
                  ) : (
                    <Activity size={13} style={{ flex: "none", marginTop: 2 }} />
                  )}
                  <span>{record.result}</span>
                </div>
              )}
              <div className="node-actions">
                <button className="mini-btn" onClick={() => onAsk(agent)}>
                  <MessageSquareText size={13} /> Assign / ask
                </button>
                <a
                  className="mini-btn"
                  href={`https://friday-universe.duckdns.org/${agent.id}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open site <ArrowUpRight size={12} />
                </a>
              </div>
            </div>
          </Reveal>
        );
      })}
    </div>
  );
}

/** Checklist D13: delegation history with status chips — newest first. */
export function TaskTimeline({ timeline }: { timeline: TaskTimelineSnapshot | null }) {
  if (!timeline) {
    return (
      <div className="ledger" aria-hidden="true">
        <div className="feed-list">
          {Array.from({ length: 3 }).map((_, i) => (
            <div className="skel-row" key={i}>
              <div className="skel-line w40" />
              <div className="skel-line w80" />
            </div>
          ))}
        </div>
      </div>
    );
  }
  if (timeline.events.length === 0) {
    return (
      <div className="deck-empty">
        <Waypoints size={20} style={{ marginBottom: 8 }} />
        No delegated tasks yet. Assign work from the conversation — every dispatch lands here with its status.
      </div>
    );
  }
  const counts = timeline.chip_counts ?? {};
  return (
    <div className="ledger">
      <div className="feed-list">
        <div className="tl-chips">
          <span className="chip chip-queued">queued {counts.queued ?? 0}</span>
          <span className="chip chip-running">running {counts.running ?? 0}</span>
          <span className="chip chip-done">done {counts.done ?? 0}</span>
          <span className="chip chip-failed">failed {counts.failed ?? 0}</span>
        </div>
        {timeline.events.map((ev, i) => (
          <div className="feed-row" key={ev.task_id || i} style={{ animationDelay: `${Math.min(i * 30, 180)}ms` }}>
            <div className={`feed-icon ${ev.chip === "failed" ? "err" : ev.chip === "done" ? "ok" : "muted-icon"}`}>
              {ev.chip === "done" ? <CheckCircle2 size={14} /> : ev.chip === "failed" ? <Activity size={14} /> : <Clock3 size={14} />}
            </div>
            <div className="feed-body">
              <span className="feed-agent">{ev.owner_agent || "unassigned"}</span>
              <p className="feed-text" style={{ margin: "3px 0" }}>
                <span className={`chip chip-${ev.chip}`}>{ev.chip}</span> {cleanDirective(ev.description, 120)}
              </p>
              {ev.error ? (
                <p className="feed-result" style={{ margin: 0, color: "var(--bad)" }}>
                  {cleanDirective(ev.error, 140)}
                </p>
              ) : ev.result ? (
                <p className="feed-result" style={{ margin: 0 }}>
                  {cleanDirective(ev.result, 140)}
                </p>
              ) : null}
            </div>
            <span className="feed-time" title="IST">
              {istTime(ev.updated_at)} IST
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function ActivityFeed({
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
      <div className="deck-empty">
        <Zap size={20} style={{ marginBottom: 8 }} />
        All agents standing by. The moment one acts — yours to see here, live.
      </div>
    );
  }

  return (
    <div className="ledger">
      <div className="feed-list">
        {unique.map((row, i) => (
          <div className="feed-row" key={`${row.agent}-${row.at}-${i}`} style={{ animationDelay: `${Math.min(i * 40, 240)}ms` }}>
            <div className={`feed-icon ${row.success ? "ok" : "err"}`}>
              {row.success ? <CheckCircle2 size={14} /> : <Activity size={14} />}
            </div>
            <div className="feed-body">
              <span className="feed-agent">{row.agent}</span>
              <p className="feed-text" style={{ margin: "3px 0" }}>
                {row.directive}
              </p>
              {row.result && (
                <p className="feed-result" style={{ margin: 0 }}>
                  {row.result}
                </p>
              )}
            </div>
            <span className="feed-time" title="IST">
              {row.at ? `${istTime(row.at)} IST` : "live"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function SystemPanel({
  telemetry,
  fleet,
  autonomy,
  cpuHistory,
  ramHistory,
}: {
  telemetry: HostTelemetry | null;
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
  cpuHistory: number[];
  ramHistory: number[];
}) {
  const online = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const total = fleet?.agent_count ?? fleet?.agents?.length ?? 0;
  const cpuOk = telemetry?.status === "ok" && typeof telemetry.cpu_percent === "number";
  const ramOk = telemetry?.status === "ok" && typeof telemetry.ram_percent === "number";

  return (
    <div className="instruments">
      <Reveal as="article">
        <div className="instrument">
          <div className="stat-head">
            <span className="stat-label">
              <Cpu size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Server 1 CPU
            </span>
            <span className={`status-pill ${cpuOk ? "good" : "muted"}`}>{cpuOk ? "live" : "n/a"}</span>
          </div>
          <div className="stat-value">{cpuOk ? <CountUp value={Math.round(telemetry!.cpu_percent!)} suffix="%" /> : "—"}</div>
          <div className="stat-foot">
            <span>{telemetry?.cpu_cores ?? "—"} cores · Oracle Always Free</span>
            <Sparkline values={cpuHistory} color="#f2a33c" />
          </div>
        </div>
      </Reveal>

      <Reveal as="article" delay={70}>
        <div className="instrument">
          <div className="stat-head">
            <span className="stat-label">
              <Gauge size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Server 1 memory
            </span>
            <span className={`status-pill ${telemetry?.status === "ok" ? "good" : "muted"}`}>
              {telemetry?.status === "ok" ? "live" : "n/a"}
            </span>
          </div>
          <div className="stat-value">{ramOk ? <CountUp value={Math.round(telemetry!.ram_percent!)} suffix="%" /> : "—"}</div>
          <div className="stat-foot">
            <span>
              {telemetry?.ram_used_gb ?? "—"} / {telemetry?.ram_total_gb ?? "—"} GB used
            </span>
            <Sparkline values={ramHistory} color="#d8c9a3" />
          </div>
        </div>
      </Reveal>

      <Reveal as="article" delay={140}>
        <div className="instrument">
          <div className="stat-head">
            <span className="stat-label">
              <Globe2 size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Fleet online
            </span>
            <span className={`status-pill ${statusTone(fleet?.status)}`}>{fleet?.status ?? "unknown"}</span>
          </div>
          <div className="stat-value">
            <CountUp value={online} />
            <small> / {total}</small>
          </div>
          <div className="stat-foot">
            <span>agents reachable right now</span>
            <Wifi size={15} style={{ color: "var(--good)" }} />
          </div>
        </div>
      </Reveal>

      <Reveal as="article" delay={210}>
        <div className="instrument">
          <div className="stat-head">
            <span className="stat-label">
              <Zap size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Autonomy
            </span>
            <span className={`status-pill ${autonomy?.autonomous_mode ? "good" : "muted"}`}>
              {autonomy?.autonomous_mode ? "running" : "manual"}
            </span>
          </div>
          <div className="stat-value">{autonomy?.history_count ?? 0}</div>
          <div className="stat-foot">
            <span>autonomous actions recorded</span>
            <span style={{ color: "var(--amber)" }}>{autonomy?.active_agent ? `active: ${autonomy.active_agent}` : "· standby"}</span>
          </div>
        </div>
      </Reveal>
    </div>
  );
}

/* Compact strip: fleet + autonomy at a glance. (The Reactor Deck's
   vitals ribbon in page.tsx supersedes this on the console; kept for
   any other surface that wants the dock footer.) */
export function ConsoleStrip({
  fleet,
  autonomy,
}: {
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
}) {
  const online = fleet?.agents?.filter((a) => statusTone(a.status) === "good").length ?? 0;
  const total = fleet?.agent_count ?? fleet?.agents?.length ?? 10;
  return (
    <div className="console-strip">
      <span className="strip-pill">
        <Zap size={12} style={{ color: "var(--amber)" }} />
        {autonomy?.autonomous_mode ? "autonomy running" : "autonomy manual"}
      </span>
      {(autonomy?.history_count ?? 0) > 0 && (
        <span className="strip-pill" title="Autonomous actions logged by the fleet">
          <BarChart2 size={12} style={{ color: "var(--amber)" }} />
          {autonomy?.history_count} actions logged
        </span>
      )}
      {fleet && online > 0 && (
        <span className="strip-pill" title="Agents answering health probes">
          <span className={`dot ${online < total ? "warn" : "good"}`} />
          {online} of {total} agents answering
        </span>
      )}
    </div>
  );
}
