/* Clock-rendering tests for lib/wire.ts (TASK-FRD-029).
   No test runner is configured in FRIDAY/ui; this file runs with plain
   Node (>= 22, native type stripping):  node lib/wire.test.ts
   It exits non-zero on the first failed expectation. */
import assert from "node:assert/strict";
import { activityFrameTime, clockTime, clockTimeOrBlank } from "./wire.ts";

// A full ISO instant renders as the fleet-zone wall clock either way.
// 2026-11-19T11:13:05Z is 16:43:05 in Asia/Kolkata (UTC+5:30).
assert.equal(clockTime("2026-11-19T11:13:05.000Z"), "16:43:05");
assert.equal(clockTimeOrBlank("2026-11-19T11:13:05.000Z"), "16:43:05");

// Epoch milliseconds (the activity socket's Date.now() fallback) parse.
assert.equal(clockTimeOrBlank(0), "05:30:00");

// The autonomous log's old bare time-of-day string has no date, so
// Date cannot parse it: clockTime keeps its placeholder for the
// callers that rely on it, clockTimeOrBlank renders nothing — the
// activity log must show no time rather than "--:--:--" (FRD-029).
assert.equal(clockTime("16:43:05"), "--:--:--");
assert.equal(clockTimeOrBlank("16:43:05"), "");

// Missing values: placeholder from clockTime, blank from the OrBlank.
assert.equal(clockTime(""), "--:--:--");
assert.equal(clockTime(null), "--:--:--");
assert.equal(clockTime(undefined), "--:--:--");
assert.equal(clockTimeOrBlank(""), "");
assert.equal(clockTimeOrBlank(null), "");
assert.equal(clockTimeOrBlank(undefined), "");

// TASK-FRD-030: the live-append clock for activity socket frames. A
// frame's recorded_at wins over its timestamp — in particular a frame
// whose timestamp is the backlog's bare time-of-day fallback still
// renders its real time when recorded_at rides along (the FRD-030 bug
// was live rows rendering blank while the seed path showed the time).
assert.equal(
  activityFrameTime({ recorded_at: "2026-11-19T11:13:05.000Z", timestamp: "16:43:05" }),
  "16:43:05",
);
assert.equal(activityFrameTime({ timestamp: "2026-11-19T11:13:05.000Z" }), "16:43:05");
// A legacy frame (no recorded_at, bare timestamp) honestly shows no time.
assert.equal(activityFrameTime({ timestamp: "16:43:05" }), "");
assert.equal(activityFrameTime({ recorded_at: "", timestamp: "16:43:05" }), "");
// A frame carrying no time at all falls back to its arrival time.
assert.match(activityFrameTime({}), /^\d{2}:\d{2}:\d{2}$/);

// TASK-FRD-038 checkpoint 2: sendChat carries the D-023 control session.
// The global fetch is stubbed per case; module state is reset between
// cases so no token or stored key leaks across them.
import { sendChat } from "./wire.ts";
import {
  CONTROL_KEY_STORAGE,
  CONTROL_SESSION_HEADER,
  ControlAuthError,
  clearControlSession,
  isControlAuthError,
  setControlSessionStorage,
  storeControlKey,
} from "./controlSession.ts";

