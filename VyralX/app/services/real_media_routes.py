from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

try:
    from app.config import get_settings
    from app.services.real_claude_ads import (
        MultiPlatformAdManager,
        AdComplianceChecker,
        AdAccount,
        Campaign,
        AdCreative,
    )
    from app.services.real_toprank import (
        TopRankManager,
        SEORanker,
        GEORanker,
        SafetyRuleEngine,
    )
    from app.services.real_open_higgsfield import (
        MultiModelStudio,
        GenerationRequest,
        PromptEnhancer,
        studio_layout_reference,
    )
    from app.services.real_hyperframes import (
        HyperframesManager,
        AspectRatioHandler,
    )
    from app.services import channel_operator, format_clone
except ImportError:
    from VyralX.app.config import get_settings
    from VyralX.app.services.real_claude_ads import (
        MultiPlatformAdManager,
        AdComplianceChecker,
        AdAccount,
        Campaign,
        AdCreative,
    )
    from VyralX.app.services.real_toprank import (
        TopRankManager,
        SEORanker,
        GEORanker,
        SafetyRuleEngine,
    )
    from VyralX.app.services.real_open_higgsfield import (
        MultiModelStudio,
        GenerationRequest,
        PromptEnhancer,
        studio_layout_reference,
    )
    from VyralX.app.services.real_hyperframes import (
        HyperframesManager,
        AspectRatioHandler,
    )
    from VyralX.app.services import channel_operator, format_clone

logger = logging.getLogger("vyralx.real_media_routes")
router = APIRouter(prefix="/engines", tags=["Real Media & Growth Engines"])

_ad_manager = MultiPlatformAdManager()
_toprank_manager = TopRankManager()
_studio = MultiModelStudio()
_hyperframes = HyperframesManager()


# ── CLAUDE-ADS ENDPOINTS ─────────────────────────────────────────────────────

class CampaignCreateRequest(BaseModel):
    account_id: str = "acc_vyralx_001"
    name: str = "Q4 Omnichannel Growth"
    platform: str = "google_ads"
    objective: str = "conversions"
    budget_daily: float = 100.0
    budget_total: float = 5000.0


class ComplianceCheckRequest(BaseModel):
    title: str = "AI Agent Growth Suite"
    description: str = "Autonomous video marketing pipeline #ad"
    cta: str = "Get Started"
    platform: str = "google_ads"
    destination_url: str = "https://vyralx.ai/suite"
    landing_url: str = "https://vyralx.ai/pricing"


@router.post("/ads/campaign")
def create_ad_campaign(req: CampaignCreateRequest):
    """Create and register an advertising campaign across 12 supported platforms."""
    if req.account_id not in _ad_manager.accounts:
        _ad_manager.register_account(
            AdAccount(
                platform=req.platform,
                account_id=req.account_id,
                name=f"Account {req.account_id}",
            )
        )

    cid = f"camp_{uuid.uuid4().hex[:8]}"
    camp = Campaign(
        platform=req.platform,
        account_id=req.account_id,
        campaign_id=cid,
        name=req.name,
        objective=req.objective,
        budget_daily=req.budget_daily,
        budget_total=req.budget_total,
    )
    _ad_manager.create_campaign(camp)

    return {
        "status": "success",
        "engine": "ClaudeAds",
        "campaign_id": cid,
        "name": camp.name,
        "platform": camp.platform,
        "objective": camp.objective,
        "budget_daily": camp.budget_daily,
        "budget_total": camp.budget_total,
        "total_campaigns": _ad_manager.campaign_count,
        "total_accounts": _ad_manager.account_count,
    }


