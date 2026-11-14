"use client";

import { AlertTriangle, Mic, PhoneOff, Radio } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";
import { useCallback, useEffect, useRef, useState } from "react";
import { Arc, ArcState } from "./Arc";
import { apiBase, formatClock, requestJson } from "@/lib/api";

/* ============================================================
   The voice line — a continuous LiveKit call with FRIDAY.

   One tap opens a fresh private room (a new room per call, so
   no stale agent session can linger from the last one), the
   microphone stays open for the whole conversation, and the
   line puts itself to rest when it goes quiet — the free
   LiveKit minutes are finite and are treated that way.

   The worker's own heartbeat (/api/voice/diagnostics) is read
   before anything else: when the speech service cannot take
   a call, the button says why instead of ringing into silence.

   Connection behaviour is carried over unchanged from the
   previous console — token fetch, per-call room, intentional-
   end guard, bounded reconnect, session diagnostics report.
   Everything the owner sees and reads here is new.
   ============================================================ */

const IDLE_TIMEOUT_MS = 3 * 60 * 1000;
const HARD_CAP_MS = 30 * 60 * 1000;

type LineStatus = "idle" | "connecting" | "connected" | "error";

type WorkerStatus = {
  state?: string;
  provider?: string;
  detail?: string;
  updated_at?: string;
};

