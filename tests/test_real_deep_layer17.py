"""
Real Deep Layer 17 Tests — debpalash/VoiceStudio → VyralX.

Functional tests for VyralX/app/agents/real_voice_studio.py:
stdlib DSP (radix-2 FFT, Hann window, mel scale), frame feature extraction,
pitch tracking, speaker embedding/verification, voice design from a text
brief, energy VAD, forced alignment, WER/CER, dubbing timeline fitting,
audiobook chaptering, streaming dictation, the language registry and VRAM
planning for local engines.
"""

import importlib.util
import math
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_voice_studio.py")

spec = importlib.util.spec_from_file_location("real_voice_studio", MODULE_PATH)
vs = importlib.util.module_from_spec(spec)
sys.modules["real_voice_studio"] = vs
spec.loader.exec_module(vs)


SR = 16000


def tone(freq: float, seconds: float, sr: int = SR, amp: float = 0.6) -> list[float]:
    """A harmonic-rich tone: good enough for FFT/pitch/VAD exercises."""
    return [amp * sum(a * math.sin(2 * math.pi * freq * h * i / sr)
                      for h, a in enumerate((1.0, 0.4, 0.2), start=1))
            for i in range(int(seconds * sr))]


def noise(seconds: float, sr: int = SR, amp: float = 0.05, seed: int = 1) -> list[float]:
    state = seed
    out = []
    for _ in range(int(seconds * sr)):
        state = (1103515245 * state + 12345) & 0x7FFFFFFF
        out.append(amp * (state / 0x7FFFFFFF * 2 - 1))
    return out


@pytest.fixture()
def extractor():
    return vs.FeatureExtractor()


# ── DSP primitives ───────────────────────────────────────────────────────────

def test_fft_matches_the_dft_of_a_short_signal():
    result = vs.fft([1.0, 0.0, -1.0, 0.0])
    assert [round(abs(value), 4) for value in result] == [0.0, 2.0, 1.4142, 1.4142]
    # a constant signal has energy only in bin 0
    dc = vs.fft([1.0] * 8)
    assert round(abs(dc[0]), 6) == pytest.approx(8.0)
    assert all(round(abs(value), 6) == 0.0 for value in dc[1:])


def test_hann_window_shape():
    window = vs.hann_window(4)
    assert [round(value, 3) for value in window] == [0.0, 0.75, 0.75, 0.0]
    assert vs.hann_window(1) == pytest.approx([1.0])
    assert max(vs.hann_window(64)) <= 1.0


def test_mel_scale_roundtrip():
    assert vs.hz_to_mel(1000) == pytest.approx(999.986, abs=1e-3)
    assert vs.mel_to_hz(1000) == pytest.approx(1000.022, abs=1e-3)
    assert vs.mel_to_hz(vs.hz_to_mel(440.0)) == pytest.approx(440.0, abs=1e-6)


# ── feature extraction ───────────────────────────────────────────────────────

def test_frame_features(extractor):
    frames = extractor.extract(tone(120.0, 2.0))
    assert len(frames) == 198
    frame = frames[10]
    assert frame.start_s == pytest.approx(0.1)
    assert frame.db == pytest.approx(18.08, abs=1e-2)
    assert frame.centroid_hz == pytest.approx(432.3, abs=1.0)
    assert len(frame.mel) == 24
    assert 0.0 <= frame.zcr <= 1.0
    assert frame.is_silent is False
    row = frame.to_dict()
    assert set(row) >= {"start_s", "energy", "db", "zcr", "centroid_hz"}


def test_frame_times_and_spectrum(extractor):
    signal = tone(120.0, 0.5)
    times = extractor.frame_times(signal)
    assert times[0] == 0.0 and times[1] == pytest.approx(0.01)
    assert len(times) == len(extractor.extract(signal))
    assert len(extractor.spectrum(tone(120.0, 0.025))) == 257


def test_silence_frames_are_flagged(extractor):
    frames = extractor.extract(noise(0.5, amp=0.00001))
    assert frames
    assert all(frame.is_silent for frame in frames[:5])


