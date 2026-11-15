#!/usr/bin/env python3
"""TASK-FRD-005 voice acceptance participant.

Server-side LiveKit participant for FRIDAY's repeatable voice
acceptance harness. Joins a fresh room through FRIDAY's PRODUCTION
token endpoint (the real user path), stays silent for the greeting,
then speaks the fixed battery from battery.json (pre-rendered WAVs
from make_utterances.py) and records the agent's audio with
wall-clock timestamps so per-turn silence gaps can be measured.

Reply-end detection is deliberately conservative — the VOI-007/008
lesson: that run's participant mistook the Stratex answer's first
fragment plus a 0.10 s energy dip for the complete reply, published
the next question over FRIDAY, and Gemini Live's interruption
cancelled ~70% of the answer. Here a reply counts as ended only
after >= MIN_SPEECH_S of agent speech AND >= END_SILENCE_S of
continuous silence, so the harness can never truncate an answer
the way the VOI-007 participant did.

Run on Server 1 with the fleet venv python:
  /opt/friday_universe/venv/bin/python participant.py \
      --room friday-frd005-<run-id> --battery battery.json \
      --utter-dir /tmp/frd005/utterances --out-dir /tmp/frd005/runs/<run-id>

Outputs in --out-dir:
  <room>_timeline.json  events, per-turn gaps, speech clusters
  <room>_agent.wav      the agent's audio at its native rate
Exit code: 0 = call completed (the scorer judges quality),
           2 = infrastructure failure (token/connect/agent never joined).
"""
import argparse
import asyncio
import json
import os
import sys
import time
import wave

import httpx
from livekit import rtc

TOKEN_URL = "http://127.0.0.1:10000/api/livekit/token"
IDENTITY = "muse-frd005"
SAMPLE_RATE = 24000

GREETING_WAIT_S = 90.0      # max wait for FRIDAY to speak first
END_SILENCE_S = 2.0         # continuous silence that ends a reply
MIN_SPEECH_S = 0.8          # speech required before a reply can end
CLUSTER_GAP_S = 0.35        # frame gaps below this merge into one cluster
INTER_TURN_PAUSE_S = 1.0


