"use client";

import { useEffect, useState } from "react";
import Counter from "../reactbits/Counter";
import { BUILD_NAME, BUILD_TAG } from "@/lib/build-info";
import {
  ageLabel,
  fetchAutonomy,
  fetchTelemetry,
  fetchWorker,
  oneLine,
  type AutonomySnapshot,
  type HostTelemetry,
  type WorkerStatus,
} from "@/lib/wire";

/* ================================================================
   The machine's pulse, summoned — the host's vitals, the voice
   worker's heartbeat, and what autonomy has been doing. Every
   number here is a live reading from the box itself
   (/api/system_telemetry, /api/autonomous/status,
   /api/voice/diagnostics). There are deliberately no switches
   in this layer: it reports, it does not configure.
   ================================================================ */

export function PulseSheet() {
  const [telemetry, setTelemetry] = useState<HostTelemetry | null>(null);
  const [autonomy, setAutonomy] = useState<AutonomySnapshot | null>(null);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const [t, a] = await Promise.all([fetchTelemetry(), fetchAutonomy()]);
        if (cancelled) return;
        setTelemetry(t);
        setAutonomy(a);
        setFailed(false);
      } catch {
        if (!cancelled) setFailed(true);
      }
      try {
        const w = await fetchWorker();
        if (!cancelled) setWorker(w);
      } catch {
        /* the voice heartbeat is a bonus reading, not a requirement */
      }
    };
    void load();
    const timer = window.setInterval(load, 20_000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const recent = (autonomy?.recent_actions ?? []).slice(0, 6);

  return (
    <div className="pulse">
      {failed && <p className="sheet-note">The machine didn&apos;t answer — no numbers are invented in its place.</p>}

      <div className="pulse-vitals">
        <div className="pulse-vital">
          <span className="pulse-label">Processor</span>
          <span className="pulse-value">
            {typeof telemetry?.cpu_percent === "number" ? <Counter value={Math.round(telemetry.cpu_percent)} fontSize={30} /> : "—"}
            <span className="pulse-unit">%</span>
          </span>
          <span className="pulse-sub">{telemetry?.cpu_cores ? `${telemetry.cpu_cores} cores` : ""}</span>
        </div>
        <div className="pulse-vital">
          <span className="pulse-label">Memory</span>
          <span className="pulse-value">
            {typeof telemetry?.ram_percent === "number" ? <Counter value={Math.round(telemetry.ram_percent)} fontSize={30} /> : "—"}
            <span className="pulse-unit">%</span>
          </span>
          <span className="pulse-sub">
            {telemetry?.ram_used_gb != null && telemetry?.ram_total_gb != null
              ? `${telemetry.ram_used_gb.toFixed(1)} of ${telemetry.ram_total_gb.toFixed(1)} GB`
              : ""}
          </span>
        </div>
        <div className="pulse-vital">
          <span className="pulse-label">Voice service</span>
          <span className="pulse-value pulse-value-text">{worker?.state ?? "—"}</span>
          <span className="pulse-sub">{worker?.provider ?? ""}</span>
        </div>
        <div className="pulse-vital">
          <span className="pulse-label">Autonomy</span>
          <span className="pulse-value pulse-value-text">{autonomy ? (autonomy.autonomous_mode ? "awake" : "asleep") : "—"}</span>
          <span className="pulse-sub">
            {autonomy?.active_directive ? oneLine(autonomy.active_directive, 60) : "no directive in flight"}
          </span>
        </div>
      </div>

      {recent.length > 0 && (
        <div className="pulse-actions">
          <p className="pulse-actions-head">Latest autonomous moves</p>
          {recent.map((action, idx) => (
            <p key={idx} className="pulse-action">
              <span className={`pulse-action-mark ${action.success === false ? "is-bad" : ""}`} aria-hidden="true" />
              <span className="pulse-action-text">
                {oneLine(action.directive || action.action_type || "action", 130)}
                {action.target ? <span className="pulse-action-target"> → {oneLine(action.target, 40)}</span> : null}
              </span>
              <time className="chronicle-time">{ageLabel(action.recorded_at || action.timestamp)}</time>
            </p>
          ))}
        </div>
      )}

      <p className="pulse-foot">
        {BUILD_NAME} · build {BUILD_TAG}
        {telemetry?.os ? ` · ${telemetry.os}` : ""}
        {telemetry?.timestamp ? ` · read ${ageLabel(telemetry.timestamp) || "just now"}` : ""}
      </p>
    </div>
  );
}