def test_pitch_tracking():
    tracker = vs.PitchTracker()
    pitches = tracker.track(tone(120.0, 2.0))
    stats = tracker.stats(pitches)
    assert stats["mean_f0"] == pytest.approx(120.12, abs=0.5)
    assert stats["stdev_f0"] < 2.0
    assert stats["voiced_ratio"] == pytest.approx(1.0)
    assert stats["min_f0"] <= stats["mean_f0"] <= stats["max_f0"]
    assert tracker.stats([])["mean_f0"] == 0.0


# ── cloning ──────────────────────────────────────────────────────────────────

def test_enrolment_builds_a_usable_profile():
    cloner = vs.VoiceCloner()
    profile = cloner.enroll("amber", tone(120.0, 4.0))
    assert profile.name == "amber"
    assert len(profile.embedding) == 48  # mean + std pooling of 24 mels
    assert profile.mean_f0 == pytest.approx(120.12, abs=0.5)
    assert profile.pitch_class == "baritone"
    assert profile.speaking_rate_wps > 0
    assert profile.reference_seconds == pytest.approx(4.0)
    assert profile.is_usable is True
    assert profile.to_dict()["embedding_dim"] == 48


def test_short_reference_is_not_usable():
    cloner = vs.VoiceCloner()
    profile = cloner.enroll("tiny", tone(120.0, 1.0))
    assert profile.is_usable is False


def test_similarity_separates_speakers():
    cloner = vs.VoiceCloner()
    low = cloner.enroll("low", tone(120.0, 4.0))
    high = cloner.enroll("high", tone(220.0, 4.0))
    near = cloner.enroll("near", tone(122.0, 4.0))
    assert cloner.similarity(low, near) > 0.99
    assert cloner.similarity(low, high) < cloner.similarity(low, near)
    assert cloner.cosine(low.embedding, high.embedding) == pytest.approx(
        cloner.similarity(low, high), abs=1e-3)


def test_verification_and_best_match():
    cloner = vs.VoiceCloner()
    reference = tone(120.0, 4.0)
    profile = cloner.enroll("amber", reference)
    verdict = cloner.verify(profile, reference)
    assert verdict["verified"] is True
    assert verdict["similarity"] >= 0.99
    assert verdict["threshold"] == pytest.approx(0.90)
    impostor = cloner.verify(profile, tone(300.0, 4.0))
    assert impostor["similarity"] < verdict["similarity"]
    match = cloner.best_match(tone(121.0, 3.0))
    assert match["best"] == "amber"
    assert match["score"] > 0.99
    assert [name for name, _ in match["ranking"]] == ["amber"]
    with pytest.raises(ValueError):
        vs.VoiceCloner().best_match(tone(120.0, 1.0))


def test_estimate_rate_is_plausible():
    cloner = vs.VoiceCloner()
    rate = cloner.estimate_rate(tone(120.0, 4.0))
    assert 0.0 < rate < 30.0


# ── voice design ─────────────────────────────────────────────────────────────

def test_voice_design_parses_a_brief():
    designer = vs.VoiceDesigner()
    design = designer.design("A warm, calm British female narrator with a low pitch")
    assert design.gender == "feminine"
    assert design.accent == "british"
    assert design.pitch == "low"
    assert design.pace == "slow"
    assert design.rate_multiplier() == pytest.approx(0.82)
    assert design.pitch_multiplier() == pytest.approx(1.0384)
    assert design.target_f0() == pytest.approx(134.99, abs=1e-2)
    assert 0.0 <= design.breathiness() <= 1.0
    assert design.to_params()["gender"] == "feminine"


def test_voice_design_defaults_and_masculine_cues():
    designer = vs.VoiceDesigner()
    plain = designer.design("A neutral documentary narrator")
    assert plain.gender == "neutral"
    assert plain.pitch_multiplier() == pytest.approx(1.0)
    assert plain.target_f0() == pytest.approx(130.0)
    male = designer.design("deep male announcer, raspy, fast")
    assert male.gender == "masculine"
    assert male.pitch == "low"
    assert male.timbre == "raspy"
    assert male.pace == "fast"
    assert male.rate_multiplier() > 1.0