export function VoiceCall({ onStateChange }: { onStateChange?: (state: ArcState) => void }) {
  const [status, setStatus] = useState<LineStatus>("idle");
  const [message, setMessage] = useState("Tap the ring and just talk — no menus, no wake word.");
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [micSpeaking, setMicSpeaking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const roomRef = useRef<Room | null>(null);
  /* Both time refs are (re)stamped the moment a call connects; their
     initial values are never read before that. */
  const lastActivityRef = useRef<number>(0);
  const connectedAtRef = useRef<number>(0);
  const sessionIdRef = useRef<string>("");
  const sessionStartRef = useRef<number>(0);
  /* Intentional-end guard: a call the owner ended on purpose must
     never resurrect itself through the drop-reconnect path. */
  const intentionalEndRef = useRef(false);

  const arcState: ArcState =
    status === "connected"
      ? peerSpeaking
        ? "speaking"
        : micSpeaking
          ? "listening"
          : "listening"
      : status === "connecting"
        ? "connecting"
        : status === "error"
          ? "thinking"
          : "idle";

  useEffect(() => {
    onStateChange?.(arcState);
  }, [arcState, onStateChange]);

  /* Worker heartbeat: fetched once on mount. Only real failures
     (no-provider / error) are surfaced — the resting "registered"
     heartbeat is the service's normal state, not a warning. */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await requestJson<{ worker?: WorkerStatus }>("/api/voice/diagnostics");
        if (!cancelled && res?.worker) setWorker(res.worker);
      } catch {
        /* endpoint absent → the line behaves as it always has */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const workerFailed = worker?.state === "no-provider" || worker?.state === "error";

  const clearAudioElements = useCallback(() => {
    document.querySelectorAll("audio[data-livekit]").forEach((el) => el.remove());
  }, []);

  const endCall = useCallback(
    (note: string) => {
      intentionalEndRef.current = true;
      roomRef.current?.disconnect();
      roomRef.current = null;
      clearAudioElements();
      setPeerSpeaking(false);
      setMicSpeaking(false);
      setAudioBlocked(false);
      setSeconds(0);
      setStatus("idle");
      setMessage(note);
    },
    [clearAudioElements],
  );

  /* Call clock + the two self-rest rules (idle, hard cap). */
  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
      const idleFor = Date.now() - lastActivityRef.current;
      if (idleFor > IDLE_TIMEOUT_MS) {
        endCall("Closed after three quiet minutes — your free voice minutes matter more than an open line. Tap to talk again.");
      } else if (Date.now() - connectedAtRef.current > HARD_CAP_MS) {
        endCall("That's the 30-minute mark for one call. Tap whenever you're ready to continue.");
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [status, endCall]);

  /* Teardown on unmount. */
  useEffect(() => {
    return () => {
      roomRef.current?.disconnect();
      roomRef.current = null;
      document.querySelectorAll("audio[data-livekit]").forEach((el) => el.remove());
    };
  }, []);

  async function startCall() {
    if (status === "connecting" || status === "connected") return;
    setStatus("connecting");
    setMessage("Opening a private room for us…");
    setPeerSpeaking(false);
    setMicSpeaking(false);
    setAudioBlocked(false);
    intentionalEndRef.current = false;

    /* A fresh room per call: the shared fixed room once accumulated
       one agent per call, which is exactly the dead-air failure this
       design replaced. A new room gives every call exactly one agent
       and a clean lifecycle — the room empties when the call ends. */
    const suffix =
      typeof crypto !== "undefined" && crypto.randomUUID
        ? crypto.randomUUID().slice(0, 8)
        : Math.random().toString(36).slice(2, 10);
    const roomName = `friday-${suffix}`;

    const room = new Room({ adaptiveStream: true, dynacast: true });
    let startupComplete = false;
    let startupFailed = false;
    let startupDisconnected = false;
    try {
      void room.startAudio().catch(() => {});
    } catch {
      /* optional playback warm-up */
    }

    try {
      const identity = `owner-${suffix}`;
      const body = await requestJson<{ server_url: string; token: string }>(
        `/api/livekit/token?room=${encodeURIComponent(roomName)}&identity=${encodeURIComponent(identity)}`,
      );

      const attachAudio = (track: Track) => {
        if (track.kind !== Track.Kind.Audio) return;
        if (track.attachedElements.length > 0) return;
        const element = track.attach() as HTMLAudioElement;
        element.setAttribute("data-livekit", "true");
        element.autoplay = true;
        element.setAttribute("playsinline", "true");
        element.volume = 1.0;
        document.body.appendChild(element);
        element.play().catch(() => {
          setAudioBlocked(true);
          void room.startAudio().catch(() => {});
        });
      };

      room.on(RoomEvent.TrackSubscribed, (track) => {
        if (track.kind === Track.Kind.Audio) attachAudio(track);
      });

      room.on(RoomEvent.TrackUnsubscribed, (track) => {
        track.detach().forEach((el) => el.remove());
      });

      room.on(RoomEvent.ActiveSpeakersChanged, (speakers) => {
        lastActivityRef.current = Date.now();
        const peer = speakers.some((s) => s.identity && !s.identity.startsWith("owner-"));
        const self = speakers.some((s) => s.identity?.startsWith("owner-"));
        setPeerSpeaking(peer);
        setMicSpeaking(self);
        /* Once FRIDAY actually speaks, the line stops saying "waking
           up" — the owner can see the call came alive. */
        if (peer) {
          setMessage((current) => (current.startsWith("Line's open") ? "We're live. Talk over me whenever you need to." : current));
        }
      });

      let lastRtt: number | null = null;
      let lastLoss: number | null = null;
      room.on(RoomEvent.ConnectionQualityChanged, (_quality: unknown, participant: unknown) => {
        const p = participant as
          | { isLocal?: boolean; connectionQuality?: { rtt?: unknown; roundTripTime?: unknown; loss?: unknown; fractionLost?: unknown } }
          | undefined;
        if (!p?.isLocal) return;
        const info = p.connectionQuality;
        if (info && typeof info === "object") {
          const rtt = info.rtt ?? info.roundTripTime;
          const loss = info.loss ?? info.fractionLost;
          if (typeof rtt === "number" && rtt > 0) lastRtt = rtt;
          if (typeof loss === "number" && loss >= 0 && loss <= 1) lastLoss = loss * 100;
        }
      });

      let reconnectAttempts = 0;
      const MAX_RECONNECT = 2;

      const postDiagnostics = async (finalStatus: string, durationSec: number) => {
        try {
          await fetch(`${apiBase()}/api/voice/diagnostics/report`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              session_id: sessionIdRef.current,
              started_at: new Date(sessionStartRef.current).toISOString(),
              ended_at: new Date().toISOString(),
              duration_sec: Math.round(durationSec),
              rtt_ms: lastRtt,
              packet_loss_pct: lastLoss,
              reconnect_count: reconnectAttempts,
              quality: finalStatus,
            }),
          });
        } catch {
          /* diagnostics are best-effort — never block the call flow */
        }
      };

      const settleClosed = async (duration: number) => {
        await postDiagnostics(duration > 0 ? (lastRtt != null && lastRtt < 250 ? "good" : "degraded") : "no-session-yet", duration);
        roomRef.current = null;
        clearAudioElements();
        setPeerSpeaking(false);
        setMicSpeaking(false);
        setSeconds(0);
        setStatus("idle");
        setMessage("Line closed.");
      };

      room.on(RoomEvent.Disconnected, async () => {
        /* A failed setup owns its cleanup and its error state — it was
           never a live session, so no reconnect and no overwrite. */
        if (startupFailed) return;
        if (!startupComplete) {
          startupDisconnected = true;
          return;
        }
        const duration = (Date.now() - sessionStartRef.current) / 1000;
        /* Intentional end: report the session and settle. Never
           resurrect a line the owner closed on purpose. */
        if (intentionalEndRef.current) {
          await settleClosed(duration);
          return;
        }
        if (reconnectAttempts < MAX_RECONNECT && Date.now() - lastActivityRef.current < IDLE_TIMEOUT_MS) {
          reconnectAttempts += 1;
          setStatus("connecting");
          setMessage(`The line dropped — bringing it back (${reconnectAttempts}/${MAX_RECONNECT})…`);
          try {
            await new Promise((r) => setTimeout(r, 1000 * reconnectAttempts));
            if (!roomRef.current) {
              const fresh = new Room({ adaptiveStream: true, dynacast: true });
              await fresh.connect(body.server_url, body.token);
              await fresh.localParticipant.setMicrophoneEnabled(true);
              roomRef.current = fresh;
              connectedAtRef.current = Date.now();
              lastActivityRef.current = Date.now();
              setStatus("connected");
              setMessage("Back with you — go ahead.");
              return;
            }
          } catch {
            /* fall through to the honest closed path */
          }
        }
        await settleClosed(duration);
      });

      await room.connect(body.server_url, body.token);
      await room.localParticipant.setMicrophoneEnabled(true);
      if (startupDisconnected) throw new Error("The line dropped while it was opening. Tap to try again.");

      startupComplete = true;
      roomRef.current = room;
      connectedAtRef.current = Date.now();
      lastActivityRef.current = Date.now();
      sessionIdRef.current = `voice-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      sessionStartRef.current = Date.now();
      setSeconds(0);
      setStatus("connected");
      setMessage("Line's open. Give me a moment — I'll say hello first.");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "The voice line couldn't open.";
      startupFailed = true;
      intentionalEndRef.current = true;
      /* roomRef is only assigned after the mic publishes; clean the
         locally allocated room even when setup failed before that. */
      try {
        await room.disconnect();
      } catch {
        /* retain the original error */
      }
      roomRef.current = null;
      clearAudioElements();
      setStatus("error");
      setMessage(
        reason.includes("permission") || reason.toLowerCase().includes("denied")
          ? "Mic permission denied — the browser blocked it. Allow mic access for this site, then tap again."
          : reason,
      );
    }
  }

  return (
    <div className="voice-line">
      <button
        type="button"
        className="arc-button"
        onClick={() => {
          /* The ring starts a call; it never ends one — an accidental
             tap mid-conversation must not hang up. The End call
             button below owns ending. */
          if (status === "idle" || status === "error") void startCall();
        }}
        disabled={status === "connecting" || (workerFailed && status === "idle")}
        aria-label={status === "connected" ? "Voice call in progress" : "Start a voice call with FRIDAY"}
        title={workerFailed && status === "idle" ? `Voice service unavailable: ${worker?.detail || worker?.state}` : undefined}
      >
        <Arc state={arcState} />
      </button>

      <div className="line-readout" aria-live="polite">
        <strong className="line-message">{message}</strong>
        {status === "connected" && (
          <span className="line-timer">
            <span className="rec-dot" aria-hidden="true" />
            {formatClock(seconds)}
          </span>
        )}
      </div>

      {workerFailed && status === "idle" && (
        <p className="line-warning" role="alert">
          <AlertTriangle size={14} aria-hidden="true" />
          <span>The voice service can&apos;t take a call right now: {worker?.detail || worker?.state}</span>
        </p>
      )}

      <button
        type="button"
        className={`call-btn ${status === "connected" ? "is-live" : ""}`}
        onClick={() => (status === "connected" ? endCall("Line closed.") : void startCall())}
        disabled={status === "connecting" || (workerFailed && status === "idle")}
        aria-label={status === "connected" ? "End voice call" : "Start voice call"}
      >
        {status === "connecting" ? (
          <>
            <Radio size={17} className="spin" /> Connecting
          </>
        ) : status === "connected" ? (
          <>
            <PhoneOff size={16} /> End call
          </>
        ) : (
          <>
            <Mic size={17} /> Talk to FRIDAY
          </>
        )}
      </button>

      {audioBlocked && (
        <p className="line-note warn">Your browser held back the sound — tap anywhere once, then press the button again.</p>
      )}
      <p className="line-note">English or Telugu · I hear you through the whole call, not in turns</p>
    </div>
  );
}
