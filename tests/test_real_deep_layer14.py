"""
Real Deep Layer 14 Tests — heygen-com/hyperframes → VyralX.

Functional tests for VyralX/app/agents/real_hyperframes.py:
CSS value parsing (lengths, colours, contrast, inline style blocks), the HTML
scene graph, the frame clock, deterministic RNG, easing/spring curves,
animation tracks, transition scheduling, caption alignment + readability,
the render manifest and the ffmpeg command builder.
"""

import importlib.util
import os
import sys

import pytest

MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "VyralX", "app", "agents", "real_hyperframes.py")

spec = importlib.util.spec_from_file_location("real_hyperframes", MODULE_PATH)
hf = importlib.util.module_from_spec(spec)
sys.modules["real_hyperframes"] = hf
spec.loader.exec_module(hf)


SCENE_HTML = """
<div id="root" class="scene">
  <div style="opacity: 1; width: 1080px; height: 1920px">
    <h1 style="font-size: 96px; color: #ffffff">Hyperframes</h1>
    <p style="font-size: 48px">Scene one keeps the hook on screen for three seconds.</p>
    <img src="logo.png" />
  </div>
</div>
"""

WORDS = ["Every", "second", "of", "this", "clip", "was", "rendered",
         "deterministically", "from", "a", "seed"]


@pytest.fixture()
def composer():
    comp = hf.HyperframesComposer(fps=24, width=1080, height=1920, seed="demo")
    comp.add_scene(hf.SceneSpec(scene_id="s1", html=SCENE_HTML, duration_s=3.0,
                                transition_out="crossfade"))
    comp.add_scene(hf.SceneSpec(scene_id="s2", html=SCENE_HTML, duration_s=4.0,
                                transition_in="crossfade"))
    return comp


# ── CSS values ───────────────────────────────────────────────────────────────

def test_length_units_resolve_against_a_reference():
    assert hf.Length.parse("24px").resolve() == pytest.approx(24.0)
    assert hf.Length.parse("50vh").resolve(1920) == pytest.approx(960.0)
    assert hf.Length.parse("25%").resolve(400.0) == pytest.approx(100.0)
    assert hf.Length.parse("2em").resolve() == pytest.approx(32.0)
    assert hf.Length.parse("") is None


def test_color_parsing_and_contrast_ratio():
    white = hf.Color.parse("#FFFFFF")
    black = hf.Color.parse("#000000")
    assert (white.r, white.g, white.b) == (255, 255, 255)
    assert white.contrast_ratio(black) == pytest.approx(21.0, rel=1e-3)
    assert black.contrast_ratio(black) == pytest.approx(1.0, rel=1e-3)
    assert hf.Color.parse("#336699") == hf.Color(51, 102, 153, 1.0)
    assert hf.Color.parse("not-a-color") is None


def test_style_declaration_accessors():
    style = hf.StyleDeclaration("opacity: 0.5; font-size: 24px; color: #ff0000; padding: 10px 20px")
    assert style.get("padding") == "10px 20px"
    assert style.length("font-size") == pytest.approx(24.0)
    assert style.number("opacity") == pytest.approx(0.5)
    assert style.color("color") == hf.Color(255, 0, 0, 1.0)
    assert style.opacity() == pytest.approx(0.5)
    assert style.get("missing", "fallback") == "fallback"
    assert set(hf.StyleDeclaration.ANIMATABLE) >= {"opacity", "scale", "translateY"}


# ── scene graph ──────────────────────────────────────────────────────────────

def test_scene_graph_structure():
    graph = hf.HtmlSceneGraph(SCENE_HTML)
    summary = graph.summary()
    assert summary["nodes"] == 5
    assert summary["tag_mix"]["h1"] == 1
    assert summary["tag_mix"]["img"] == 1
    assert summary["media"] == ["logo.png"]
    assert "Hyperframes" in graph.text_content()
    assert len(graph.nodes) == summary["nodes"] + 1  # + synthetic root


def test_scene_graph_selectors_and_z_order():
    graph = hf.HtmlSceneGraph(SCENE_HTML)
    assert [n.tag for n in graph.find("h1")] == ["h1"]
    assert len(graph.find(".scene")) == 1
    assert len(graph.find("#root")) == 1
    z = graph.z_order()
    assert len(z) == len(graph.nodes) - 1  # painted nodes exclude the synthetic root
    assert [node.depth for node in z] == sorted(node.depth for node in z)


def test_scene_node_walk_and_to_dict():
    graph = hf.HtmlSceneGraph(SCENE_HTML)
    heading = graph.find("h1")[0]
    assert heading.to_dict()["tag"] == "h1"
    for node in heading.walk():
        assert isinstance(node.style, hf.StyleDeclaration)


# ── clock, rng, easing ───────────────────────────────────────────────────────

