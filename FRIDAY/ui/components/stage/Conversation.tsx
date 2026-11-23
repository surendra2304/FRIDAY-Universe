"use client";

import { ArrowUp } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import ShinyText from "../reactbits/ShinyText";
import { ControlGate } from "../ControlGate";
import { CHAT_CEILING_MS, clockTime, fetchHistory, sendChat } from "@/lib/wire";
import { hasStoredControlKey, isControlAuthError, startControlSessionRefresh } from "@/lib/controlSession";

/* ================================================================
   The stream — the written half of the conversation, living
   under the halo on the same stage as the voice line.

   On load it picks the thread back up from the durable history
   (newest twenty exchanges, oldest first, forty bubbles at
   most), so a reload is a pause, never an amnesia. Sending rides
   the five-minute chat ceiling that the backend contract sets;
   a send that outlives it says so honestly instead of hanging.
   ================================================================ */

const RESTORE_LIMIT = 20;
const MAX_BUBBLES = 40;

interface Bubble {
  id: string;
  role: "owner" | "friday";
  text: string;
  at: number;
  error?: boolean;
}

let bubbleSeq = 0;
function nextId(): string {
  bubbleSeq += 1;
  return `b-${Date.now()}-${bubbleSeq}`;
}

export function Conversation({
  onBusyChange,
  composerRef,
}: {
  onBusyChange?: (busy: boolean) => void;
  composerRef?: RefObject<HTMLTextAreaElement | null>;
}) {
  const [bubbles, setBubbles] = useState<Bubble[]>([]);
  const [restored, setRestored] = useState(false);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  /* TASK-FRD-038: the paste-once key gate, raised when a chat call
     answers 401 — "required" when this browser holds no key,
     "rejected" when the stored key was refused. */
  const [gateReason, setGateReason] = useState<"required" | "rejected" | null>(null);
  const streamRef = useRef<HTMLDivElement | null>(null);
  const localComposerRef = useRef<HTMLTextAreaElement | null>(null);
  const textareaRef = composerRef ?? localComposerRef;

  /* Keep a stored session warm across the visit, so the first send
     after the 20-minute TTL does not pay a mint round-trip. */
  useEffect(() => {
    if (hasStoredControlKey()) void startControlSessionRefresh();
  }, []);

  /* Restore the durable thread once, on mount. */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const entries = await fetchHistory(RESTORE_LIMIT);
        if (cancelled || entries.length === 0) return;
        const restoredBubbles: Bubble[] = [];
        for (const entry of [...entries].reverse()) {
          const at = new Date(entry.timestamp).getTime() || Date.now();
          if (entry.user_input) restoredBubbles.push({ id: nextId(), role: "owner", text: entry.user_input, at });
          if (entry.friday_reply) restoredBubbles.push({ id: nextId(), role: "friday", text: entry.friday_reply, at });
        }
        if (!cancelled && restoredBubbles.length > 0) {
          setBubbles(restoredBubbles.slice(-MAX_BUBBLES));
          setRestored(true);
        }
      } catch {
        /* history unreachable → a fresh thread, not an error wall */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* Keep the newest words in view. */
  useEffect(() => {
    const el = streamRef.current;
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [bubbles, busy]);

  const send = useCallback(async () => {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setBusy(true);
    onBusyChange?.(true);
    const ownerBubble: Bubble = { id: nextId(), role: "owner", text, at: Date.now() };
    setBubbles((current) => [...current, ownerBubble].slice(-MAX_BUBBLES));
    try {
      const reply = await sendChat(text);
      const answer = typeof reply?.reply === "string" && reply.reply.trim() ? reply.reply : "…";
      const fridayBubble: Bubble = { id: nextId(), role: "friday", text: answer, at: Date.now() };
      setBubbles((current) => [...current, fridayBubble].slice(-MAX_BUBBLES));
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "AbortError";
      const reason = error instanceof Error ? error.message : "unknown";
      /* TASK-FRD-038: a 401 is not a lost link — it is the key gate.
         Raise the paste-once prompt instead of a generic failure. */
      if (isControlAuthError(error)) {
        const rejected = error.code === "control-key-rejected";
        setGateReason(rejected ? "rejected" : "required");
        const errorBubble: Bubble = {
          id: nextId(),
          role: "friday",
          error: true,
          at: Date.now(),
          text: rejected
            ? "That key was rejected, so I can't answer from this browser yet. Paste the current key below."
            : "I need the owner key in this browser before I can answer. Paste it once below.",
        };
        setBubbles((current) => [...current, errorBubble].slice(-MAX_BUBBLES));
        return;
      }
      const errorBubble: Bubble = {
        id: nextId(),
        role: "friday",
        error: true,
        at: Date.now(),
        text: timedOut
          ? `No answer inside ${Math.round(CHAT_CEILING_MS / 1000)} seconds. FRIDAY may still finish it in the background — if it does, the reply lands in this thread's history.`
          : `That didn't get through (${reason}). Nothing was passed on — send it again when you're ready.`,
      };
      setBubbles((current) => [...current, errorBubble].slice(-MAX_BUBBLES));
    } finally {
      setBusy(false);
      onBusyChange?.(false);
    }
  }, [draft, busy, onBusyChange]);

  return (
    <section className="stream-wrap" aria-label="Conversation">
      <div className="stream" ref={streamRef}>
        {bubbles.length === 0 && !busy && (
          <p className="stream-empty">
            Nothing here yet. Start the line and speak, or write the first thing below — either way, it lands in
            the same conversation.
          </p>
        )}
        {restored && bubbles.length > 0 && <div className="stream-divider">Picked up from before</div>}
        {bubbles.map((bubble) => (
          <article key={bubble.id} className={`bubble ${bubble.role}${bubble.error ? " is-error" : ""}`}>
            <p className="bubble-text">{bubble.text}</p>
            <time className="bubble-time" dateTime={new Date(bubble.at).toISOString()}>
              {clockTime(bubble.at)}
            </time>
          </article>
        ))}
        {busy && (
          <p className="stream-working" aria-live="polite">
            <ShinyText text="FRIDAY is on it…" speed={2.4} />
          </p>
        )}
      </div>

      {gateReason && <ControlGate reason={gateReason} onConnected={() => setGateReason(null)} />}

      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          ref={textareaRef}
          className="composer-input"
          rows={1}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          placeholder="Write it instead…"
          aria-label="Write a message to FRIDAY"
        />
        <button type="submit" className="composer-send" disabled={busy || draft.trim().length === 0} aria-label="Send message">
          <ArrowUp size={18} aria-hidden="true" />
        </button>
      </form>
    </section>
  );
}