{
  const realFetch = globalThis.fetch;
  const storage = new Map<string, string>();
  const fakeStorage = {
    getItem: (k: string) => (storage.has(k) ? storage.get(k)! : null),
    setItem: (k: string, v: string) => {
      storage.set(k, v);
    },
    removeItem: (k: string) => {
      storage.delete(k);
    },
  };

  type Route = (url: string, headers: Record<string, string>) => {
    status: number;
    body: unknown;
  };
  const installFetch = (route: Route) => {
    const calls: { url: string; headers: Record<string, string> }[] = [];
    globalThis.fetch = (async (url: string, init?: { headers?: Record<string, string> }) => {
      const headers = (init?.headers ?? {}) as Record<string, string>;
      calls.push({ url, headers });
      const res = route(url, headers);
      return {
        ok: res.status >= 200 && res.status < 300,
        status: res.status,
        statusText: res.status === 200 ? "OK" : "Unauthorized",
        json: async () => res.body,
        text: async () => JSON.stringify(res.body),
      };
    }) as typeof fetch;
    return calls;
  };

  const reset = () => {
    clearControlSession();
    storage.clear();
    setControlSessionStorage(fakeStorage);
  };

  const TOKEN_1 = "fcs1.1800001200.aaaa";
  const TOKEN_2 = "fcs1.1800001500.bbbb";
  const mintBody = (token: string) => ({
    status: "ok",
    token,
    expires_at: new Date(Date.now() + 1_200_000).toISOString(),
    ttl_seconds: 1200,
  });

  try {
    // 1. No key stored: the chat goes out bare (loopback works keyless)
    // and a 401 raises the gate instead of a generic error.
    reset();
    let calls = installFetch((url) => {
      if (url === "/api/chat") return { status: 200, body: { reply: "hello" } };
      throw new Error(`unexpected fetch ${url}`);
    });
    assert.equal((await sendChat("hi")).reply, "hello");
    assert.equal(calls.length, 1);
    assert.equal(calls[0].headers[CONTROL_SESSION_HEADER], undefined);

    reset();
    calls = installFetch(() => ({ status: 401, body: { error: "HTTP_401" } }));
    await assert.rejects(
      sendChat("hi"),
      (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-auth-required",
    );
    assert.equal(calls.length, 1); // no retry without a key to mint with

    // 2. Key stored: mint once, chat carries the token.
    reset();
    storeControlKey("owner-key");
    calls = installFetch((url, headers) => {
      if (url === "/api/control/session") {
        assert.equal(headers["x-friday-api-key"], "owner-key");
        return { status: 200, body: mintBody(TOKEN_1) };
      }
      assert.equal(headers[CONTROL_SESSION_HEADER], TOKEN_1);
      return { status: 200, body: { reply: "hello" } };
    });
    assert.equal((await sendChat("hi")).reply, "hello");
    assert.equal(calls.filter((c) => c.url === "/api/control/session").length, 1);
    assert.equal(calls.filter((c) => c.url === "/api/chat").length, 1);

    // 3. Stale token: chat 401s, a fresh mint retries once and succeeds.
    reset();
    storeControlKey("owner-key");
    let chats = 0;
    let mints = 0;
    calls = installFetch((url, headers) => {
      if (url === "/api/control/session") {
        mints += 1;
        return { status: 200, body: mintBody(mints === 1 ? TOKEN_1 : TOKEN_2) };
      }
      chats += 1;
      if (chats === 1) return { status: 401, body: { error: "HTTP_401" } };
      assert.equal(headers[CONTROL_SESSION_HEADER], TOKEN_2);
      return { status: 200, body: { reply: "hello again" } };
    });
    assert.equal((await sendChat("hi")).reply, "hello again");
    assert.equal(mints, 2);
    assert.equal(chats, 2);

    // 4. The stored key is refused at mint time: no chat attempt, the
    // gate learns the key itself is wrong.
    reset();
    storeControlKey("wrong-key");
    calls = installFetch((url) => {
      if (url === "/api/control/session") return { status: 401, body: {} };
      throw new Error(`unexpected fetch ${url}`);
    });
    await assert.rejects(
      sendChat("hi"),
      (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-key-rejected",
    );
    assert.equal(calls.filter((c) => c.url === "/api/chat").length, 0);

    // 5. A 401 that survives the refresh means the key is rejected.
    reset();
    storeControlKey("owner-key");
    calls = installFetch((url) => {
      if (url === "/api/control/session") return { status: 200, body: mintBody(TOKEN_1) };
      return { status: 401, body: { error: "HTTP_401" } };
    });
    await assert.rejects(
      sendChat("hi"),
      (e: unknown) => isControlAuthError(e) && (e as ControlAuthError).code === "control-key-rejected",
    );
    assert.equal(calls.filter((c) => c.url === "/api/chat").length, 2);
    assert.equal(storage.get(CONTROL_KEY_STORAGE), "owner-key"); // the key stays stored; the gate clears it on a fresh paste
  } finally {
    globalThis.fetch = realFetch;
    clearControlSession();
    setControlSessionStorage(null);
  }
}

console.log("wire.test.ts: all expectations passed");