def test_frame_clock_counting_and_seeking():
    clock = hf.FrameClock(fps=24, duration_s=6.6)
    assert clock.frame_at(6.6) == 157
    assert len(clock.frame_times()) == 158
    assert clock.frame_times()[1] == pytest.approx(1 / 24, rel=1e-3)
    assert clock.time_at(24) == pytest.approx(1.0, rel=1e-6)
    seeked = clock.seek(1.0)
    assert seeked["frame"] == 24


def test_deterministic_rng_is_reproducible():
    first = hf.DeterministicRng("demo")
    second = hf.DeterministicRng("demo")
    values = [round(first.random(), 4) for _ in range(3)]
    assert values == [round(second.random(), 4) for _ in range(3)]
    assert values == [0.8802, 0.1619, 0.8487]
    assert all(0.0 <= value <= 1.0 for value in values)
    assert 1 <= first.int_between(1, 10) <= 10
    assert first.choice(list("abc")) in "abc"
    assert first.uniform(2.0, 4.0) != first.next_u64()


def test_cubic_bezier_and_spring_curves():
    ease = hf.cubic_bezier(0.4, 0.0, 0.2, 1.0)
    assert ease(0.0) == pytest.approx(0.0, abs=1e-6)
    assert ease(1.0) == pytest.approx(1.0, abs=1e-6)
    assert ease(0.5) == pytest.approx(0.7756, abs=1e-3)
    assert ease(0.25) < ease(0.75)
    spring = hf.spring()
    assert spring(0.0) == pytest.approx(0.0, abs=1e-6)
    assert spring(1.0) == pytest.approx(1.0, abs=1e-2)
    assert spring(0.2) > 0.5, "a stiff spring should be well past halfway at 200ms"


# ── animation tracks ─────────────────────────────────────────────────────────

def test_animation_track_sampling():
    track = hf.AnimationTrack("opacity")
    track.add(0.0, 0.0)
    track.add(1.0, 1.0, easing="ease_out")
    assert track.sample(-1.0) == pytest.approx(0.0)
    assert track.sample(2.0) == pytest.approx(1.0)
    assert 0.0 <= track.sample(0.5) <= 1.0
    samples = track.samples(24)
    assert len(samples) == 24
    assert all(0.0 <= value <= 1.0 for _, value in samples)
    assert track.to_dict()["name"] == "opacity"


def test_track_easing_monotonic():
    linear = hf.AnimationTrack("scale")
    linear.add(0.0, 1.0, easing="linear")
    linear.add(1.0, 2.0)
    values = [round(value, 6) for _, value in linear.samples(5)]
    assert values == [pytest.approx(v, abs=1e-6) for v in (1.0, 1.2, 1.4, 1.6, 1.8)]
    assert values == sorted(values)


# ── transitions ──────────────────────────────────────────────────────────────

def test_transition_scheduler_layout_overlaps_scenes():
    scheduler = hf.TransitionScheduler()
    first = hf.SceneSpec(scene_id="s1", html=SCENE_HTML, duration_s=3.0, transition_out="crossfade")
    second = hf.SceneSpec(scene_id="s2", html=SCENE_HTML, duration_s=4.0, transition_in="crossfade")
    layout = scheduler.layout([first, second])
    assert layout[0].start == pytest.approx(0.0)
    assert layout[0].end == pytest.approx(3.0)
    assert layout[1].start == pytest.approx(2.6)
    assert layout[1].end == pytest.approx(6.6)
    assert scheduler.total_duration(layout) == pytest.approx(6.6)
    overlap = scheduler.overlap_report(layout)
    assert overlap["with_overlap"] == 1
    assert overlap["total_overlap_s"] == pytest.approx(0.4)
    assert scheduler.transition_curve("crossfade", 0.5) == pytest.approx(0.5)


def test_transition_validation_rejects_unknown_names():
    scheduler = hf.TransitionScheduler()
    assert "cut" in scheduler.SUPPORTED
    good = hf.SceneSpec(scene_id="s1", html=SCENE_HTML, duration_s=2.0, transition_in="cut")
    assert scheduler.validate([good]) == []
    bad = hf.SceneSpec(scene_id="s2", html=SCENE_HTML, duration_s=2.0, transition_in="spiral")
    problems = scheduler.validate([bad])
    assert problems and "spiral" in problems[0]


# ── captions ─────────────────────────────────────────────────────────────────

def test_caption_alignment_covers_the_window():
    aligner = hf.CaptionAligner(max_chars=32, max_lines=2)
    cues = aligner.align(WORDS, start=0.0, end=6.0)
    assert cues[0].start == pytest.approx(0.0)
    assert cues[-1].end == pytest.approx(6.0, abs=1e-6)
    assert " ".join(cue.text for cue in cues).split()[:3] == WORDS[:3]
    assert all(cue.start < cue.end for cue in cues)