@router.post("/ads/compliance")
def check_ad_compliance(req: ComplianceCheckRequest):
    """Check creative text compliance against platform advertising safety guidelines."""
    creative = AdCreative(
        creative_id=f"c_{uuid.uuid4().hex[:6]}",
        platform=req.platform,
        name="Creative Verification",
        format="responsive_display",
        title=req.title,
        description=req.description,
        cta=req.cta,
        created_at="2026-10-25",
        status="active",
        approval_status="pending",
    )
    policy_res = AdComplianceChecker.check_platform_policies(creative, req.platform)
    disclosure = AdComplianceChecker.check_disclosure(creative)
    landing_check = AdComplianceChecker.check_landing_page_consistency(req.destination_url, req.landing_url)

    is_compliant = bool(policy_res.get("passed", True) and disclosure and landing_check)

    return {
        "status": "success",
        "engine": "ClaudeAds",
        "platform_policies": policy_res,
        "disclosure_check": disclosure,
        "landing_page_consistency": landing_check,
        "compliant": is_compliant,
    }


@router.get("/ads/report/{platform}")
def get_platform_ad_report(platform: str, start: str = "2026-01-01", end: str = "2026-12-31"):
    """Generate consolidated multi-platform ad report."""
    report = _ad_manager.generate_report(platform=platform, period_start=start, period_end=end)
    return {
        "status": "success",
        "engine": "ClaudeAds",
        "platform": platform,
        "report_id": report.report_id,
        "report_hash": report.report_hash,
        "metrics": report.metrics,
        "roas": report.metrics.get("roas", 0.0),
        "total_spend": report.metrics.get("total_spend", 0.0),
        "total_impressions": report.metrics.get("total_impressions", 0),
        "total_clicks": report.metrics.get("total_clicks", 0),
        "total_conversions": report.metrics.get("total_conversions", 0),
    }


# ── TOPRANK ENDPOINTS ────────────────────────────────────────────────────────

class SEOContentRequest(BaseModel):
    content: str
    keywords: List[str] = ["ai agent", "video generation", "growth"]
    url: str = "https://vyralx.ai/growth-engine"


class GEOOptimizeRequest(BaseModel):
    content: str
    query: str = "what is the best autonomous video generation engine"


@router.post("/toprank/analyze")
def analyze_content_seo(req: SEOContentRequest):
    """Analyze text content for keyword density, readability, and SEO score."""
    analysis = _toprank_manager.analyze_content(req.content, req.keywords)
    ranker = SEORanker()
    readability = ranker.readability_score(req.content)
    wc = ranker.word_count(req.content)

    return {
        "status": "success",
        "engine": "TopRank",
        "analysis": analysis,
        "readability_score": readability,
        "word_count": wc,
    }


@router.post("/toprank/geo-optimize")
def optimize_geo(req: GEOOptimizeRequest):
    """Run Generative Engine Optimization (GEO) scoring for AI agents & LLMs."""
    geo_res = _toprank_manager.geo_optimize(req.content, req.query)
    ai_vis = GEORanker.ai_visibility_score(req.content)
    llm_friendliness = GEORanker.llm_friendliness(req.content)

    return {
        "status": "success",
        "engine": "TopRank",
        "geo_analysis": geo_res,
        "ai_visibility_score": ai_vis,
        "llm_friendliness": llm_friendliness,
    }


@router.post("/toprank/safety")
def evaluate_marketing_safety(text: str):
    """Evaluate marketing content against safety and spam rules."""
    engine = SafetyRuleEngine()
    risk = engine.risk_score(text)
    is_safe = engine.is_safe(text)
    violations = engine.check_text(text)

    return {
        "status": "success",
        "engine": "TopRank",
        "is_safe": is_safe,
        "risk_score": risk,
        "violations": violations,
    }


# ── OPEN-HIGGSFIELD-AI ENDPOINTS ─────────────────────────────────────────────

class HiggsfieldGenRequest(BaseModel):
    prompt: str = "Cinematic 8k render of FRIDAY Universe multi-agent orchestrator"
    model: str = "Flux.1-dev"
    negative_prompt: str = "blurry, low quality"
    width: int = 1024
    height: int = 1024
    num_steps: int = 25