def test_voice_design_audition_and_duration():
    designer = vs.VoiceDesigner()
    design = designer.design("A warm British female narrator with a low pitch")
    script = designer.audition_script(design)
    assert design.gender in script and design.accent in script
    seconds = designer.estimate_duration(design, "word " * 100)
    assert seconds == pytest.approx(100 / (2.6 * design.rate_multiplier()), abs=1e-2)


# ── VAD, alignment, transcription ────────────────────────────────────────────

def test_vad_merges_speech_around_short_gaps(extractor):
    vad = vs.VoiceActivityDetector()
    signal = tone(120.0, 0.5) + noise(0.4, amp=0.001) + tone(120.0, 0.5)
    frames = extractor.extract(signal)
    segments = vad.detect(frames, 0.01)
    assert len(segments) == 1
    assert segments[0].start == pytest.approx(0.0)
    assert segments[0].duration == pytest.approx(1.38, abs=0.05)
    assert segments[0].to_dict()["confidence"] == 1.0
    assert vad.detect([], 0.01) == []


def test_forced_aligner_spreads_words_over_speech():
    aligner = vs.ForcedAligner()
    signal = tone(120.0, 0.5) + noise(0.4, amp=0.001) + tone(120.0, 0.5)
    words = aligner.align(["one", "two", "three", "four"], signal)
    assert [w.word for w in words] == ["one", "two", "three", "four"]
    assert words[0].start == 0.0
    assert words[-1].end <= 1.4
    times = [w.start for w in words]
    assert times == sorted(times)
    assert aligner.align([], signal) == []
    assert aligner.align(["x"], noise(0.5, amp=0.0))[0].end == 0.0


def test_wer_and_cer_use_levenshtein():
    transcriber = vs.Transcriber()
    assert transcriber.wer("the cat sat on the mat", "the cat sat on a mat") == pytest.approx(0.1667, abs=1e-4)
    assert transcriber.wer("a b c", "a b c") == 0.0
    assert transcriber.wer("", "") == 0.0
    assert transcriber.wer("", "a") == 1.0
    assert transcriber.cer("cat", "car") == pytest.approx(0.3333, abs=1e-4)


def test_transcribe_reports_speech_ratio():
    transcriber = vs.Transcriber()
    result = transcriber.transcribe(tone(120.0, 1.0))
    assert result["total_seconds"] == pytest.approx(1.0)
    assert result["speech_ratio"] == pytest.approx(0.98, abs=0.02)
    assert result["segments"]
    with_words = transcriber.transcribe(tone(120.0, 1.0), words=["alpha", "beta"])
    assert with_words["word_count"] == 2
    assert [w["word"] for w in with_words["words"]] == ["alpha", "beta"]


# ── dubbing ──────────────────────────────────────────────────────────────────

def synth(text: str, rate: float) -> float:
    return len(text.split()) / 2.6 / rate


def test_dubbing_timeline_clamps_rate_and_reports_overflow():
    timeline = vs.DubbingTimeline()
    cues = timeline.build([
        (0.0, 2.0, "Hello there"),
        (2.0, 6.0, "This is a much longer sentence for testing"),
        (6.0, 7.0, "Way too much text crammed into a tiny one second gap here"),
    ], synth)
    assert [cue.index for cue in cues] == [0, 1, 2]
    assert all(timeline.min_rate <= cue.rate <= timeline.max_rate for cue in cues)
    assert cues[0].overflow == 0.0
    assert cues[-1].overflow > 0.0
    assert cues[-1].overflow == pytest.approx(1.885, abs=1e-2)
    report = timeline.report(cues)
    assert report["cues"] == 3
    assert report["overflow_cues"] == [2]
    assert report["fit_ratio"] == pytest.approx(0.6667, abs=1e-3)
    assert timeline.report([]) == {"cues": 0}


def test_dubbing_shift_is_capped():
    timeline = vs.DubbingTimeline()
    cues = timeline.build([
        (0.0, 1.0, "short line"),
        (1.0, 2.0, "another much much much longer line that will not fit at all here"),
        (2.0, 3.0, "and yet another very long line that overflows the gap again"),
    ], synth)
    shifted = timeline.shift(cues)
    assert all(cue.padding <= timeline.max_shift_s + 1e-9 for cue in shifted)
    assert shifted[-1].padding >= shifted[0].padding