def test_caption_readability_report():
    aligner = hf.CaptionAligner()
    cues = aligner.align(WORDS, 0.0, 6.0)
    report = aligner.readability_report(cues)
    assert report["cues"] == len(cues)
    assert report["mean_cps"] > 0
    assert report["total_covered_s"] == pytest.approx(6.0, abs=1e-2)
    assert report["too_fast"] == []


def test_caption_readability_flags_fast_cues():
    aligner = hf.CaptionAligner(max_cps=5.0)
    cues = aligner.align(WORDS, 0.0, 2.0)
    report = aligner.readability_report(cues)
    assert report["too_fast"], "an 11-word script in 2s must read as too fast"


def test_caption_wrap_respects_line_budget():
    aligner = hf.CaptionAligner(max_chars=16)
    lines = aligner.wrap("alpha beta gamma delta epsilon zeta eta theta".split())
    assert len(lines) > 1
    for line in lines:
        assert len("".join(line).strip()) <= 16


def test_caption_srt_and_drift_correction():
    aligner = hf.CaptionAligner()
    cues = aligner.align(WORDS, 0.0, 6.0)
    srt = aligner.to_srt(cues)
    assert srt.splitlines()[0] == "1"
    assert "-->" in srt.splitlines()[1]
    corrected = aligner.correct_drift(cues, 3.0)
    assert corrected[-1].end == pytest.approx(3.0, abs=1e-6)
    assert corrected[0].start == pytest.approx(0.0)


def test_caption_cue_to_srt_block():
    cue = hf.CaptionCue(index=0, start=1.0, end=2.5, text="hello world", words=["hello", "world"])
    block = cue.to_srt()
    assert block.splitlines()[1] == "00:00:01,000 --> 00:00:02,500"
    assert cue.to_dict()["text"] == "hello world"


# ── composer end to end ──────────────────────────────────────────────────────

def test_composer_timeline_frame_plan_and_manifest(composer):
    timeline = composer.timeline()
    assert [p.scene.scene_id for p in timeline] == ["s1", "s2"]
    plan = composer.frame_plan()
    assert len(plan) == 158
    assert plan[0]["frame"] == 0 and plan[0]["scene_id"] == "s1"
    assert plan[-1]["scene_id"] == "s2"
    manifest = composer.build()
    assert manifest.fps == 24
    assert (manifest.width, manifest.height) == (1080, 1920)
    assert manifest.duration_s == pytest.approx(6.6)
    assert manifest.total_frames == 158
    assert len(manifest.cues) == 4 and manifest.to_dict()["cue_count"] == 4
    assert len(manifest.digest) == 64
    int(manifest.digest, 16)  # digest must be hex (sha256 of the composition)


def test_composer_manifest_is_deterministic(composer):
    first = composer.build()
    second = composer.build()
    assert first.digest == second.digest
    assert first.to_dict()["scenes"] == second.to_dict()["scenes"]


def test_composer_captions_start_after_the_transition(composer):
    placed = composer.timeline()
    cues = composer.captions(placed[1].scene, placed[1])
    assert cues
    assert cues[0].start >= placed[1].start + placed[1].transition_in_duration - 1e-6
    assert cues[-1].end <= placed[1].end + 1e-6


def test_composer_validation_reports_problems():
    comp = hf.HyperframesComposer()
    comp.add_scene(hf.SceneSpec(scene_id="bad", html="<div>x</div>", duration_s=1.0,
                                transition_in="teleport"))
    problems = comp.validate()
    assert problems and "teleport" in problems[0]


# ── ffmpeg ───────────────────────────────────────────────────────────────────

def test_ffmpeg_command_builder(composer):
    builder = hf.FfmpegCommandBuilder()
    argv = builder.build(composer.build())
    assert argv[0] == "ffmpeg"
    assert "-framerate" in argv and "24" in argv
    assert "-i" in argv
    assert "1080x1920" in argv
    assert argv[-1] == "out.mp4"
    assert "-frames:v" in argv
    assert builder.encode_args(1080, 1920)[-1] == "1080x1920"
    assert builder.frames_input("f%05d.png", 30)[0] == "-framerate"


def test_ffmpeg_concat_demuxer_listing():
    listing, argv = hf.FfmpegCommandBuilder().concat_demuxer(["a.mp4", "b.mp4"])
    assert listing.splitlines() == ["file 'a.mp4'", "file 'b.mp4'"]
    assert "-f" in argv and "concat" in argv
    assert argv[-1] == "concat.mp4"


# ── helpers ──────────────────────────────────────────────────────────────────

def test_numeric_helpers():
    assert hf.clamp01(-2.0) == 0.0 and hf.clamp01(3.0) == 1.0
    assert hf.safe_div(1.0, 0.0, default=7.0) == 7.0
    assert hf.statistics_mean([1.0, 2.0, 3.0]) == pytest.approx(2.0)