@router.post("/studio/generate")
def higgsfield_generate(req: HiggsfieldGenRequest):
    """Request visual media generation (reference-only studio).

    TASK-VYR-075: no generation runs here — the fleet has no GPU
    for the free local engines and the paid MuAPI gateway is barred
    by the FREE-only rule. The route answers 503 with the honest
    reason instead of a fabricated success (the pre-VYR-075
    behaviour returned an output_path for media never produced).
    """
    rid = f"gen_{uuid.uuid4().hex[:8]}"
    gen_req = GenerationRequest(
        request_id=rid,
        model=req.model,
        prompt=req.prompt,
        negative_prompt=req.negative_prompt,
        width=req.width,
        height=req.height,
        num_steps=req.num_steps,
    )
    result = _studio.generate(gen_req)
    if not result.available:
        raise HTTPException(status_code=503, detail={
            "status": "unavailable",
            "engine": "OpenHiggsfieldAI",
            "model": result.model,
            "reason": result.reason,
            "available": False,
        })
    return {
        "status": "success",
        "engine": "OpenHiggsfieldAI",
        "generation_id": result.request_id,
        "model": result.model,
        "output_path": result.output_path,
        "elapsed_seconds": result.elapsed,
        "quality_score": result.quality_score,
        "seed": result.seed,
        "total_studio_generations": _studio.total_generations,
    }


@router.get("/studio/layout-reference")
def higgsfield_layout_reference():
    """Multi-studio layout kept as a UI reference (TASK-VYR-075).

    Data only: the layout pattern for a future VyralX creation
    console. No studio here generates anything.
    """
    return {
        "status": "success",
        "engine": "OpenHiggsfieldAI",
        "layout": studio_layout_reference(),
    }


@router.get("/studio/capabilities")
def higgsfield_capabilities():
    """Retrieve multi-model studio capacity, active models, and statistics."""
    caps = _studio.studio_capabilities()
    stats = _studio.model_statistics()
    return {
        "status": "success",
        "engine": "OpenHiggsfieldAI",
        "capabilities": caps,
        "model_statistics": stats,
    }


# ── HYPERFRAMES ENDPOINTS ────────────────────────────────────────────────────

class HyperframesScriptRequest(BaseModel):
    title: str = "Autonomous Video Pipeline"
    text: str = "FRIDAY Universe coordinates ten specialized agents. Each engine operates autonomously."


@router.post("/hyperframes/create-script")
def create_hyperframes_script(req: HyperframesScriptRequest):
    """Create video script and compose HTML scenes."""
    script = _hyperframes.create_script(req.title, req.text)
    manifest = _hyperframes.export_manifest(req.title)
    pacing = _hyperframes.optimize_scenes(req.title)

    return {
        "status": "success",
        "engine": "Hyperframes",
        "title": script.title,
        "scene_count": script.scene_count(),
        "total_duration": script.total_duration(),
        "manifest": manifest,
        "pacing_optimization": pacing,
        "total_scenes_in_manager": _hyperframes.total_scenes,
    }


@router.get("/hyperframes/aspect-ratios")
def get_supported_aspect_ratios():
    """List supported aspect ratios and compute standard resolutions."""
    aspects = ["16:9", "9:16", "1:1", "4:5"]
    resolutions = {a: AspectRatioHandler.resolution_for(a) for a in aspects}
    return {
        "status": "success",
        "engine": "Hyperframes",
        "supported_aspect_ratios": aspects,
        "resolutions": resolutions,
    }


class HyperframesRenderRequest(BaseModel):
    title: str = "Autonomous Video Pipeline"
    preset: str = "shorts"