# ── audiobooks + dictation ───────────────────────────────────────────────────

def test_audiobook_chaptering_and_export():
    builder = vs.AudiobookBuilder()
    segments = [vs.SpeechSegment(i * 10.0, i * 10.0 + 8.0) for i in range(8)]
    silences = builder.find_silences(segments, 85.0)
    assert silences == [9.0, 19.0, 29.0, 39.0, 49.0, 59.0, 69.0, 81.5]
    chapters = builder.chapterize(segments, 85.0)
    assert len(chapters) == 1
    assert chapters[0].start == 0.0
    assert chapters[0].words == 160
    assert chapters[0].duration == pytest.approx(85.0)
    assert builder.chapterize([], 10.0) == []
    plan = builder.export_plan(chapters)
    assert plan["chapters"] == 1
    assert plan["files"][0]["file"] == "01-chapter-1.mp3"
    assert plan["total_duration_s"] == pytest.approx(86.5)
    assert plan["total_size_mb"] > 0


def test_dictation_session_commits_after_silence():
    session = vs.DictationSession(silence_timeout_s=0.2)
    loud = [0.5 * math.sin(i / 10.0) for i in range(1600)]
    quiet = [0.0005 for _ in range(1600)]
    first = session.push(loud, "hello world")
    assert first["speaking"] is True
    assert first["interim"] == "hello world"
    session.push(loud, "how are you")
    assert session.push(quiet)["committed"] is False
    committed = session.push(quiet)
    assert committed["committed"] is True
    assert "how are you" in session.text().lower()


def test_dictation_punctuation():
    assert vs.DictationSession.punctuate("hello world") == "Hello world."
    assert vs.DictationSession.punctuate("what is the plan") == "What is the plan?"
    assert vs.DictationSession.punctuate("") == ""
    assert vs.DictationSession.punctuate("a  b") == "A b."


# ── language registry + model manager ────────────────────────────────────────

def test_language_registry():
    registry = vs.LanguageRegistry()
    assert len(registry.all()) == 57
    assert registry.TOTAL_SUPPORTED == 646
    assert registry.has("en") and not registry.has("zz")
    hindi = registry.get("hi")
    assert hindi.name == "Hindi" and hindi.script == "Devanagari"
    assert [lang.code for lang in registry.by_family("Romance")][0] == "es"
    assert "en" in [lang.code for lang in registry.by_script("Latin")]
    report = registry.coverage_report()
    assert report["catalogued"] == 57
    assert report["total_supported"] == 646
    assert 0.0 < report["coverage_pct"] < 100.0
    assert sum(report["families"].values()) == 57


def test_model_manager_vram_planning():
    manager = vs.ModelManager(vram_bytes=8 * (1024 ** 3))
    spec_model = vs.VoiceModelSpec(name="vs-1b", params_b=1.0)
    assert manager.register(spec_model).name == "vs-1b"
    assert manager.usable_bytes == 7 * (1024 ** 3)
    plan = manager.plan(spec_model)
    assert plan["model"] == "vs-1b"
    assert plan["usable_gb"] == pytest.approx(7.0)
    by_quant = {row["quant"]: row for row in plan["options"]}
    assert by_quant["fp16"]["needed_gb"] == pytest.approx(2.05, abs=1e-2)
    assert by_quant["fp16"]["fits"] is True
    assert by_quant["int4"]["needed_gb"] < by_quant["int8"]["needed_gb"] < by_quant["fp16"]["needed_gb"]
    assert plan["recommended"] == "fp16"
    assert manager.fits(spec_model, "fp16") is True
    assert manager.fits(spec_model, "int4") is True
    huge = vs.VoiceModelSpec(name="vs-70b", params_b=70.0)
    assert manager.fits(huge, "fp16") is False
    info = spec_model.to_dict()
    assert info["weight_gb"] == pytest.approx(1.86, abs=1e-2)
    assert info["total_gb"] == pytest.approx(2.05, abs=1e-2)


# ── helpers ──────────────────────────────────────────────────────────────────

def test_numeric_helpers():
    assert vs.clamp01(3.0) == 1.0 and vs.clamp01(-3.0) == 0.0
    assert vs.safe_div(2.0, 0.0, default=4.0) == 4.0
