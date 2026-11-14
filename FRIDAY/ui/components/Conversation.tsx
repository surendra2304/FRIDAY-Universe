"use client";

import { AlertTriangle, Eraser, Loader2, RotateCcw, Send } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, requestJson } from "@/lib/api";
import { prefersReducedMotion } from "./fx";

/* ============================================================
   The written half of the Talk screen — the same conversation
   the voice line speaks from. One brain, two mouths: anything
   typed here is answered by the identical pipeline that routes
   work to the ten-agent crew.

   Behaviour carried over unchanged from the previous console:
   - POST /api/chat {message}, with a 300-second client ceiling
     matched to the server budget — long delegations (a Forge
     build can run for minutes) are waited out, never abandoned
     mid-flight and misreported as failures.
   - The tail of the previous session is restored from
     GET /api/v1/conversation/history on load, so a reload never
     greets the owner with amnesia. (TASK-REL-029 is making that
     store survive restarts; the endpoint contract is unchanged.)
   - Transport failures render as a plain-language notice with
     a one-tap resend, and proactive alerts arrive via response
     metadata — never glued onto the answer text.
   ============================================================ */

const STARTERS = ["Crew status", "What do you remember about me?", "Stratex portfolio status", "Today's important news"];

/** Render cap in bubbles — the thread stays a conversation, not an archive. */
const MAX_RENDERED = 40;
/**
 * Restore window in ENTRIES (one entry = one exchange = up to two
 * bubbles). Invariant kept from the old console: RESTORE_LIMIT × 2
 * must cover MAX_RENDERED, or the fetch silently becomes the cap.
 */
const RESTORE_LIMIT = 20;
/** Client ceiling for one /api/chat round-trip (matches the server's 300s). */
const CHAT_TIMEOUT_MS = 300_000;

type ThreadMessage = ChatMessage & {
  /** Arrived during this session → eligible for the reveal effect. */
  live?: boolean;
  /** For error notices: the user text a resend should repeat. */
  retryOf?: string;
};

function appendCapped(current: ThreadMessage[], next: ThreadMessage[]): ThreadMessage[] {
  return [...current, ...next].slice(-MAX_RENDERED);
}

/** Progressive reveal for a live reply — one rAF pass, tap to complete,
    full text always present for assistive tech. */