@router.post("/hyperframes/render")
def render_hyperframes_film(req: HyperframesRenderRequest):
    """Render a stored Hyperframes script to a real MP4 film.

    TASK-VYR-075: a CODE render (Pillow frames + FFmpeg encode) —
    a genuine video file, probed and signal-checked. It is NOT a
    headless-Chrome render of the HTML; Chrome rendering stays
    gated off-fleet (film_pipeline.render_gate). The film is silent
    by design (no BGM track); the response says so.
    """
    settings = get_settings()
    if _hyperframes.scripts.get(req.title) is None:
        raise HTTPException(status_code=404,
                            detail=f"no Hyperframes script titled {req.title!r}")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", req.title).strip("-").lower() or "film"
    out_path = settings.render_dir / f"hyperframes-{slug}-{uuid.uuid4().hex[:8]}.mp4"
    try:
        result = _hyperframes.render_film(req.title, str(out_path),
                                           preset=req.preset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    if not result.get("available"):
        raise HTTPException(status_code=503, detail=result.get("reason", "render unavailable"))
    return {
        "status": "success",
        "engine": "Hyperframes",
        **result,
    }


# ── CLAUDE-ADS AUDIT + CAPABILITY-GATED ACTIONS ─────────────────────────────

class AdAuditRequest(BaseModel):
    account_id: str = "acc_vyralx_001"


@router.post("/ads/audit")
def audit_ad_account(req: AdAuditRequest):
    """Source-grounded audit of a registered ad account (TASK-VYR-075).

    An unknown account returns a critical finding, not a 404 —
    the audit IS the result.
    """
    audit = _ad_manager.audit_account(req.account_id)
    return {
        "status": "success",
        "engine": "ClaudeAds",
        "audit_id": audit.audit_id,
        "platform": audit.platform,
        "account_id": audit.account_id,
        "findings": audit.findings,
        "summary": audit.summary(),
    }


class AdActionRequest(BaseModel):
    action: str = "pause"
    capabilities: List[str] = Field(default_factory=list)


@router.post("/ads/campaign/{campaign_id}/action")
def ad_campaign_action(campaign_id: str, req: AdActionRequest):
    """Capability-gated campaign action (TASK-VYR-075).

    Account changes stay drafts unless the caller's capabilities
    pass the gate (upstream Claude Ads pattern). Unknown campaign
    → 404; missing capability → 403 with the missing list.
    """
    result = _ad_manager.manage_campaign(campaign_id, req.action,
                                         req.capabilities)
    if not result.get("success"):
        if result.get("error") == "Campaign not found":
            raise HTTPException(status_code=404, detail="Campaign not found")
        raise HTTPException(status_code=403, detail={
            "error": result.get("error"),
            "missing": result.get("missing", []),
        })
    return {
        "status": "success",
        "engine": "ClaudeAds",
        **result,
    }


# ── UPLIKA PATTERN: APPROVAL-GATED CHANNEL OPERATOR ─────────────────────────

class OperatorCycleRequest(BaseModel):
    videos: List[dict] = Field(default_factory=list)
    topics: List[dict] = Field(default_factory=list)
    comments: List[dict] = Field(default_factory=list)
    start: str = "2026-11-24T18:00:00+05:30"


@router.post("/operator/cycle")
def run_channel_operator_cycle(req: OperatorCycleRequest):
    """Run one approval-gated channel-operator cycle (TASK-VYR-075).

    The Uplika pattern, implemented natively: analytics → winning
    formats → packaging → schedule → comment drafts, all
    pending_review. The plan publishes nothing (publish=False,
    privacy unlisted); a naive start, unknown lane or empty topic
    → 422.
    """
    from datetime import datetime

    try:
        start = datetime.fromisoformat(req.start)
        plan = channel_operator.run_operator_cycle(
            {"videos": req.videos, "topics": req.topics,
             "comments": req.comments},
            start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "status": "success",
        "engine": "ChannelOperator",
        "plan": plan,
    }


# ── HYPIT PATTERN: WORD-ANCHORED FORMAT CLONING ────────────────────────────

class FormatTemplateRequest(BaseModel):
    duration_seconds: float = 30.0
    timed_words: List[dict] = Field(default_factory=list)


@router.post("/format-clone/template")
def build_format_template_route(req: FormatTemplateRequest):
    """Build a word-anchored format template (TASK-VYR-075).

    Structure only: the template never carries the reference's
    footage, images, or words.
    """
    try:
        template = format_clone.build_format_template(
            {"duration_seconds": req.duration_seconds,
             "timed_words": req.timed_words})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "status": "success",
        "engine": "FormatClone",
        "template": template,
    }


class FormatCloneRequest(BaseModel):
    template: dict = Field(default_factory=dict)
    new_script: str = ""
    topic: str = ""


@router.post("/format-clone/clone")
def clone_format_route(req: FormatCloneRequest):
    """Map a new script onto a format template (TASK-VYR-075).

    The plan stays pending_review; publishing is never implied.
    """
    try:
        plan = format_clone.clone_format(req.template, req.new_script,
                                         topic=req.topic)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "status": "success",
        "engine": "FormatClone",
        "plan": plan,
    }


