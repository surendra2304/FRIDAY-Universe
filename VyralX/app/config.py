import shutil
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(Path(__file__).resolve().parent.parent / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "VyralX"
    app_env: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    api_key: str = "development-only-change-me"
    # Oracle Autonomous Database only. Empty by default so a missing configuration
    # fails closed instead of silently creating a SQLite file.
    database_url: str = ""
    # Second Oracle database: downloads, edits and uploads (media catalogue).
    media_database_url: str = ""
    data_dir: Path = Path("./data")
    media_dir: Path = Path("./media")
    render_dir: Path = Path("./renders")
    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"
    max_upload_mb: int = 2048
    max_stock_clip_mb: int = 150
    max_render_seconds: int = 14400
    max_concurrent_renders: int = 1
    render_max_cpu_threads: int = 1
    render_max_memory_mb: int = 512
    render_enable_ken_burns: bool = True
    render_audio_loudness_target_lufs: float = -14.0
    render_audio_loudness_min_lufs: float = -24.0
    render_audio_loudness_max_lufs: float = -10.0
    default_shorts_width: int = 1080
    default_shorts_height: int = 1920
    default_long_width: int = 1920
    default_long_height: int = 1080
    worker_required: bool = False
    # TASK-VYR-002: whether the always-on app process itself consumes the
    # durable queues (app.worker.run_once). None = auto: run it when
    # APP_ENV is production. Set QUEUE_WORKER_ENABLED explicitly to force
    # on/off (off when a standalone worker process is used instead).
    queue_worker_enabled: bool | None = None
    worker_poll_seconds: float = 2.0
    worker_heartbeat_timeout_seconds: int = 90
    worker_max_attempts: int = 3
    friday_url: str = ""
    friday_api_key: str = ""
    inference_url: str = ""
    inference_api_key: str = ""
    inference_model: str = ""
    # Editorial guidance only; it never grants media rights or publish approval.
    channel_name: str = Field(default="", max_length=160)
    channel_niche: str = Field(default="", max_length=240)
    channel_content_pillars: str = Field(default="", max_length=1200)
    channel_avoid_topics: str = Field(default="", max_length=1200)
    channel_brand_voice: str = Field(default="", max_length=240)
    channel_call_to_action: str = Field(default="", max_length=240)
    channel_language: str = Field(default="English", max_length=80)
    # Autonomous mode only queues licensed-source projects; YouTube publishing remains manual.
    autonomous_channel_enabled: bool = False
    autonomous_pexels_license_confirmed: bool = False
    autonomous_daily_project_limit: int = Field(default=1, ge=1, le=5)
    # When enabled, a completed project queues its own PublishJob so the worker can
    # upload without a manual approval step. The review gates stay in force.
    autonomous_auto_publish: bool = False
    autonomous_publish_privacy: str = "public"
    autonomous_run_interval_minutes: int = Field(default=180, ge=10, le=1440)
    # Viral repurposing pipeline: discovery thresholds and edit policy.
    viral_min_source_views: int = Field(default=250_000, ge=0)
    viral_min_source_seconds: float = Field(default=8.0, ge=3.0, le=60.0)
    viral_max_source_seconds: float = Field(default=58.0, ge=10.0, le=60.0)
    viral_whisper_model: str = Field(default="base", max_length=40)
    # "reuse_licensed" only accepts Creative Commons clips; "transformative"
    # follows the channel's existing commentary/attribution model instead.
    viral_source_policy: str = Field(default="transformative", max_length=40)
    viral_channel_handles: str = Field(default="", max_length=1200)
    # TASK-VYR-014 quality gates: when True (the default) the autopilot path
    # fails closed — no structured vision record, a static clip, or copy whose
    # claims/structure/length fail the footage checks means the candidate is
    # skipped instead of uploaded. The flag exists as an emergency kill
    # switch only; the owner's 2026-11-17 order is that the gates stay on.
    viral_quality_gates_enabled: bool = True
    # A real synthesized music bed under every commentary render (the old
    # renders claimed [music] in captions with no music audible).
    viral_music_bed_enabled: bool = True
    # TASK-VYR-019 BGM policy (owner decision 2026-11-18, option C):
    # "growth" (the default, while the channel is unlisted and growing)
    # takes the actual popular/chart tracks from the local BGM library
    # (<data_dir>/bgm + catalog.json, operator-provisioned);
    # "monetisation" takes YouTube Audio Library tracks from
    # <data_dir>/bgm_library instead. Either way a real bed is
    # MANDATORY: app.services.viral_bgm.prepare_music_bed picks the
    # most relevant track it can and falls back to the generated synth
    # bed rather than ever shipping silence — the source it used is
    # recorded on the render job, so a fallback is never silent.
    viral_bgm_policy: str = Field(default="growth", max_length=20)
    # Optional explicit BGM library locations; empty = the policy's
    # default folder under data_dir (bgm / bgm_library) and its
    # catalog.json.
    viral_bgm_library_dir: str = Field(default="", max_length=600)
    viral_bgm_catalog_path: str = Field(default="", max_length=600)
    # TASK-VYR-019: the autonomous find -> edit -> produce loop
    # (app.services.viral_loop, scripts/run_viral_loop.py). Default OFF:
    # nothing in this build runs, schedules or uploads by itself. The
    # loop discovers trending videos across ALL YouTube categories,
    # routes voiceless sources to the commentary path and voiced
    # sources to the framed path, and holds EVERY output as an
    # unlisted pending_approval publish job for the owner's review —
    # it never drains the publish queue and never uploads.
    viral_loop_enabled: bool = False
    # Audition budget per cycle (each audition is a download + Whisper
    # pass on a small host) and the cycle's wall-clock bound. Every
    # candidate that passes the quality gates inside the budget is
    # produced — the budget bounds cost, not output.
    viral_loop_max_attempts_per_cycle: int = Field(default=24, ge=1, le=200)
    viral_loop_cycle_budget_seconds: int = Field(default=5400, ge=60, le=21600)
    # Trending fetch size per YouTube category, and the widest source
    # the loop will consider at all (longer sources are excerpted by
    # the framed path or compiled by the long-form lane, never used
    # whole).
    viral_loop_trending_per_category: int = Field(default=10, ge=1, le=50)
    viral_loop_max_source_seconds: float = Field(default=600.0, ge=60.0, le=3600.0)
    # Region for the trending chart; empty = YouTube's global chart.
    viral_loop_region: str = Field(default="", max_length=8)
    # Long-form lane (owner decision 2026-11-18, option B): shorts are
    # the staple; when enabled, one compilation attempt is made every
    # N loop cycles from a series' held renders.
    viral_loop_longform_enabled: bool = False
    viral_loop_longform_every_n_cycles: int = Field(default=6, ge=1, le=100)
    viral_loop_longform_min_clips: int = Field(default=3, ge=2, le=20)
    # TASK-VYR-026: vision pacing + daily budget for the loop. Scene
    # calls are kept at least this many seconds apart inside a cycle
    # (the provider's per-minute token limit is clipped whenever two
    # calls land inside one minute window), the cycle stops cleanly
    # once the day's estimated vision-token spend reaches the budget
    # (0 = no budget), and it also stops after this many CONSECUTIVE
    # rate-limit-exhausted vision calls (summary reason
    # vision_rate_limited) instead of burning the remaining attempt
    # budget against a drained day.
    viral_loop_vision_min_interval_seconds: float = Field(default=65.0, ge=0.0, le=3600.0)
    viral_loop_vision_daily_token_budget: int = Field(default=180000, ge=0, le=10000000)
    viral_loop_vision_rate_limit_stop_threshold: int = Field(default=3, ge=1, le=24)
    # --- IG2 B7-C1: optional MoneyPrinterTurbo producer lane --------------
    # The autopilot's producer lane. "viral_remix" (default) is the native
    # lane; "mpt" routes produce_one to app.services.mpt_lane, which renders
    # briefs with a local MoneyPrinterTurbo checkout and passes the result
    # through the SAME five quality gates. The lane runs only when it is
    # BOTH selected here AND enabled below — either one alone is inert.
    viral_producer_lane: str = Field(default="viral_remix", max_length=40)
    viral_mpt_lane_enabled: bool = False
    # Path to the operator-provisioned MoneyPrinterTurbo checkout (holds
    # cli.py + config.toml). Empty = not provisioned; the lane refuses.
    viral_mpt_home: str = Field(default="", max_length=600)
    # Free stock sources only: pexels | pixabay (MPT's AI-generation
    # sources are paid and are refused by the lane).
    viral_mpt_video_source: str = Field(default="pexels", max_length=20)
    # Optional Edge-TTS voice for MPT renders; empty = VyralX's default.
    viral_mpt_voice_name: str = Field(default="", max_length=120)
    # How to launch MPT's cli.py in MPT's own environment, e.g.
    # "/opt/mpt/.venv/bin/python" or "uv run python". Empty = python3.
    viral_mpt_python_cmd: str = Field(default="", max_length=200)
    # JSON briefs file for the lane; empty = <data_dir>/mpt_briefs.json.
    viral_mpt_briefs_path: str = Field(default="", max_length=600)
    viral_mpt_timeout_seconds: int = Field(default=1800, ge=60, le=7200)
    inference_generation_path: str = "/v1/task/execute"
    inference_timeout_seconds: int = 60
    # Frame analysis: the commentary must describe what the clip actually shows,
    # so three frames are sent to a vision model before any copy is written.
    vision_api_key: str = ""
    vision_base_url: str = "https://api.groq.com/openai/v1"
    vision_model: str = "qwen/qwen3.8-27b"
    vision_timeout_seconds: int = 90
    # TASK-VYR-026: bounded retry for the vision stage. Only HTTP 429
    # is retried (up to this many retries after the first attempt),
    # waiting the provider's Retry-After when it sends one and a
    # 30/60/120s ladder otherwise; the total wait per call is capped
    # so a drained day cannot stall a cycle indefinitely.
    vision_max_retries: int = Field(default=3, ge=0, le=10)
    vision_retry_wait_cap_seconds: int = Field(default=240, ge=0, le=3600)
    tts_provider: str = "espeak"
    espeak_bin: str = "espeak-ng"
    espeak_voice: str = "en-us"
    espeak_rate: int = 165
    inference_tts_url: str = ""
    inference_tts_api_key: str = ""
    inference_tts_path: str = "/v1/audio/speech"
    inference_tts_model: str = ""
    inference_tts_voice: str = "alloy"
    inference_tts_timeout_seconds: int = 180
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "pNInz6obpgDQGcFmaJgB"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    elevenlabs_timeout_seconds: int = 120
    caption_alignment_url: str = ""
    caption_alignment_api_key: str = ""
    caption_alignment_path: str = "/v1/align"
    caption_alignment_timeout_seconds: int = 90
    caption_alignment_language: str = "en"
    intelx_url: str = ""
    intelx_api_key: str = ""
    memora_url: str = ""
    memora_api_key: str = ""
    # TASK-MEM-005-R1: VyralX authenticates to Memora with its OWN keys —
    # the dedicated VYRALX_MEMORA_API_KEY, else its per-agent VYRALX_API_KEY.
    # memora_api_key above binds env MEMORA_API_KEY (Memora's own key) and
    # is no longer presented to Memora; it is retained only so existing
    # deployments keep parsing.
    vyralx_memora_api_key: str = ""
    vyralx_api_key: str = ""
    memora_write_enabled: bool = False
    memora_read_enabled: bool = False
    sentinel_url: str = ""
    sentinel_api_key: str = ""
    sentinel_required_for_publish: bool = False
    sentinel_policy_path: str = "/v1/security/audit"
    stratex_url: str = ""
    stratex_api_key: str = ""
    forge_url: str = ""
    forge_api_key: str = ""
    cortex_url: str = ""
    cortex_api_key: str = ""
    futuris_url: str = ""
    futuris_api_key: str = ""
    vyralx_url: str = ""
    vyralx_api_key: str = ""
    echo_url: str = ""
    echo_api_key: str = ""
    echo_notifications_enabled: bool = False
    mediax_url: str = ""
    mediax_api_key: str = ""
    mediax_registry_enabled: bool = False
    datax_url: str = ""
    datax_api_key: str = ""
    datax_telemetry_enabled: bool = False
    gatekeeper_url: str = ""
    gatekeeper_api_key: str = ""
    bgm_ducking_attenuation_db: float = -16.0
    bgm_default_volume: float = 0.20
    pexels_api_key: str = ""
    unsplash_access_key: str = ""
    youtube_data_api_key: str = ""
    youtube_client_secrets_file: Path = Path("./secrets/youtube-client-secret.json")
    youtube_token_file: Path = Path("./data/secrets/youtube-token.json")
    # Logged-in YouTube cookie jar (Netscape format). Datacenter IPs are
    # challenged with "Sign in to confirm you're not a bot"; yt-dlp needs a
    # cookie jar from a signed-in browser to get through.
    youtube_cookies_file: Path = Path("./data/youtube_cookies.txt")
    youtube_default_privacy: str = "private"
    youtube_category_id: str = "28"
    # ISO 639-1 code sent as snippet.defaultLanguage/defaultAudioLanguage on
    # upload; empty string omits the fields.
    youtube_default_language: str = "en"
    # TASK-VYR-014: monetization slots. Affiliate/product links are JSON —
    # [{"label": "...", "url": "https://..."}] — and are rendered into upload
    # descriptions (with the mandatory disclosure block) only when set.
    # Empty default: descriptions stay byte-identical to the current format.
    affiliate_links_json: str = ""
    # Real business contact shown in descriptions / media kit. Empty = hidden.
    business_email: str = ""
    # Write a cross-post release bundle (Reels/TikTok/Facebook captions +
    # render copy) next to every produced Short.
    crosspost_export_enabled: bool = True
    youtube_upload_enabled: bool = False
    youtube_analytics_enabled: bool = False
    # TASK-VYR-014: channel identity + YPP eligibility tracker. The channel
    # id lets the tracker use the Data API key directly; empty = resolve the
    # channel through the OAuth session instead.
    youtube_channel_id: str = ""
    ypp_tracker_enabled: bool = True

    @model_validator(mode="after")
    def validate_settings(self) -> "Settings":
        production = self.app_env.lower() != "development"
        if not shutil.which(self.ffmpeg_bin):
            try:
                import static_ffmpeg
                ff, fp = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
                if ff and Path(ff).is_file():
                    self.ffmpeg_bin = ff
                if fp and Path(fp).is_file():
                    self.ffprobe_bin = fp
            except Exception:
                pass
        if self.app_env.lower() != "development" and (
            not self.api_key or self.api_key == "development-only-change-me"
        ):
            raise ValueError("Set a unique API_KEY outside development")
        if production:
            for label, value in (
                ("DATABASE_URL", self.database_url),
                ("MEDIA_DATABASE_URL", self.media_database_url),
            ):
                configured = (value or "").strip()
                if not configured:
                    raise ValueError(
                        f"{label} is required outside development: VyralX stores its data in "
                        "Oracle Autonomous Database, and there is no SQLite or PostgreSQL fallback"
                    )
                if not configured.startswith("oracle"):
                    raise ValueError(
                        f"{label} must be an Oracle Autonomous Database URL "
                        f"(oracle+oracledb://...); got {configured.split('://')[0]!r}"
                    )
        if self.worker_poll_seconds < 0.5:
            raise ValueError("WORKER_POLL_SECONDS must be at least 0.5")
        if self.worker_max_attempts < 1:
            raise ValueError("WORKER_MAX_ATTEMPTS must be at least 1")
        if self.render_max_cpu_threads < 1:
            raise ValueError("RENDER_MAX_CPU_THREADS must be at least 1")
        if self.render_max_memory_mb < 64:
            raise ValueError("RENDER_MAX_MEMORY_MB must be at least 64")
        if not (-40.0 <= self.render_audio_loudness_target_lufs <= -5.0):
            raise ValueError("RENDER_AUDIO_LOUDNESS_TARGET_LUFS must be between -40 and -5 LUFS")
        if not (-50.0 <= self.render_audio_loudness_min_lufs <= self.render_audio_loudness_max_lufs <= 0.0):
            raise ValueError("Invalid audio loudness min/max bounds")
        if self.max_stock_clip_mb < 1 or self.max_stock_clip_mb > self.max_upload_mb:
            raise ValueError("MAX_STOCK_CLIP_MB must be between 1 and MAX_UPLOAD_MB")
        if self.tts_provider.lower() not in {"espeak", "external", "elevenlabs", "edge"}:
            raise ValueError("TTS_PROVIDER must be espeak, external, elevenlabs, or edge")
        if not 80 <= self.espeak_rate <= 300:
            raise ValueError("ESPEAK_RATE must be between 80 and 300")
        if not 1 <= self.caption_alignment_timeout_seconds <= 300:
            raise ValueError("CAPTION_ALIGNMENT_TIMEOUT_SECONDS must be between 1 and 300")
        if (
            not self.caption_alignment_path.startswith("/")
            or self.caption_alignment_path.startswith("//")
            or "?" in self.caption_alignment_path
            or "#" in self.caption_alignment_path
        ):
            raise ValueError("CAPTION_ALIGNMENT_PATH must be a safe absolute path")
        if not self.caption_alignment_language.strip() or len(self.caption_alignment_language) > 20:
            raise ValueError("CAPTION_ALIGNMENT_LANGUAGE must be a short language tag")
        if any(ch.isspace() for ch in self.caption_alignment_language):
            raise ValueError("CAPTION_ALIGNMENT_LANGUAGE must not contain whitespace")
        if self.caption_alignment_url:
            alignment_url = urlsplit(self.caption_alignment_url.strip())
            if (
                alignment_url.scheme not in {"http", "https"}
                or not alignment_url.netloc
                or alignment_url.query
                or alignment_url.fragment
                or alignment_url.username
                or alignment_url.password
            ):
                raise ValueError("CAPTION_ALIGNMENT_URL must be an HTTP(S) base URL without credentials")
            if not self.caption_alignment_api_key.strip():
                raise ValueError("CAPTION_ALIGNMENT_API_KEY is required when alignment is configured")
        if self.autonomous_publish_privacy not in {"private", "unlisted", "public"}:
            raise ValueError("AUTONOMOUS_PUBLISH_PRIVACY must be private, unlisted, or public")
        if self.viral_source_policy not in {"reuse_licensed", "transformative"}:
            raise ValueError("VIRAL_SOURCE_POLICY must be reuse_licensed or transformative")
        if self.viral_bgm_policy not in {"growth", "monetisation"}:
            raise ValueError("VIRAL_BGM_POLICY must be growth or monetisation")
        if self.viral_producer_lane not in {"viral_remix", "mpt"}:
            raise ValueError("VIRAL_PRODUCER_LANE must be viral_remix or mpt")
        if self.sentinel_required_for_publish and not (
            self.sentinel_url and self.sentinel_api_key
            and self.sentinel_policy_path.startswith("/")
            and not self.sentinel_policy_path.startswith("//")
        ):
            raise ValueError(
                "SENTINEL_URL, SENTINEL_API_KEY and a validated absolute SENTINEL_POLICY_PATH "
                "are required when policy checks are enforced"
            )
        return self

    def prepare_directories(self) -> None:
        for directory in (self.data_dir, self.media_dir, self.render_dir):
            directory.mkdir(parents=True, exist_ok=True)
        self.youtube_token_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def database_backend(self) -> str:
        value = (self.database_url or "").strip()
        if not value:
            return "unconfigured"
        scheme = value.split("://")[0]
        if scheme.startswith("oracle"):
            return "oracle"
        if scheme.startswith("sqlite"):
            return "sqlite"
        if scheme.startswith("postgres"):
            return "postgresql"
        return scheme

    @property
    def media_database_backend(self) -> str:
        value = (self.media_database_url or "").strip()
        if not value:
            return "unconfigured"
        scheme = value.split("://")[0]
        if scheme.startswith("oracle"):
            return "oracle"
        if scheme.startswith("sqlite"):
            return "sqlite"
        if scheme.startswith("postgres"):
            return "postgresql"
        return scheme

    def resolved_database_url(self) -> str:
        """Return the configured URL, or a development-only SQLite file.

        The fallback exists purely so the unit-test suite and local development
        run without Oracle credentials. Outside ``APP_ENV=development`` the
        validator above has already rejected an empty value.
        """

        value = (self.database_url or "").strip()
        if value:
            return value
        if self.app_env.lower() == "development":
            self.data_dir.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{(self.data_dir / 'vyralx-dev.db').as_posix()}"
        raise RuntimeError("DATABASE_URL is not configured and APP_ENV is not development")


@lru_cache
def get_settings() -> Settings:
    return Settings()