function RevealText({ text, live }: { text: string; live?: boolean }) {
  const [count, setCount] = useState(live ? 0 : text.length);
  const done = count >= text.length;

  useEffect(() => {
    if (!live || prefersReducedMotion()) {
      setCount(text.length);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const duration = Math.min(1400, 260 + text.length * 3.2);
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration);
      setCount(Math.floor(text.length * (1 - Math.pow(1 - p, 2))));
      if (p < 1) raf = requestAnimationFrame(tick);
      else setCount(text.length);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [text, live]);

  if (done) return <>{text}</>;
  return (
    <span onClick={() => setCount(text.length)} title="Tap to show the whole reply">
      <span aria-hidden="true">
        {text.slice(0, count)}
        <span className="caret" />
      </span>
      <span className="sr-only">{text}</span>
    </span>
  );
}

export function Conversation({ prefill }: { prefill?: { text: string; seq: number } }) {
  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [restoredCount, setRestoredCount] = useState(0);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  /* Restore the previous session's tail on mount. Silence on failure
     is correct here: a fresh install simply has nothing to restore. */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await requestJson<{
          entries?: Array<{ user_input?: string; friday_reply?: string; timestamp?: string }>;
        }>("/api/v1/conversation/history?limit=" + RESTORE_LIMIT);
        if (cancelled || !res.entries?.length) return;
        const restored: ThreadMessage[] = [];
        for (const e of [...res.entries].reverse()) {
          const at = e.timestamp ? new Date(e.timestamp).getTime() : Date.now();
          if (e.user_input?.trim()) restored.push({ role: "user", text: e.user_input, at });
          if (e.friday_reply?.trim()) restored.push({ role: "friday", text: e.friday_reply, at });
        }
        const capped = restored.slice(-MAX_RENDERED);
        if (capped.length) {
          setMessages(capped);
          setRestoredCount(capped.length);
        }
      } catch {
        /* history unavailable → a fresh thread, not an error surface */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  /* External prefill (a "direct a task" tap on a Crew tile): fill the
     composer and focus it in place — never scroll the page. */
  useEffect(() => {
    if (!prefill || prefill.seq === 0) return;
    setInput((current) => (current.trim() ? current : prefill.text));
    requestAnimationFrame(() => inputRef.current?.focus());
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill?.seq]);

  /* Composer auto-grow, capped by the stylesheet. */
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 130)}px`;
  }, [input]);

  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => {
      const el = scrollRef.current;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }, []);

  useEffect(() => {
    scrollToEnd();
  }, [messages, busy, scrollToEnd]);

  async function send(text: string) {
    const clean = text.trim();
    if (!clean || busy) return;
    setBusy(true);
    setInput("");
    setMessages((current) => appendCapped(current, [{ role: "user", text: clean, at: Date.now() }]));
    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), CHAT_TIMEOUT_MS);
    try {
      const result = await requestJson<{
        reply?: string;
        mode?: string;
        metadata?: { proactive_notice?: string | null };
      }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: clean }),
        signal: controller.signal,
      });
      const answer = result.reply || result.mode || "FRIDAY took that in.";
      setMessages((current) => appendCapped(current, [{ role: "friday", text: answer, at: Date.now(), live: true }]));
      /* Proactive alerts ride in metadata and render as a dismissible
         strip — the answer text itself stays clean. */
      setNotice(result.metadata?.proactive_notice ?? null);
    } catch (error) {
      const timedOut = error instanceof DOMException && error.name === "AbortError";
      const reason = timedOut
        ? `No answer inside ${Math.round(CHAT_TIMEOUT_MS / 1000)} seconds. FRIDAY may still be working on it — long jobs finish in the background, and the reply lands in this conversation's history.`
        : error instanceof Error
          ? error.message
          : "FRIDAY couldn't be reached.";
      setMessages((current) =>
        appendCapped(current, [{ role: "friday", text: reason, at: Date.now(), error: true, retryOf: clean }]),
      );
    } finally {
      window.clearTimeout(timer);
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void send(input);
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void send(input);
    }
  }

  const clock = (at: number) =>
    hydrated ? new Date(at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : "";

  return (
    <div className="convo" id="convo">
      <div className="convo-head">
        <span className="convo-title">The conversation</span>
        <button
          type="button"
          className="ghost-btn"
          onClick={() => {
            setMessages([]);
            setRestoredCount(0);
            setNotice(null);
          }}
          disabled={messages.length === 0}
          title="Clear what's on screen — FRIDAY keeps the memory itself"
          aria-label="Clear the on-screen conversation"
        >
          <Eraser size={13} /> Clear view
        </button>
      </div>

      {notice && (
        <div className="convo-notice" role="status">
          <span>{notice}</span>
          <button type="button" onClick={() => setNotice(null)} aria-label="Dismiss this notice">
            Dismiss
          </button>
        </div>
      )}

      <div className="convo-scroll" ref={scrollRef}>
        {restoredCount > 0 && (
          <div className="convo-divider" aria-label="Restored conversation history">
            from earlier · {restoredCount} messages
          </div>
        )}
        {messages.length === 0 && (
          <div className="convo-empty">
            <h3>Or write it here.</h3>
            <p>
              Questions, orders, half-formed ideas — all read the same way. Anything I hand to the crew comes back in this
              thread, and lands in the Record.
            </p>
          </div>
        )}
        {messages.map((m, i) =>
          m.error ? (
            <div className="sys-note" role="alert" key={i}>
              <AlertTriangle size={15} className="sys-note-icon" aria-hidden="true" />
              <div className="sys-note-body">
                <strong>That one didn&apos;t land</strong>
                <code>{m.text}</code>
              </div>
              {m.retryOf && (
                <button
                  type="button"
                  className="ghost-btn"
                  onClick={() => void send(m.retryOf!)}
                  disabled={busy}
                  aria-label="Send the failed message again"
                >
                  <RotateCcw size={12} /> Send again
                </button>
              )}
            </div>
          ) : m.role === "user" ? (
            <div key={i} className="line user">
              <div className="line-text">{m.text}</div>
              <div className="line-meta">You · {clock(m.at)}</div>
            </div>
          ) : (
            <div key={i} className="line friday">
              <div className="line-head">
                <span className="line-who">FRIDAY</span>
                <span className="line-time">{clock(m.at)}</span>
              </div>
              <div className="line-text">
                <RevealText text={m.text} live={m.live} />
              </div>
            </div>
          ),
        )}
        {busy && (
          <div className="thinking" aria-live="polite">
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="thinking-dot" />
            <span className="thinking-word">FRIDAY is on it</span>
          </div>
        )}
      </div>

      <form className="composer" onSubmit={onSubmit}>
        {messages.length === 0 && (
          <div className="composer-starters">
            <span className="starters-label">Start with</span>
            {STARTERS.map((chip) => (
              <button type="button" key={chip} className="starter" onClick={() => void send(chip)}>
                {chip}
              </button>
            ))}
          </div>
        )}
        <div className="composer-row">
          <textarea
            ref={inputRef}
            className="composer-input"
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Write to FRIDAY…"
            aria-label="Write to FRIDAY"
            disabled={busy}
          />
          <button type="submit" className="send-btn" disabled={busy || !input.trim()} aria-label="Send">
            {busy ? <Loader2 size={17} className="spin" /> : <Send size={17} />}
          </button>
        </div>
      </form>
    </div>
  );
}
