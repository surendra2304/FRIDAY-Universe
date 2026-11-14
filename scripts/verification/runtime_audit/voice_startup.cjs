/* Offline regressions executing the ACTUAL VoiceCall.tsx startCall function.
 * No network, voice provider, owner audio or cloud credentials are used.
 */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const esbuild = require('esbuild');

const sourcePath = process.env.VOICE_CALL_SOURCE || path.resolve(__dirname, '../../../FRIDAY/ui/components/VoiceCall.tsx');
const source = fs.readFileSync(sourcePath, 'utf8');
const start = source.indexOf('  async function startCall() {');
const end = source.indexOf('\n  return (', start);
assert(start >= 0 && end > start, 'Actual source boundary changed; inspect the harness, never substitute a mirror');
const js = esbuild.transformSync(source.slice(start, end), { loader: 'ts', format: 'cjs' }).code;

async function scenario(name) {
  const rooms = [];
  let status = 'idle', message = '', diagnosticPosts = 0;
  const noop = () => {};
  const roomRef = { current: null };
  const intentionalEndRef = { current: false };
  class Room {
    constructor() {
      this.connected = false;
      this.disconnects = 0;
      this.events = new Map();
      this.localParticipant = { setMicrophoneEnabled: async () => {
        if (['microphone_denied', 'cleanup_failure'].includes(name)) throw Error('Permission denied');
        if (name === 'microphone_missing') throw Error('Requested device not found');
        if (name === 'startup_disconnect_without_rejection') {
          this.connected = false;
          await this.events.get('Disconnected')?.();
        }
      } };
      rooms.push(this);
    }
    async startAudio() {}
    on(event, handler) { this.events.set(event, handler); return this; }
    async connect(url, token) {
      assert.equal(url, 'wss://fixture.invalid');
      assert.equal(token, 'offline-fixture-token');
      if (name === 'connect_failure') throw Error('Connection failed');
      if (name === 'startup_disconnect') {
        await this.events.get('Disconnected')?.();
        throw Error('Connection failed during startup');
      }
      this.connected = true;
    }
    async disconnect() {
      this.disconnects++;
      this.connected = false;
      await this.events.get('Disconnected')?.();
      if (name === 'cleanup_failure') throw Error('Cleanup failed');
    }
  }
  const context = vm.createContext({
    Error, Room, status,
    RoomEvent: new Proxy({}, { get: (_, key) => String(key) }),
    Track: { Kind: { Audio: 'audio' } },
    crypto: { randomUUID: () => 'offline-fixture-uuid' },
    roomRef, intentionalEndRef,
    lastActivityRef: { current: Date.now() }, connectedAtRef: { current: 0 },
    sessionIdRef: { current: '' }, sessionStartRef: { current: Date.now() },
    setStatus: value => { status = value; }, setMessage: value => { message = value; },
    setPeerSpeaking: noop, setMicSpeaking: noop, setAudioBlocked: noop, setSeconds: noop,
    requestJson: async () => {
      if (name === 'token_failure') throw Error('Token endpoint unavailable');
      return { server_url: 'wss://fixture.invalid', token: 'offline-fixture-token' };
    },
    clearAudioElements: noop, IDLE_TIMEOUT_MS: 180000, HARD_CAP_MS: 1800000,
    window: { setTimeout: fn => { fn(); return 0; } },
    document: { querySelectorAll: () => [] }, apiBase: () => '',
    fetch: async () => { diagnosticPosts++; return { ok: true }; },
    console, Date, Math,
  });
  vm.runInContext(js + '\nglobalThis.runActualStartCall = startCall;', context);
  await context.runActualStartCall();
  await Promise.resolve();
  const failures = ['microphone_denied', 'microphone_missing', 'token_failure', 'connect_failure', 'startup_disconnect', 'startup_disconnect_without_rejection', 'cleanup_failure'];
  if (failures.includes(name)) {
    assert.equal(status, 'error', name + ': preserve the real setup error');
    assert.equal(rooms.length, 1, name + ': never resurrect a failed startup');
    assert.equal(rooms[0].disconnects, 1, name + ': disconnect the locally allocated room');
    assert.equal(rooms[0].connected, false, name + ': no connected room after successful cleanup');
    assert.equal(roomRef.current, null, name + ': no dangling component ref');
    assert.equal(diagnosticPosts, 0, name + ': not a completed voice session');
    if (name === 'cleanup_failure') assert.match(message, /Mic permission denied/, 'Cleanup must not mask the original error');
  } else {
    assert.equal(status, 'connected');
    assert.equal(roomRef.current, rooms[0]);
    if (name === 'intentional_end') {
      intentionalEndRef.current = true;
      await rooms[0].disconnect();
      assert.equal(status, 'idle');
      assert.equal(rooms.length, 1, 'Intentional End must not reconnect');
      assert.equal(diagnosticPosts, 1, 'A real established session still posts diagnostics');
    }
  }
  return { name, state: 'passed', rooms_created: rooms.length, disconnect_calls: rooms[0].disconnects, diagnostic_posts: diagnosticPosts };
}

(async () => {
  const tests = [];
  for (const name of ['microphone_denied', 'microphone_missing', 'token_failure', 'connect_failure', 'startup_disconnect', 'startup_disconnect_without_rejection', 'cleanup_failure', 'successful_startup', 'intentional_end']) {
    tests.push(await scenario(name));
  }
  console.log(JSON.stringify({ state: 'passed', network_calls: 0, owner_audio_accepted: false, source_sha256: crypto.createHash('sha256').update(source).digest('hex'), tests }, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