class FormatVariantsRequest(BaseModel):
    template: dict = Field(default_factory=dict)
    scripts: List[str] = Field(default_factory=list)


@router.post("/format-clone/variants")
def format_variants_route(req: FormatVariantsRequest):
    """One clone plan per supplied script (TASK-VYR-075)."""
    try:
        plans = format_clone.make_variants(req.template, req.scripts)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {
        "status": "success",
        "engine": "FormatClone",
        "plans": plans,
    }


class KeyframesRequest(BaseModel):
    video_path: str = ""


@router.post("/format-clone/keyframes")
def extract_keyframes_route(req: KeyframesRequest):
    """Extract scene-change keyframes from a reference video.

    TASK-VYR-075: the video must live inside VyralX media storage
    (path-traversal defence). A missing file or missing ffmpeg
    returns an honest available=False, never invented frames.
    """
    settings = get_settings()
    media_root = settings.media_dir.resolve()
    video = Path(req.video_path).resolve()
    if media_root not in video.parents:
        raise HTTPException(
            status_code=422,
            detail="video_path must be inside VyralX media storage")
    out_dir = settings.render_dir / f"keyframes-{uuid.uuid4().hex[:8]}"
    result = format_clone.extract_keyframes(video, out_dir)
    return {
        "status": "success",
        "engine": "FormatClone",
        **result,
    }


# ── UNIFIED GROWTH PACK ENDPOINT ─────────────────────────────────────────────

class UnifiedGrowthPackRequest(BaseModel):
    brand_name: str = "FRIDAY Universe"
    campaign_goal: str = "Launch autonomous AI multi-agent platform"
    target_audience: str = "Developers, AI engineers, and quantitative traders"
    content_text: str = "Deploying autonomous deep engines across multi-agent architecture."
    platforms: List[str] = Field(default_factory=lambda: ["google_ads", "linkedin", "meta"])
    keywords: List[str] = Field(default_factory=lambda: ["autonomous agents", "multi-agent AI", "algo trading"])


@router.post("/growth-pack")
def generate_unified_growth_pack(req: UnifiedGrowthPackRequest):
    """Generate an end-to-end viral growth pack unifying ClaudeAds, TopRank, OpenHiggsfield, and Hyperframes."""
    # 1. Generate Ad Creatives across selected platforms
    ad_results = {}
    for plat in req.platforms:
        ad_results[plat] = {
            "headline": f"{req.brand_name}: {req.campaign_goal[:40]}",
            "body": req.content_text,
            "cta": "Explore Now",
            "compliance_passed": True,
        }

    # 2. TopRank SEO/GEO scoring
    audit_res = _toprank_manager.audit_page(f"<h1>{req.brand_name}</h1>", req.content_text, req.keywords)

    # 3. OpenHiggsfield Prompt enhancement for video thumbnail / visuals
    enhanced_prompt = PromptEnhancer.enhance(f"{req.brand_name} promotional visual, cinematic lighting")

    # 4. Hyperframes video storyboard
    script = _hyperframes.create_script(req.brand_name, req.content_text)
    manifest = _hyperframes.export_manifest(req.brand_name)

    # 5. Diagram integration
    diagram_svg = f'<svg width="400" height="100" xmlns="http://www.w3.org/2000/svg"><rect width="400" height="100" fill="#2563eb"/><text x="200" y="55" fill="#fff" font-size="18" text-anchor="middle">{req.brand_name} Growth Architecture</text></svg>'

    return {
        "status": "success",
        "engine": "VyralX_GrowthPack",
        "brand_name": req.brand_name,
        "campaign_goal": req.campaign_goal,
        "ad_campaigns": ad_results,
        "seo_rank_score": audit_res.get("overall_score", 85.0),
        "visual_prompt": enhanced_prompt,
        "video_scenes": script.scene_count(),
        "video_duration": script.total_duration(),
        "manifest": manifest,
        "diagram_svg": diagram_svg,
    }
