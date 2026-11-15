#!/usr/bin/env python3
"""TASK-FRD-005 — render the fixed battery utterances once.

Reads battery.json, synthesises every turn's prompt with edge-tts
(voice + rate pinned in the battery) and converts to 24000 Hz mono
s16 WAV — the format participant.py publishes. Writes a manifest
with the sha256 of every WAV; if the manifest already matches the
battery (same texts, voice, rate, battery_version) the existing
WAVs are reused untouched, so every acceptance run speaks
byte-identical prompts and runs are comparable.

Requires: edge-tts, and PyAV (bundled with livekit-agents on
Server 1) or an ffmpeg binary for the mp3 -> WAV conversion.
Run: /opt/friday_universe/venv/bin/python make_utterances.py \
         --battery battery.json --out-dir /tmp/frd005/utterances
"""
import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import wave

import edge_tts


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def battery_fingerprint(battery):
    payload = {
        "battery_version": battery["battery_version"],
        "tts": battery["tts"],
        "texts": [t["text"] for t in battery["turns"]],
        "ids": [t["id"] for t in battery["turns"]],
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


async def render_one(text, voice, rate, mp3_path):
    await edge_tts.Communicate(text, voice, rate=rate).save(mp3_path)


def convert(mp3_path, wav_path, sample_rate):
    """Decode mp3 to WAV at the battery sample rate, mono s16.

    Prefers PyAV (its bundled ffmpeg libraries are present wherever
    livekit-agents is installed — Server 1 has no ffmpeg binary);
    falls back to an ffmpeg binary when PyAV is unavailable.
    """
    try:
        import av
        from av.audio.resampler import AudioResampler
    except ImportError:
        av = None
    if av is not None:
        resampler = AudioResampler(
            format="s16", layout="mono", rate=sample_rate)
        pcm = bytearray()
        with av.open(mp3_path) as container:
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    pcm.extend(out.to_ndarray().tobytes())
            for out in resampler.resample(None):
                pcm.extend(out.to_ndarray().tobytes())
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sample_rate)
            w.writeframes(bytes(pcm))
        return
    subprocess.run(
        [
            "ffmpeg", "-y", "-v", "error", "-i", mp3_path,
            "-ar", str(sample_rate), "-ac", "1", "-f", "wav", wav_path,
        ],
        check=True,
    )


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    with open(args.battery, "r", encoding="utf-8") as fh:
        battery = json.load(fh)
    os.makedirs(args.out_dir, exist_ok=True)
    manifest_path = os.path.join(args.out_dir, "utterances_manifest.json")
    fingerprint = battery_fingerprint(battery)

    if not args.force and os.path.exists(manifest_path):
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        if manifest.get("fingerprint") == fingerprint and all(
            os.path.exists(os.path.join(args.out_dir, f"{tid}.wav"))
            and manifest["files"].get(tid) == sha256_file(
                os.path.join(args.out_dir, f"{tid}.wav")
            )
            for tid in manifest.get("files", {})
        ):
            print(f"utterances unchanged (fingerprint {fingerprint[:12]}); reusing")
            return 0

    tts = battery["tts"]
    files = {}
    for turn in battery["turns"]:
        mp3_path = os.path.join(args.out_dir, turn["id"] + ".mp3")
        wav_path = os.path.join(args.out_dir, turn["id"] + ".wav")
        await render_one(turn["text"], tts["voice"], tts["rate"], mp3_path)
        convert(mp3_path, wav_path, int(tts["sample_rate_hz"]))
        files[turn["id"]] = sha256_file(wav_path)
        print(f"rendered {turn['id']}: sha256 {files[turn['id']][:12]}")
    manifest = {
        "task": "TASK-FRD-005",
        "battery_version": battery["battery_version"],
        "fingerprint": fingerprint,
        "voice": tts["voice"],
        "rate": tts["rate"],
        "sample_rate_hz": tts["sample_rate_hz"],
        "files": files,
    }
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"manifest written: {manifest_path}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(asyncio.run(main()))
    except subprocess.CalledProcessError as exc:
        print(f"FATAL: ffmpeg conversion failed ({exc})", file=sys.stderr)
        raise SystemExit(2)
