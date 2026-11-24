"use client";

import { Mic, MicOff, PhoneCall, PhoneOff, Radio } from "lucide-react";
import { Room, RoomEvent, Track } from "livekit-client";
import { useCallback, useEffect, useRef, useState, type MutableRefObject } from "react";
import { apiBase, durationClock, fetchWorker, requestJson, type WorkerStatus } from "@/lib/wire";

/* ================================================================
   The voice line for the Halo console (TASK-WEB-002).

   One continuous LiveKit conversation with FRIDAY. Every call
   opens its own room — a room per call means no stale agent can
   linger from the last conversation — and the microphone stays
   open until the line closes. The line rests itself after three
   quiet minutes and caps a single call at thirty, because the
   free voice minutes are a budget, not an assumption.

   Before anything rings, the worker heartbeat is read: if the
   speech service cannot take a call, the controls say so plainly
   instead of opening a room nobody answers.

   The connection discipline here (fresh room, intentional-end
   guard, bounded reconnect, session diagnostics) is production
   behaviour carried over deliberately; every word the owner
   reads and every pixel of presentation is new.
   ================================================================ */

const IDLE_TIMEOUT_MS = 3 * 60 * 1000;
const HARD_CAP_MS = 30 * 60 * 1000;

export type VoicePhase = "resting" | "opening" | "listening" | "thinking" | "speaking" | "down";

export interface VoiceLinkControls {
  start: () => void;
  end: () => void;
  toggleMute: () => void;
}

type LineStatus = "idle" | "connecting" | "connected" | "error";

