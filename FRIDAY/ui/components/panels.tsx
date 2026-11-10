"use client";

import {
  Activity,
  ArrowUpRight,
  BarChart2,
  CheckCircle2,
  Cpu,
  Database,
  Eye,
  Globe2,
  HardDrive,
  Layers,
  MessageSquareText,
  Network,
  ShieldCheck,
  Terminal,
  Wifi,
  Zap,
} from "lucide-react";
import { Agent, AutonomySnapshot, FleetSnapshot, HostTelemetry, LiveActivityEvent, statusTone } from "@/lib/api";
import { CountUp, Reveal, SpotlightCard } from "./effects";

/* ============================================================
   Fleet grid, telemetry strip and live activity feed.
   ============================================================ */

const AGENT_ORDER = ["stratex", "inference", "cortex", "forge", "intelx", "vyralx", "memora", "futuris", "sentinel"] as const;

const AGENT_ICONS: Record<string, React.ReactNode> = {
  stratex: <BarChart2 size={17} />,
  inference: <Network size={17} />,
  cortex: <Database size={17} />,
  forge: <Terminal size={17} />,
  intelx: <ShieldCheck size={17} />,
  vyralx: <Layers size={17} />,
  memora: <HardDrive size={17} />,
  futuris: <Eye size={17} />,
  sentinel: <Wifi size={17} />,
};

