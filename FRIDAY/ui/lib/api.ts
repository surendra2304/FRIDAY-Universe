/* ============================================================
   FRIDAY Universe UI — shared API client library.

   Reconstructed 2026-11-11 (checklist D12 tranche): the deployed
   static bundle (FRIDAY/ui/out) was built against this module, but
   the file itself was never committed — the source tree could not
   rebuild (`next build` failed on the missing `@/lib/api` module).
   Every export below matches exactly what app/page.tsx and
   components/*.tsx import and how they use it.

   Backend contracts mirrored here (FRIDAY/src/friday/api/server.py):
   - GET  /api/agents/status      → FleetSnapshot
   - GET  /api/system_telemetry   → HostTelemetry
   - GET  /api/autonomous/status → AutonomySnapshot
   - GET  /api/agents/live        → AgentsLiveSnapshot (per-agent RIGHT-NOW work)
   - WS   /api/ws/activity        → LiveActivityEvent frames ({type:"activity"})
   - POST /api/chat               → { reply, mode? }
   ============================================================ */

export interface Agent {
  id: string;
  name: string;
  role?: string;
  icon?: string;
  /** ONLINE | REACHABLE | DEGRADED | UNREACHABLE | OFFLINE (peer reachability only) */
  status: string;
  latency_ms?: number;
  endpoint?: string;
  details?: string;
  last_checked?: string;
}

export interface FleetSnapshot {
  status: string;
  scope?: string;
  timestamp?: string;
  agent_count: number;
  status_counts?: Record<string, number>;
  agents: Agent[];
  note?: string;
}

export interface HostTelemetry {
  status: string;
  cpu_percent?: number;
  cpu_cores?: number;
  ram_percent?: number;
  ram_total_gb?: number;
  ram_used_gb?: number;
  ram_avail_gb?: number;
  os?: string;
  operator?: string;
  timestamp?: string;
}

export interface AutonomyAction {
  timestamp?: string;
  recorded_at?: string;
  action_type?: string;
  target?: string;
  directive?: string;
  result?: string;
  success?: boolean;
}

export interface AgentActivity {
  directive?: string;
  result?: string;
  success?: boolean;
  recorded_at?: string;
  timestamp?: string;
}

export interface AutonomySnapshot {
  autonomous_mode?: boolean;
  full_access_mode?: boolean;
  sensitive_actions_auto_approved?: boolean;
  autonomous_mode_persistence?: string;
  active_agent?: string | null;
  active_directive?: string | null;
  history_count?: number;
  agent_activity?: Record<string, AgentActivity>;
  recent_actions?: AutonomyAction[];
}

export interface LiveActivityEvent {
  type?: string;
  agent?: string;
  action?: string;
  target?: string;
  directive?: string;
  result?: string;
  status?: string;
  detail?: string;
  command?: string;
  agents_involved?: string;
  success?: boolean;
  timestamp?: string;
}

/** One delegation-history event from the unified task ledger (D13). */
export interface TaskTimelineEvent {
  task_id: string;
  description: string;
  owner_agent: string;
  status: string;
  chip: "queued" | "running" | "done" | "failed";
  created_at: string;
  updated_at: string;
  result?: string;
  error?: string;
  history_len?: number;
}

export interface TaskTimelineSnapshot {
  status: string;
  scope: string;
  timestamp: string;
  total_records: number;
  returned: number;
  chip_counts?: Record<string, number>;
  events: TaskTimelineEvent[];
  note?: string;
}

export interface ChatMessage {
  role: "user" | "friday";
  text: string;
  /** epoch ms from Date.now() — every message is created with it */
  at: number;
  error?: boolean;
}

/** One agent's current-work line from the unified task ledger (D12). */
export interface AgentNow {
  id: string;
  reachability: string;
  latency_ms?: number;
  last_checked?: string;
  /** Task currently in flight (submitted/assigned/dispatched). */
  in_flight?: {
    task_id: string;
    description: string;
    status: string;
    since: string;
  } | null;
  /** Most recent terminal outcome (completed/failed/routing_failed). */
  last_outcome?: {
    task_id: string;
    description: string;
    status: string;
    at: string;
  } | null;
  total_records?: number;
}

export interface AgentsLiveSnapshot {
  status: string;
  scope: string;
  timestamp: string;
  ledger_total: number;
  agents: AgentNow[];
  note?: string;
}

/* ------------------------------------------------------------ values ----- */

/**
 * Base URL every API call is rooted at. The dashboard is served from the same
 * origin as the API in production (FastAPI serves the static export behind the
 * reverse proxy), so the page origin is correct; `?api=` overrides it for local
 * development against a remote backend (e.g. `?api=http://localhost:8000`).
 */
export function apiBase(): string {
  if (typeof window === "undefined") return "";
  const override = new URLSearchParams(window.location.search).get("api");
  if (override) return override.replace(/\/+$/, "");
  return window.location.origin;
}

/** Fetch JSON from the API; throws with status + first bytes on failure. */
export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    cache: "no-store",
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = (await res.text()).slice(0, 200);
    } catch {
      /* body unreadable — status line is enough */
    }
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return (await res.json()) as T;
}

/** Format a clock time in IST (Asia/Kolkata) — the project clock (D-026). */
export function istTime(value?: string | number | Date | null): string {
  if (value === undefined || value === null || value === "") return "--:--:--";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "--:--:--";
  return date.toLocaleTimeString("en-IN", {
    timeZone: "Asia/Kolkata",
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Voice-call duration clock: seconds → MM:SS. */
export function formatClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** One clean display line from a directive/result string (collapse + bound). */
export function cleanDirective(text?: string | null, maxLen = 160): string {
  if (!text) return "";
  const oneLine = String(text).replace(/\s+/g, " ").trim();
  if (oneLine.length <= maxLen) return oneLine;
  return `${oneLine.slice(0, Math.max(1, maxLen - 1))}…`;
}

/**
 * Short age label ("now", "45s", "3m", "2h", "5d") for a timestamp.
 * Returns "" when the stamp cannot be parsed — callers then show the plain
 * word ("active") instead of a wrong age (TASK-UI-003).
 */
export function freshness(value?: string | number | Date | null): string {
  if (value === undefined || value === null || value === "") return "";
  const then = value instanceof Date ? value.getTime() : new Date(value).getTime();
  if (!Number.isFinite(then)) return "";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 5) return "now";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** Tone class for a status word (matches CSS status-pill / agent-card tones). */
export function statusTone(status?: string | null): "good" | "warn" | "bad" | "muted" {
  const s = String(status ?? "").toUpperCase();
  if (["ONLINE", "REACHABLE", "OK", "HEALTHY", "COMPLETED"].includes(s)) return "good";
  if (["DEGRADED", "WARN", "PENDING"].includes(s)) return "warn";
  if (["OFFLINE", "UNREACHABLE", "FAILED", "ERROR", "ROUTING_FAILED"].includes(s)) return "bad";
  return "muted";
}
