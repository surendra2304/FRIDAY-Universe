"use client";

import { Loader2, MessageSquareText, Send, Sparkles } from "lucide-react";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import { ChatMessage, requestJson } from "@/lib/api";

/* ============================================================
   FRIDAY chat — talks to the friend-persona /api/chat pipeline
   (the same engine that routes to the 10-agent fleet).
   ============================================================ */

const CHIPS = [
  "How's the fleet?",
  "Portfolio status",
  "Research this week's macro news",
  "Write me a script that renames my files by date",
];

export function ChatPanel({ prefill }: { prefill?: { text: string; seq: number } }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    setHydrated(true);
  }, []);

  /* external prefill (e.g. "Ask via chat" on an agent card) */
  useEffect(() => {
    if (!prefill || prefill.seq === 0) return;
    setInput((current) => (current.trim() ? current : prefill.text));
    requestAnimationFrame(() => {
      inputRef.current?.focus();
      inputRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefill?.seq]);

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
    setMessages((current) => [...current, { role: "user", text: clean, at: Date.now() }]);
    try {
      const result = await requestJson<{ reply?: string; mode?: string }>("/api/chat", {
        method: "POST",
        body: JSON.stringify({ message: clean }),
      });
      const answer = result.reply || result.mode || "FRIDAY accepted the message.";
      setMessages((current) => [...current, { role: "friday", text: answer, at: Date.now() }]);
    } catch (error) {
      const reason = error instanceof Error ? error.message : "FRIDAY could not be reached.";
      setMessages((current) => [...current, { role: "friday", text: reason, at: Date.now(), error: true }]);
    } finally {
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

  return (
    <div className="panel" id="chat">
      <div className="panel-head">
        <div className="panel-title">
          <div className="title-icon cyan">
            <MessageSquareText size={17} />
          </div>
          <div>
            <h3>Chat with FRIDAY</h3>
            <span className="subtitle">Same brain as voice — routes to the ten-agent fleet</span>
          </div>
        </div>
        <span style={{ fontSize: 11.5, color: "var(--faint)", letterSpacing: "0.14em", textTransform: "uppercase" }}>
          <Sparkles size={11} style={{ display: "inline", marginRight: 5, verticalAlign: -1 }} />
          Persona live
        </span>
      </div>

      <div className="chat-body">
        <div className="chat-scroll" ref={scrollRef}>
          {messages.length === 0 ? (
            <div className="chat-empty">
              <MessageSquareText size={30} />
              <p style={{ margin: 0, fontSize: 13.5 }}>
                Say anything — FRIDAY answers as your friend and coordinator,
                <br />
                and can dispatch real work to any agent in the fleet.
              </p>
            </div>
          ) : (
            messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "bubble user"
                    : m.error
                      ? "bubble friday error"
                      : "bubble friday"
                }
              >
                {m.text}
                <div className="bubble-meta">
                  {m.role === "user" ? "You" : "FRIDAY"} ·{" "}
                  {hydrated ? new Date(m.at).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" }) : ""}
                </div>
              </div>
            ))
          )}
          {busy && (
            <div className="typing-row panel" style={{ padding: "13px 18px" }}>
              <span className="typing-dot" />
              <span className="typing-dot" />
              <span className="typing-dot" />
            </div>
          )}
        </div>

        {messages.length === 0 && (
          <div className="chat-chips">
            {CHIPS.map((chip) => (
              <button key={chip} className="chip" onClick={() => void send(chip)}>
                {chip}
              </button>
            ))}
          </div>
        )}

        <form className="chat-input-row" onSubmit={onSubmit}>
          <textarea
            ref={inputRef}
            className="chat-input"
            rows={1}
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Message FRIDAY…"
            aria-label="Message FRIDAY"
            disabled={busy}
          />
          <button className="send-btn" type="submit" disabled={busy || !input.trim()} aria-label="Send message">
            {busy ? <Loader2 size={17} className="spin" /> : <Send size={17} />}
          </button>
        </form>
      </div>
    </div>
  );
}