export function Sparkline({ values, color, width = 130, height = 38 }: { values: number[]; color: string; width?: number; height?: number }) {
  if (values.length < 2) return <svg width={width} height={height} aria-hidden="true" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(max - min, 1);
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * 100},${100 - ((v - min) / span) * 90}`);
  const d = `M${pts.join(" L")}`;
  const last = pts[pts.length - 1].split(",");
  return (
    <svg width={width} height={height} viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path d={d} fill="none" stroke={color} strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r={3} fill={color} />
    </svg>
  );
}

export function FleetGrid({
  fleet,
  autonomy,
  liveActivity,
  onAsk,
}: {
  fleet: FleetSnapshot | null;
  autonomy: AutonomySnapshot | null;
  liveActivity: Record<string, LiveActivityEvent>;
  onAsk: (agent: Agent) => void;
}) {
  const agents = fleet?.agents ?? [];
  const sorted = [...agents].sort((a, b) => {
    const ai = AGENT_ORDER.indexOf(a.id as (typeof AGENT_ORDER)[number]);
    const bi = AGENT_ORDER.indexOf(b.id as (typeof AGENT_ORDER)[number]);
    return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi);
  });

  if (sorted.length === 0) {
    return (
      <div className="panel feed-empty">
        <Globe2 size={22} style={{ marginBottom: 8 }} />
        The fleet has not reported yet. The status probe refreshes every 30 seconds.
      </div>
    );
  }

  return (
    <div className="fleet-grid">
      {sorted.map((agent, index) => {
        const live = liveActivity[agent.id];
        const record = live
          ? { directive: live.directive || `${live.action ?? "activity"} ${live.target ?? ""}`.trim(), result: live.result, success: Boolean(live.success) }
          : autonomy?.agent_activity?.[agent.id];
        const isActive = autonomy?.active_agent?.toLowerCase() === agent.id;
        const tone = statusTone(agent.status);
        return (
          <Reveal key={agent.id} delay={Math.min(index * 60, 360)} as="article">
            <SpotlightCard className={`agent-card tone-${tone}${isActive ? " active" : ""}`}>
              <span className="edge" aria-hidden="true" />
              <div className="agent-head">
                <div className="agent-icon">{AGENT_ICONS[agent.id] ?? <Database size={17} />}</div>
                <div className="agent-identity">
                  <div className="agent-name">
                    {agent.name}
                    {isActive && <span className="dot good pulse" aria-label="active" />}
                  </div>
                  <span className="agent-id">{agent.id}</span>
                  <div className="agent-role">{agent.role || "Specialist agent"}</div>
                </div>
                <span className={`status-pill ${tone}`}>{agent.status}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
                <span className="agent-latency">
                  {typeof agent.latency_ms === "number" ? `${Math.round(agent.latency_ms)} ms` : "latency n/a"}
                </span>
              </div>
              <div className="agent-task">
                {record?.directive ? (
                  <>
                    <strong>Last directive:</strong> {record.directive}
                  </>
                ) : (
                  <>Idle — awaiting directive</>
                )}
              </div>
              {record?.result !== undefined && record.result !== null && String(record.result).trim() !== "" && (
                <div className={`agent-result ${record.success ? "good" : "bad"}`}>
                  {record.success ? <CheckCircle2 size={13} style={{ flex: "none", marginTop: 2 }} /> : <Activity size={13} style={{ flex: "none", marginTop: 2 }} />}
                  <span>{String(record.result).slice(0, 120)}</span>
                </div>
              )}
              <div className="agent-actions">
                <button className="mini-btn" onClick={() => onAsk(agent)}>
                  <MessageSquareText size={13} /> Ask via chat
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
            </SpotlightCard>
          </Reveal>
        );
      })}
    </div>
  );
}

export function TelemetryStrip({
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

  return (
    <div className="telemetry-grid">
      <Reveal as="article">
        <SpotlightCard className="panel stat-card">
          <div className="stat-head">
            <span className="stat-label">
              <Cpu size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Host CPU
            </span>
            <span className={`status-pill ${cpuOk ? "good" : "muted"}`}>{cpuOk ? "live" : "n/a"}</span>
          </div>
          <div className="stat-value grad-text">
            {cpuOk ? <CountUp value={Math.round(telemetry!.cpu_percent!)} suffix="%" /> : "—"}
          </div>
          <div className="stat-foot">
            <span>{telemetry?.cpu_cores ?? "—"} cores · {telemetry?.os ?? "Oracle host"}</span>
            <Sparkline values={cpuHistory} color="#8de6cf" />
          </div>
        </SpotlightCard>
      </Reveal>

      <Reveal as="article" delay={70}>
        <SpotlightCard className="panel stat-card">
          <div className="stat-head">
            <span className="stat-label">
              <Activity size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Host memory
            </span>
            <span className={`status-pill ${telemetry?.status === "ok" ? "good" : "muted"}`}>
              {telemetry?.status === "ok" ? "live" : "n/a"}
            </span>
          </div>
          <div className="stat-value grad-text">
            {telemetry?.status === "ok" && typeof telemetry.ram_percent === "number" ? (
              <CountUp value={Math.round(telemetry.ram_percent)} suffix="%" />
            ) : (
              "—"
            )}
          </div>
          <div className="stat-foot">
            <span>
              {telemetry?.ram_used_gb ?? "—"} / {telemetry?.ram_total_gb ?? "—"} GB used
            </span>
            <Sparkline values={ramHistory} color="#b9a6ff" />
          </div>
        </SpotlightCard>
      </Reveal>

      <Reveal as="article" delay={140}>
        <SpotlightCard className="panel stat-card">
          <div className="stat-head">
            <span className="stat-label">
              <Globe2 size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Fleet online
            </span>
            <span className={`status-pill ${statusTone(fleet?.status)}`}>{fleet?.status ?? "unknown"}</span>
          </div>
          <div className="stat-value grad-text">
            <CountUp value={online} />
            <small> / {total}</small>
          </div>
          <div className="stat-foot">
            <span>agents reachable right now</span>
            <Wifi size={15} style={{ color: "var(--mint)" }} />
          </div>
        </SpotlightCard>
      </Reveal>

      <Reveal as="article" delay={210}>
        <SpotlightCard className="panel stat-card">
          <div className="stat-head">
            <span className="stat-label">
              <Zap size={13} style={{ display: "inline", marginRight: 6, verticalAlign: -2 }} /> Autonomy
            </span>
            <span className={`status-pill ${autonomy?.autonomous_mode ? "good" : "muted"}`}>
              {autonomy?.autonomous_mode ? "enabled" : "manual"}
            </span>
          </div>
          <div className="stat-value grad-text">
            {autonomy?.history_count ?? 0}
          </div>
          <div className="stat-foot">
            <span>recorded autonomous actions</span>
            {autonomy?.active_agent ? (
              <span style={{ color: "var(--cyan)" }}>{autonomy.active_agent}</span>
            ) : (
              <span>standby</span>
            )}
          </div>
        </SpotlightCard>
      </Reveal>
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
      directive: event.directive || `${event.action ?? "activity"} ${event.target ?? ""}`.trim(),
      result: String(event.result ?? ""),
      success: Boolean(event.success),
      at: event.timestamp ?? "",
    });
  }
  for (const action of autonomy?.recent_actions ?? []) {
    rows.push({
      agent: action.target || action.action_type || "system",
      directive: action.directive || action.action_type || "action",
      result: String(action.result ?? ""),
      success: action.success !== false,
      at: action.timestamp ?? "",
    });
  }
  const seen = new Set<string>();
  const unique = rows.filter((r) => {
    const k = `${r.agent}|${r.directive}|${r.at}`;
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  }).slice(0, 12);

  if (unique.length === 0) {
    return (
      <div className="panel feed-empty">
        <Zap size={20} style={{ marginBottom: 8 }} />
        All agents standing by. Recent fleet actions will appear here in real time.
      </div>
    );
  }

  return (
    <div className="panel">
      <div className="feed-list">
        {unique.map((row, i) => (
          <div className="feed-row" key={`${row.agent}-${row.at}-${i}`} style={{ animationDelay: `${Math.min(i * 40, 240)}ms` }}>
            <div className={`feed-icon ${row.success ? "ok" : "err"}`}>
              {row.success ? <CheckCircle2 size={14} /> : <Activity size={14} />}
            </div>
            <div className="feed-body">
              <span className="feed-agent">{row.agent}</span>
              <p className="feed-text" style={{ margin: "3px 0" }}>{row.directive}</p>
              {row.result && <p className="feed-result" style={{ margin: 0 }}>{row.result.slice(0, 140)}</p>}
            </div>
            <span className="feed-time">
              {row.at
                ? new Date(row.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" })
                : "live"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