export function VoiceCall({
  onPhase,
  linkRef,
}: {
  onPhase?: (phase: VoicePhase) => void;
  linkRef?: MutableRefObject<VoiceLinkControls | null>;
}) {
  const [status, setStatus] = useState<LineStatus>("idle");
  const [message, setMessage] = useState("Quiet for now. Start the line and speak whenever you're ready.");
  const [peerSpeaking, setPeerSpeaking] = useState(false);
  const [micSpeaking, setMicSpeaking] = useState(false);
  const [seconds, setSeconds] = useState(0);
  const [audioBlocked, setAudioBlocked] = useState(false);
  const [muted, setMuted] = useState(false);
  const [worker, setWorker] = useState<WorkerStatus | null>(null);
  const roomRef = useRef<Room | null>(null);
  /* Both stamps are set the moment a call connects; nothing reads
     them before that. */
  const lastActivityRef = useRef<number>(0);
  const connectedAtRef = useRef<number>(0);
  const sessionIdRef = useRef<string>("");
  const sessionStartRef = useRef<number>(0);
  /* Intentional-end guard: a line the owner closed on purpose must
     never pull itself back through the drop-reconnect path. */
  const intentionalEndRef = useRef(false);
  const lastVoiceRef = useRef<number>(0);

  const phase: VoicePhase =
    status === "connected"
      ? peerSpeaking
        ? "speaking"
        : micSpeaking
          ? "listening"
          : Date.now() - lastVoiceRef.current < 6000
            ? "thinking"
            : "listening"
      : status === "connecting"
        ? "opening"
        : status === "error"
          ? "down"
          : "resting";

  useEffect(() => {
    onPhase?.(phase);
  }, [phase, onPhase]);

  /* Worker heartbeat, read once on mount. Only a real failure is
     surfaced; the resting heartbeat is the service breathing, not
     a warning. */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const w = await fetchWorker();
        if (!cancelled && w) setWorker(w);
      } catch {
        /* no heartbeat endpoint → the line behaves as it always has */
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
    (note: string = "Line closed. The room is yours again.") => {
      intentionalEndRef.current = true;
      roomRef.current?.disconnect();
      roomRef.current = null;
      clearAudioElements();
      setPeerSpeaking(false);
      setMicSpeaking(false);
      setAudioBlocked(false);
      setMuted(false);
      setSeconds(0);
      setStatus("idle");
      setMessage(note);
    },
    [clearAudioElements],
  );

  const toggleMute = useCallback(() => {
    const room = roomRef.current;
    if (!room || status !== "connected") return;
    const next = !muted;
    setMuted(next);
    void room.localParticipant.setMicrophoneEnabled(!next).catch(() => {
      setMuted(!next);
    });
  }, [muted, status]);

  /* Call clock and the two self-rest rules. */
  useEffect(() => {
    if (status !== "connected") return;
    const timer = window.setInterval(() => {
      setSeconds(Math.floor((Date.now() - connectedAtRef.current) / 1000));
      if (Date.now() - lastActivityRef.current > IDLE_TIMEOUT_MS) {
        endCall("Three quiet minutes, so I closed the line — your voice minutes are worth more than an open room.");
      } else if (Date.now() - connectedAtRef.current > HARD_CAP_MS) {
        endCall("Thirty minutes on one line is the cap. Start again whenever you like.");
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

  /* Expose the line's controls so the halo itself can start and
     end the call — the orb is the room, not a picture of it. The
     effect re-runs on every status/message change, so the ref
     always holds the current render's closures. */
  useEffect(() => {
    if (!linkRef) return;
    linkRef.current = {
      start: () => {
        setMuted(false);
        void startCall();
      },
      end: () => endCall(),
      toggleMute,
    };
    return () => {
      if (linkRef) linkRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [linkRef, endCall, toggleMute, status, message]);

  async function startCall() {
    /* TASK-VOI-032: the microphone's browser-side audio processing,
       pinned explicitly at every enable site instead of left to SDK
       defaults. Steady room noise (a fan) reaches Gemini's
       server-side activity detection, which — at the worker's start
       sensitivity — decides barge-in; the browser's noise
       suppression is the first filter in that chain, so it is
       stated here as a contract, not assumed. These are
       best-effort browser preferences, not guarantees: the
       worker-side sensitivity is the gate that decides, this only
       attenuates what reaches it. The mute toggle needs no options
       — it toggles the track these settings created. This const
       lives inside startCall on purpose: the startup-regression
       harness executes this function standalone from source, so
       anything it references must be defined in here. */
    const MIC_CAPTURE_OPTIONS = {
      noiseSuppression: true,
      echoCancellation: true,
      autoGainControl: true,
    };
    if (status === "connecting" || status === "connected") return;
    setStatus("connecting");
    setMessage("Reaching FRIDAY…");
    setPeerSpeaking(false);
    setMicSpeaking(false);
    setAudioBlocked(false);
    intentionalEndRef.current = false;

    /* A fresh room for every call. The old shared room collected
       one agent per call and left them talking to nobody; a new
       room gives each conversation exactly one agent and a clean
       lifecycle — when the call ends, the room empties. */
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
      /* playback warm-up is best-effort */
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
        if (peer || self) lastVoiceRef.current = Date.now();
        setPeerSpeaking(peer);
        setMicSpeaking(self);
        /* The first time FRIDAY actually speaks, the line stops
           announcing itself and simply becomes a conversation. */
        if (peer) {
          setMessage((current) => (current.startsWith("I'm listening") ? "We're talking — interrupt me any time." : current));
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
          /* diagnostics never block the conversation */
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
        setMessage("Line closed. The room is yours again.");
      };

      room.on(RoomEvent.Disconnected, async () => {
        /* A failed opening owns its own cleanup and its error —
           it was never a live session, so no reconnect, no overwrite. */
        if (startupFailed) return;
        if (!startupComplete) {
          startupDisconnected = true;
          return;
        }
        const duration = (Date.now() - sessionStartRef.current) / 1000;
        /* Intentional end: report the session and settle. A line
           the owner closed stays closed. */
        if (intentionalEndRef.current) {
          await settleClosed(duration);
          return;
        }
        if (reconnectAttempts < MAX_RECONNECT && Date.now() - lastActivityRef.current < IDLE_TIMEOUT_MS) {
          reconnectAttempts += 1;
          setStatus("connecting");
          setMessage(`The line stumbled — pulling it back (${reconnectAttempts}/${MAX_RECONNECT})…`);
          try {
            await new Promise((r) => window.setTimeout(r, 1000 * reconnectAttempts));
            if (!roomRef.current) {
              const fresh = new Room({ adaptiveStream: true, dynacast: true });
              await fresh.connect(body.server_url, body.token);
              await fresh.localParticipant.setMicrophoneEnabled(true, MIC_CAPTURE_OPTIONS);
              roomRef.current = fresh;
              connectedAtRef.current = Date.now();
              lastActivityRef.current = Date.now();
              setStatus("connected");
              setMessage("Back. Where were we?");
              return;
            }
          } catch {
            /* fall through to the honest closed path */
          }
        }
        await settleClosed(duration);
      });

      await room.connect(body.server_url, body.token);
      await room.localParticipant.setMicrophoneEnabled(true, MIC_CAPTURE_OPTIONS);
      if (startupDisconnected) throw new Error("The line dropped while it was opening. Try again.");

      startupComplete = true;
      roomRef.current = room;
      connectedAtRef.current = Date.now();
      lastActivityRef.current = Date.now();
      sessionIdRef.current = `voice-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      sessionStartRef.current = Date.now();
      setSeconds(0);
      setStatus("connected");
      setMessage("I'm listening — give me a second to say hello first.");
    } catch (error) {
      const reason = error instanceof Error ? error.message : "The voice line couldn't open.";
      startupFailed = true;
      intentionalEndRef.current = true;
      /* roomRef is only assigned once the mic publishes; the
         locally allocated room is cleaned up either way, and a
         cleanup failure never masks the original error. */
      try {
        await room.disconnect();
      } catch {
        /* keep the original error */
      }
      roomRef.current = null;
      clearAudioElements();
      setStatus("error");
      setMessage(
        reason.includes("permission") || reason.toLowerCase().includes("denied")
          ? "Mic permission denied — your browser blocked the microphone. Allow it for this site, then start again."
          : reason,
      );
    }
  }

  return (
    <div className="voice-cluster">
      <p className="voice-state" aria-live="polite">
        <span className="voice-line-text">{message}</span>
        {status === "connected" && (
          <span className="voice-clock">
            <span className="voice-dot" aria-hidden="true" />
            {durationClock(seconds)}
          </span>
        )}
      </p>

      {workerFailed && status === "idle" && (
        <p className="voice-warning" role="alert">
          The voice service isn&apos;t answering right now: {worker?.detail || worker?.state}
        </p>
      )}

      <div className="voice-actions">
        <button
          type="button"
          className={`voice-main ${status === "connected" ? "is-live" : ""}`}
          onClick={() => {
            if (status === "connected") {
              endCall();
            } else {
              setMuted(false);
              void startCall();
            }
          }}
          disabled={status === "connecting" || (workerFailed && status === "idle")}
          aria-label={status === "connected" ? "End the voice call" : "Start a voice call with FRIDAY"}
        >
          {status === "connecting" ? (
            <>
              <Radio size={16} className="spin" aria-hidden="true" /> Connecting
            </>
          ) : status === "connected" ? (
            <>
              <PhoneOff size={16} aria-hidden="true" /> End the line
            </>
          ) : (
            <>
              <PhoneCall size={16} aria-hidden="true" /> Start the line
            </>
          )}
        </button>

        {status === "connected" && (
          <button
            type="button"
            className={`voice-mute ${muted ? "is-muted" : ""}`}
            onClick={toggleMute}
            aria-label={muted ? "Unmute the microphone" : "Mute the microphone"}
            aria-pressed={muted}
          >
            {muted ? <MicOff size={16} aria-hidden="true" /> : <Mic size={16} aria-hidden="true" />}
            {muted ? "Muted" : "Mute"}
          </button>
        )}
      </div>

      {audioBlocked && (
        <p className="voice-note">Your browser is holding the sound back — tap once anywhere, then start again.</p>
      )}
      <p className="voice-note">The mic stays open for the whole conversation. English and Telugu both work.</p>
    </div>
  );
}
