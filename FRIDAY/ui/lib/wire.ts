/* ================================================================
   wire.ts — the Halo console's line to the FRIDAY backend.

   Written fresh for TASK-WEB-002. This module is plumbing, not
   design: every shape below is dictated by the JSON that
   FRIDAY/src/friday/api/server.py actually returns, and every
   path is an endpoint that already exists in production.

     POST /api/chat                          { message } -> reply
     GET  /api/v1/conversation/history       durable thread restore
     GET  /api/livekit/token                 voice room credentials
     GET  /api/voice/diagnostics             voice worker heartbeat
     POST /api/voice/diagnostics/report      session quality report
     GET  /api/agents/status                 fleet reachability
     GET  /api/agents/live                   who is doing what now
     GET  /api/system_telemetry              host vitals
     GET  /api/autonomous/status             autonomy ledger
     GET  /api/tasks/timeline                delegation ledger
     WS   /api/ws/activity                   live activity frames
   ================================================================ */

export interface FleetAgent {
  id: string;
  name: string;
  role?: string;
  icon?: string;
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
  agents: FleetAgent[];
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

export interface AutonomySnapshot {
  autonomous_mode?: boolean;
  full_access_mode?: boolean;
  sensitive_actions_auto_approved?: boolean;
  active_agent?: string | null;
  active_directive?: string | null;
  history_count?: number;
  agent_activity?: Record<string, { directive?: string; result?: string; success?: boolean; recorded_at?: string; timestamp?: string }>;
  recent_actions?: AutonomyAction[];
}

export interface LiveAgent {
  id: string;
  reachability: string;
  latency_ms?: number;
  last_checked?: string;
  in_flight?: { task_id: string; description: string; status: string; since: string } | null;
  last_outcome?: { task_id: string; description: string; status: string; at: string } | null;
  total_records?: number;
}

export interface AgentsLiveSnapshot {
  status: string;
  scope: string;
  timestamp: string;
  ledger_total: number;
  agents: LiveAgent[];
  note?: string;
}

export interface TimelineEvent {
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

export interface TimelineSnapshot {
  status: string;
  scope: string;
  timestamp: string;
  total_records: number;
  returned: number;
  chip_counts?: Record<string, number>;
  events: TimelineEvent[];
  note?: string;
}

export interface ActivityFrame {
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

export interface HistoryEntry {
  id?: string;
  user_input: string;
  friday_reply: string;
  timestamp: string;
  input_type?: string;
  status?: string;
  agents_involved?: string[];
}

export interface WorkerStatus {
  state?: string;
  provider?: string;
  detail?: string;
  updated_at?: string;
}

export interface ChatReply {
  reply: string;
  mode?: string;
  [key: string]: unknown;
}

/* ------------------------------------------------------------ transport */

export function apiBase(): string {
  if (typeof window === "undefined") return "";
  const override = new URLSearchParams(window.location.search).get("api");
  if (override) return override.replace(/\/+$/, "");
  return window.location.origin;
}

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
      /* an unreadable body still leaves the status line */
    }
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return (await res.json()) as T;
}

/* ---------------------------------------------------------------- calls */

/** The chat ceiling is a contract, not a preference: five minutes. */
export const CHAT_CEILING_MS = 300_000;

export async function sendChat(message: string): Promise<ChatReply> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), CHAT_CEILING_MS);
  try {
    return await requestJson<ChatReply>("/api/chat", {
      method: "POST",
      body: JSON.stringify({ message }),
      signal: controller.signal,
    });
  } finally {
    window.clearTimeout(timer);
  }
}

export async function fetchHistory(limit: number): Promise<HistoryEntry[]> {
  const page = await requestJson<{ entries?: HistoryEntry[] }>(
    `/api/v1/conversation/history?limit=${limit}`,
  );
  return Array.isArray(page?.entries) ? page.entries : [];
}

export function fetchFleet(): Promise<FleetSnapshot> {
  return requestJson<FleetSnapshot>("/api/agents/status");
}

export function fetchLive(): Promise<AgentsLiveSnapshot> {
  return requestJson<AgentsLiveSnapshot>("/api/agents/live");
}

export function fetchTelemetry(): Promise<HostTelemetry> {
  return requestJson<HostTelemetry>("/api/system_telemetry");
}

export function fetchAutonomy(): Promise<AutonomySnapshot> {
  return requestJson<AutonomySnapshot>("/api/autonomous/status");
}

export function fetchTimeline(): Promise<TimelineSnapshot> {
  return requestJson<TimelineSnapshot>("/api/tasks/timeline");
}

export async function fetchWorker(): Promise<WorkerStatus | null> {
  const res = await requestJson<{ worker?: WorkerStatus }>("/api/voice/diagnostics");
  return res?.worker ?? null;
}

export function openActivitySocket(onFrame: (frame: ActivityFrame) => void): WebSocket | null {
  if (typeof window === "undefined") return null;
  try {
    const base = apiBase();
    const url = `${base.replace(/^http/, "ws")}/api/ws/activity`;
    const socket = new WebSocket(url);
    socket.onmessage = (event) => {
      try {
        const parsed = JSON.parse(String(event.data)) as ActivityFrame;
        if (parsed && typeof parsed === "object") onFrame(parsed);
      } catch {
        /* a malformed frame is dropped, never rendered */
      }
    };
    return socket;
  } catch {
    return null;
  }
}

/* ------------------------------------------------------------- wording */

/** Wall-clock in the fleet's home zone, for timestamps the owner reads. */
export function clockTime(value?: string | number | Date | null): string {
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

/** Call timer: seconds as MM:SS. */
export function durationClock(totalSeconds: number): string {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  return `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** Compact age — "now", "45s", "3m", "2h", "5d"; "" when unparseable. */
export function ageLabel(value?: string | number | Date | null): string {
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

/** One display line from a long directive/result string. */
export function oneLine(text?: string | null, maxLen = 160): string {
  if (!text) return "";
  const flat = String(text).replace(/\s+/g, " ").trim();
  if (flat.length <= maxLen) return flat;
  return `${flat.slice(0, Math.max(1, maxLen - 1))}…`;
}

export type Tone = "good" | "warn" | "bad" | "muted";

export function toneFor(status?: string | null): Tone {
  const s = String(status ?? "").toUpperCase();
  if (["ONLINE", "REACHABLE", "OK", "HEALTHY", "COMPLETED", "DONE", "SUCCESS"].includes(s)) return "good";
  if (["DEGRADED", "WARN", "PENDING", "RUNNING", "QUEUED"].includes(s)) return "warn";
  if (["OFFLINE", "UNREACHABLE", "FAILED", "ERROR", "ROUTING_FAILED"].includes(s)) return "bad";
  return "muted";
}