def read_wav(path):
    with wave.open(path, "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getnchannels() != 1:
            raise SystemExit(
                f"utterance {path} is {w.getframerate()} Hz/"
                f"{w.getnchannels()} ch; battery requires "
                f"{SAMPLE_RATE} Hz mono (run make_utterances.py)"
            )
        return w.readframes(w.getnframes())


def speech_clusters(frames):
    """frames: list of (ts, nbytes) at ~10-20 ms spacing.
    Returns [(start_ts, end_ts)] merging gaps < CLUSTER_GAP_S."""
    clusters = []
    for ts, _ in frames:
        if clusters and ts - clusters[-1][1] < CLUSTER_GAP_S:
            clusters[-1][1] = ts
        else:
            clusters.append([ts, ts])
    return [(a, b) for a, b in clusters]


async def get_token(room):
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            TOKEN_URL, params={"room": room, "identity": IDENTITY}
        )
        data = resp.json()
    token = data.get("token")
    url = data.get("url") or data.get("ws_url") or data.get("server_url")
    if not token or not url:
        raise SystemExit(f"token endpoint shape unexpected: {sorted(data)}")
    return token, url


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room", required=True)
    ap.add_argument("--battery", required=True)
    ap.add_argument("--utter-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    with open(args.battery, "r", encoding="utf-8") as fh:
        battery = json.load(fh)
    os.makedirs(args.out_dir, exist_ok=True)
    room_name = args.room

    token, url = await get_token(room_name)
    room = rtc.Room()
    events = []

    def log(kind, detail=""):
        events.append((time.time(), kind, detail))
        print(f"{time.time():.3f} {kind} {detail}", flush=True)

    frames = []  # (ts, bytes) agent audio at native rate
    native_rate = [48000]
    agent_joined = asyncio.Event()

    @room.on("participant_connected")
    def _on_join(p):
        if p.identity != IDENTITY:
            log("agent_joined", p.identity)
            agent_joined.set()

    async def drain(track):
        stream = rtc.AudioStream(track)
        async for ev in stream:
            native_rate[0] = ev.frame.sample_rate
            frames.append((time.time(), bytes(ev.frame.data)))

    @room.on("track_subscribed")
    def _on_track(track, pub, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO and participant.identity != IDENTITY:
            log("agent_track", f"{track.sid} from {participant.identity}")
            asyncio.ensure_future(drain(track))

    await room.connect(url, token)
    connected_ts = time.time()
    log("connected", room_name)

    source = rtc.AudioSource(SAMPLE_RATE, 1)
    track = rtc.LocalAudioTrack.create_audio_track("mic", source)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    log("mic_published")

    try:
        await asyncio.wait_for(agent_joined.wait(), timeout=60)
    except asyncio.TimeoutError:
        log("agent_join_timeout")
        await room.disconnect()
        print("FATAL: agent never joined", file=sys.stderr)
        return 2

    async def wait_reply_end(since_idx, cap_s):
        """Wait until the reply that starts at/after frames[since_idx]
        ends: >= MIN_SPEECH_S of speech then >= END_SILENCE_S silence.
        Returns (first_frame_ts, last_frame_ts, speech_s)."""
        deadline = time.time() + cap_s
        while time.time() < deadline:
            window = frames[since_idx:]
            if window:
                clusters = speech_clusters(window)
                speech_s = sum(b - a for a, b in clusters)
                last_ts = window[-1][0]
                if speech_s >= MIN_SPEECH_S and time.time() - last_ts >= END_SILENCE_S:
                    return window[0][0], last_ts, speech_s
            await asyncio.sleep(0.15)
        window = frames[since_idx:]
        if not window:
            return None, None, 0.0
        clusters = speech_clusters(window)
        return window[0][0], window[-1][0], sum(b - a for a, b in clusters)

    # ---- greeting: FRIDAY speaks first -------------------------------
    greet_start_idx = len(frames)
    g_first, g_last, g_speech = await wait_reply_end(
        greet_start_idx, GREETING_WAIT_S
    )
    greeting = {
        "id": battery["greeting"]["id"],
        "connected_ts": connected_ts,
        "first_audio_ts": g_first,
        "gap_s": (g_first - connected_ts) if g_first else None,
        "speech_s": g_speech,
        "reply_end_ts": g_last,
    }
    log("greeting_done", f"gap={greeting['gap_s']}")

    # ---- battery turns -------------------------------------------------
    turns = []
    for turn in battery["turns"]:
        wav_path = os.path.join(args.utter_dir, turn["id"] + ".wav")
        raw = read_wav(wav_path)
        before = len(frames)
        log("utt_start", turn["id"])
        step = 240 * 2  # 10 ms of 24 kHz s16 mono
        for off in range(0, len(raw), step):
            part = raw[off:off + step]
            res = source.capture_frame(
                rtc.AudioFrame(
                    data=part,
                    sample_rate=SAMPLE_RATE,
                    num_channels=1,
                    samples_per_channel=len(part) // 2,
                )
            )
            if asyncio.iscoroutine(res):
                await res
        utt_end = time.time()
        log("utt_end", turn["id"])
        first, last, speech_s = await wait_reply_end(
            before, float(turn.get("reply_cap_s", 60))
        )
        record = {
            "id": turn["id"],
            "utt_end_ts": utt_end,
            "agent_start_ts": first,
            "gap_s": (first - utt_end) if first else None,
            "agent_end_ts": last,
            "speech_s": speech_s,
        }
        turns.append(record)
        log("turn_done", f"{turn['id']} gap={record['gap_s']}")
        await asyncio.sleep(INTER_TURN_PAUSE_S)

    await asyncio.sleep(2)
    if frames:
        with wave.open(
            os.path.join(args.out_dir, f"{room_name}_agent.wav"), "wb"
        ) as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(native_rate[0])
            for _, data in frames:
                w.writeframes(data)
    timeline = {
        "task": "TASK-FRD-005",
        "room": room_name,
        "battery_version": battery["battery_version"],
        "started_ts": connected_ts,
        "events": events,
        "greeting": greeting,
        "turns": turns,
        "audio_frames": len(frames),
        "native_rate": native_rate[0],
    }
    with open(
        os.path.join(args.out_dir, f"{room_name}_timeline.json"), "w"
    ) as fh:
        json.dump(timeline, fh, indent=1)
    print("SUMMARY " + json.dumps({"greeting": greeting, "turns": turns}))
    await room.disconnect()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except SystemExit:
        raise
    except Exception as exc:  # infrastructure failure, not a quality verdict
        print(f"FATAL: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(2)
