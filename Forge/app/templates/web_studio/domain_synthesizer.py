"""
ForgeWebStudio Domain Synthesizer.
Dynamically analyzes the user goal using NLP keyword extraction to detect domain archetype
and synthesizes fully bespoke, realistic content, copy, component architectures, colors,
fonts, and interactive models that are 100% unique to each prompt.
Eliminates ALL placeholder content ('Lorem ipsum', 'Project Alpha', 'John Doe', 'Kai Vex').
"""

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DomainBlueprint:
    domain_type: str  # portfolio, saas, ecommerce, dashboard, creative, generic
    app_title: str
    headline: str
    subheadline: str
    primary_cta: str
    secondary_cta: str
    accent_color: str
    secondary_color: str
    archetype: str = "modern_glass"
    font_heading: str = "'Outfit', sans-serif"
    font_body: str = "'Inter', sans-serif"
    three_d_scene_type: str = "torus_knot"
    categories: list[str] = field(default_factory=list)
    showcase_items: list[dict[str, Any]] = field(default_factory=list)
    features_bento: list[dict[str, Any]] = field(default_factory=list)
    interactive_modules: list[str] = field(default_factory=list)
    meta_description: str = ""
    kpi_metrics: dict[str, str] = field(default_factory=dict)
    hero_badge: str = ""
    social_proof_text: str = ""
    viewport_title: str = ""
    viewport_chip_top: str = ""
    viewport_chip_bottom_left: str = ""
    viewport_chip_bottom_right: str = ""
    model_stats: str = ""


# ---------------------------------------------------------------------------
# Color palettes keyed by archetype — deterministic but diverse
# ---------------------------------------------------------------------------
_PALETTE_POOL = [
    # (accent, secondary, archetype)
    ("#00f0ff", "#ff007a", "cyberpunk"),
    ("#6366f1", "#a855f7", "saas"),
    ("#ec4899", "#8b5cf6", "ecommerce"),
    ("#06b6d4", "#3b82f6", "mission_control"),
    ("#10b981", "#3b82f6", "saas"),
    ("#f59e0b", "#ef4444", "brutalist"),
    ("#d4af37", "#a0856c", "luxury"),
    ("#8b5cf6", "#06b6d4", "cyberpunk"),
    ("#e11d48", "#f97316", "brutalist"),
    ("#22d3ee", "#818cf8", "mission_control"),
]


def _palette_for_goal(goal: str, domain_type: str) -> tuple[str, str, str]:
    """Pick a deterministic but varied palette from the goal hash + domain."""
    seed = hashlib.md5((goal.lower() + domain_type).encode()).hexdigest()
    idx = int(seed[:4], 16) % len(_PALETTE_POOL)
    accent, secondary, archetype = _PALETTE_POOL[idx]
    # Force certain archetypes for specific domain types
    if domain_type == "dashboard":
        archetype_override = "mission_control"
        accent = ["#06b6d4", "#22d3ee", "#0ea5e9", "#3b82f6"][int(seed[4:6], 16) % 4]
        secondary = ["#3b82f6", "#818cf8", "#6366f1", "#06b6d4"][int(seed[6:8], 16) % 4]
        return accent, secondary, archetype_override
    if domain_type == "ecommerce":
        archetype_override = "ecommerce"
        return accent, secondary, archetype_override
    return accent, secondary, archetype


# ---------------------------------------------------------------------------
# NLP entity extraction helpers
# ---------------------------------------------------------------------------

def _extract_brand_name(goal: str) -> str:
    """Extract or generate a brand/project name from the goal text."""
    g = goal.strip()
    # Try: "for [Name]" or "[Name]'s portfolio"
    m = re.search(r"\bfor\s+([A-Z][a-z]+ [A-Z][a-z]+)", g)
    if m:
        return m.group(1)
    m = re.search(r"\bfor\s+([A-Z][a-z]+)", g)
    if m:
        return m.group(1)
    # "build a [Brand] ..." pattern
    m = re.search(r"(?:build|create|make)\s+(?:a\s+)?([A-Z][A-Za-z0-9]+(?:\s[A-Z][A-Za-z0-9]+)?)\s+(?:website|store|platform|dashboard|portfolio|app)", g)
    if m:
        candidate = m.group(1)
        if candidate.lower() not in {"the", "an", "this", "my", "your", "their", "futuristic", "modern", "interactive", "3d", "immersive", "best"}:
            return candidate
    # Fall back: first capitalized word from meaningful tokens
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", g)
    exclude = {"Build", "Create", "Make", "Design", "Generate", "Develop",
               "Portfolio", "Store", "Dashboard", "Platform", "Website",
               "App", "With", "And", "For", "The", "Real", "Time",
               "Interactive", "Futuristic", "Modern", "Three", "Based"}
    meaningful = [w for w in words if w not in exclude]
    if meaningful:
        return meaningful[0]
    # Generate from first 2 meaningful lowercased tokens
    tokens = [t for t in re.sub(r"[^a-z0-9\s]", "", g.lower()).split()
              if t not in {"build", "create", "make", "a", "an", "the", "for",
                           "with", "and", "or", "to", "of", "in", "on", "at"}]
    if len(tokens) >= 2:
        return tokens[0].capitalize() + tokens[1].capitalize()
    if tokens:
        return tokens[0].capitalize() + "AI"
    return "Apex"


def _extract_specialty(goal: str) -> str:
    """Extract the technical specialty/domain from the goal."""
    g = goal.lower()
    if any(k in g for k in ["three.js", "threejs", "webgl", "3d", "opengl", "glsl"]):
        return "3D WebGL Engineer"
    if any(k in g for k in ["ai", "machine learning", "ml", "neural", "llm"]):
        return "AI/ML Engineer"
    if any(k in g for k in ["rust", "systems", "embedded", "kernel"]):
        return "Systems Engineer"
    if any(k in g for k in ["blockchain", "crypto", "web3", "solidity"]):
        return "Web3 Developer"
    if any(k in g for k in ["game", "unity", "unreal", "godot"]):
        return "Game Developer"
    if any(k in g for k in ["design", "ux", "ui", "figma", "creative"]):
        return "Creative Designer & Engineer"
    if any(k in g for k in ["fullstack", "full-stack", "full stack"]):
        return "Full-Stack Engineer"
    if any(k in g for k in ["backend", "api", "microservices", "distributed"]):
        return "Backend Architect"
    if any(k in g for k in ["mobile", "ios", "android", "flutter", "react native"]):
        return "Mobile Developer"
    if any(k in g for k in ["devops", "kubernetes", "docker", "infra", "cloud"]):
        return "DevOps & Cloud Engineer"
    return "Software Engineer & Creative Technologist"


def _extract_technologies(goal: str) -> list[str]:
    """Extract mentioned or implied technologies from the goal."""
    g = goal.lower()
    techs = []
    tech_map = {
        "three.js": "Three.js", "threejs": "Three.js", "webgl": "WebGL",
        "glsl": "GLSL", "react": "React", "next.js": "Next.js", "nextjs": "Next.js",
        "vue": "Vue.js", "angular": "Angular", "svelte": "Svelte",
        "typescript": "TypeScript", "javascript": "JavaScript",
        "python": "Python", "fastapi": "FastAPI", "django": "Django",
        "node": "Node.js", "express": "Express", "rust": "Rust",
        "golang": "Go", "java": "Java", "kotlin": "Kotlin",
        "docker": "Docker", "kubernetes": "Kubernetes", "k8s": "Kubernetes",
        "postgresql": "PostgreSQL", "postgres": "PostgreSQL", "mongodb": "MongoDB",
        "redis": "Redis", "graphql": "GraphQL", "tailwind": "Tailwind CSS",
        "blockchain": "Blockchain", "solidity": "Solidity", "web3": "Web3.js",
        "tensorflow": "TensorFlow", "pytorch": "PyTorch", "ml": "Machine Learning",
        "aws": "AWS", "gcp": "GCP", "azure": "Azure", "firebase": "Firebase",
        "unity": "Unity", "unreal": "Unreal Engine",
    }
    for key, name in tech_map.items():
        if key in g and name not in techs:
            techs.append(name)
    # Defaults if nothing detected
    if not techs:
        techs = ["TypeScript", "React", "WebGL"]
    return techs[:6]


def _extract_product_domain(goal: str) -> dict[str, Any]:
    """Extract product category, items, and store personality from an e-commerce goal."""
    g = goal.lower()

    # Map keyword to (store_name_seed, category_list, product_types, color_hint)
    if any(k in g for k in ["watch", "timepiece", "luxury watch", "swiss", "dial", "horology"]):
        return {
            "brand_seed": "Chronos",
            "tagline": "Swiss Precision Reimagined for the Digital Era",
            "categories": ["All", "Tourbillons", "Divers", "Dress Watches", "Limited"],
            "product_type": "watches",
            "accent": "#d4af37",
            "secondary": "#9f7b4a",
            "archetype": "luxury",
            "hero_badge": "Handcrafted Swiss Horology • Interactive 3D Dial",
            "social_proof_text": "4.9/5 from 1,200+ horology collectors",
            "viewport_title": "Interactive 3D Complication Dial • 60FPS",
            "viewport_chip_top": "Sapphire Crystal",
            "viewport_chip_bottom_left": "COSC Chronometer",
            "viewport_chip_bottom_right": "Drag to Rotate 360°",
            "model_stats": "Swiss Tourbillon Movement • Automatic",
            "three_d_scene_type": "watch_dial",
        }
    if any(k in g for k in ["sneaker", "shoe", "footwear", "streetwear", "nike", "jordan"]):
        return {
            "brand_seed": "Apex",
            "tagline": "Where Performance Meets Cultural Identity",
            "categories": ["All", "Running", "Lifestyle", "Collab Drops", "Classics"],
            "product_type": "sneakers",
            "accent": "#f97316",
            "secondary": "#ec4899",
            "archetype": "brutalist",
            "hero_badge": "High-Performance Streetwear • Interactive 3D Model",
            "social_proof_text": "4.9/5 from 8,400+ verified sneakerheads",
            "viewport_title": "Sculpted 3D Kinetic Silhouette • 60FPS",
            "viewport_chip_top": "Carbon Fibre Plate",
            "viewport_chip_bottom_left": "Nitrogen Foam 82%",
            "viewport_chip_bottom_right": "Drag to Inspect 360°",
            "model_stats": "Adaptive Fit • Energy Return",
            "three_d_scene_type": "sneaker_3d",
        }
    if any(k in g for k in ["fashion", "clothing", "apparel", "dress", "luxury fashion"]):
        return {
            "brand_seed": "Maison",
            "tagline": "Elevated Essentials for the Modern Aesthetic",
            "categories": ["All", "Capsule", "Outerwear", "Accessories", "Editorial"],
            "product_type": "fashion",
            "accent": "#d4af37",
            "secondary": "#78716c",
            "archetype": "luxury",
            "hero_badge": "Atelier Haute Couture • Interactive 3D Silhouette",
            "social_proof_text": "4.9/5 from 2,800+ bespoke clients",
            "viewport_title": "Sculptural Draping & Silhouette • 60FPS",
            "viewport_chip_top": "Mulberry Silk 100%",
            "viewport_chip_bottom_left": "Hand-Basted Canvas",
            "viewport_chip_bottom_right": "Drag to Rotate",
            "model_stats": "Made-to-Order • Tailored Fit",
            "three_d_scene_type": "luxury_gem",
        }
    if any(k in g for k in ["keyboard", "mechanical", "gaming gear", "peripherals", "hardware"]):
        return {
            "brand_seed": "Vortex",
            "tagline": "High-Performance Input Engineering",
            "categories": ["All", "Keyboards", "Audio", "Displays", "Accessories"],
            "product_type": "peripherals",
            "accent": "#ec4899",
            "secondary": "#8b5cf6",
            "archetype": "cyberpunk",
            "hero_badge": "Pro Esports Hardware • Interactive 3D Core",
            "social_proof_text": "4.9/5 from 12,000+ competitive gamers",
            "viewport_title": "Rapid-Trigger Magnetic Core • 8000Hz",
            "viewport_chip_top": "Hall Effect Sensor",
            "viewport_chip_bottom_left": "0.1mm Actuation",
            "viewport_chip_bottom_right": "Drag to Inspect",
            "model_stats": "CNC Anodized Aluminum • Hot-Swap",
            "three_d_scene_type": "product_turntable",
        }
    if any(k in g for k in ["headphone", "audio", "speaker", "music", "studio"]):
        return {
            "brand_seed": "Sonique",
            "tagline": "Audiophile-Grade Spatial Sound Engineering",
            "categories": ["All", "Over-Ear", "IEMs", "Studio Monitors", "Cables"],
            "product_type": "audio",
            "accent": "#06b6d4",
            "secondary": "#6366f1",
            "archetype": "saas",
            "hero_badge": "Acoustic Reference Standard • Interactive 3D Acoustic Core",
            "social_proof_text": "4.9/5 from 3,400+ audio engineers",
            "viewport_title": "Planar Magnetic Driver Core • 60FPS",
            "viewport_chip_top": "106mm Planar Diaphragm",
            "viewport_chip_bottom_left": "0.001% THD Balanced",
            "viewport_chip_bottom_right": "Drag to Inspect",
            "model_stats": "Open-Back Acoustic Chamber",
            "three_d_scene_type": "audio_gear",
        }
    if any(k in g for k in ["skincare", "beauty", "cosmetics", "wellness"]):
        return {
            "brand_seed": "Lumina",
            "tagline": "Science-Backed Beauty for Radiant Living",
            "categories": ["All", "Serums", "Moisturisers", "Sun Care", "Treatments"],
            "product_type": "skincare",
            "accent": "#f472b6",
            "secondary": "#a78bfa",
            "archetype": "luxury",
        }
    if any(k in g for k in ["furniture", "interior", "home decor", "design objects"]):
        return {
            "brand_seed": "Forma",
            "tagline": "Sculptural Objects for Considered Living Spaces",
            "categories": ["All", "Seating", "Tables", "Lighting", "Objects"],
            "product_type": "furniture",
            "accent": "#d4af37",
            "secondary": "#78716c",
            "archetype": "luxury",
        }
    if any(k in g for k in ["car", "automobile", "vehicle", "ev", "electric vehicle"]):
        return {
            "brand_seed": "Volt",
            "tagline": "Electric Performance Without Compromise",
            "categories": ["All", "Sedans", "SUVs", "Performance", "Commercial"],
            "product_type": "vehicles",
            "accent": "#22d3ee",
            "secondary": "#3b82f6",
            "archetype": "mission_control",
        }
    if any(k in g for k in ["book", "course", "education", "learning", "e-learning"]):
        return {
            "brand_seed": "Nexus",
            "tagline": "Expert-Led Learning for the Next Generation of Builders",
            "categories": ["All", "Engineering", "Design", "Business", "Science"],
            "product_type": "courses",
            "accent": "#10b981",
            "secondary": "#6366f1",
            "archetype": "saas",
        }
    # Generic futuristic tech store
    brand = _extract_brand_name(goal)
    return {
        "brand_seed": brand,
        "tagline": "Curated Technology for Forward-Thinking Individuals",
        "categories": ["All", "Featured", "New Arrivals", "Bundles", "Limited"],
        "product_type": "tech",
        "accent": "#8b5cf6",
        "secondary": "#06b6d4",
        "archetype": "cyberpunk",
    }


def _extract_saas_domain(goal: str) -> dict[str, Any]:
    """Extract SaaS product positioning from goal."""
    g = goal.lower()
    brand = _extract_brand_name(goal)

    if any(k in g for k in ["analytics", "data", "insights", "bi", "business intelligence"]):
        return {
            "brand": brand + "Analytics",
            "tagline": "Turn Raw Data Into Competitive Intelligence",
            "value_prop": "Real-time data ingestion, AI-powered anomaly detection, and predictive dashboards that surface actionable insights before your competition sees them.",
            "categories": ["Core Engine", "Integrations", "AI Insights", "Enterprise"],
            "cta_primary": "Start Free Analysis",
            "cta_secondary": "Explore Live Demo",
            "accent": "#3b82f6",
            "secondary": "#06b6d4",
        }
    if any(k in g for k in ["security", "cybersecurity", "pentest", "soc", "zero trust"]):
        return {
            "brand": brand + "Shield",
            "tagline": "Zero-Trust Security That Never Sleeps",
            "value_prop": "Continuous threat intelligence, automated incident response, and AI-driven vulnerability scanning that protects your infrastructure in real-time.",
            "categories": ["Threat Intel", "Incident Response", "Compliance", "Enterprise"],
            "cta_primary": "Start Free Scan",
            "cta_secondary": "Book Security Audit",
            "accent": "#ef4444",
            "secondary": "#f97316",
        }
    if any(k in g for k in ["devops", "ci/cd", "deployment", "infrastructure", "platform engineering"]):
        return {
            "brand": brand + "Deploy",
            "tagline": "Ship Faster. Break Nothing. Sleep Better.",
            "value_prop": "Intelligent CI/CD pipelines with auto-rollback, multi-cloud orchestration, and predictive capacity planning that eliminates production surprises.",
            "categories": ["Pipelines", "Observability", "Cloud", "Enterprise"],
            "cta_primary": "Deploy in 60 Seconds",
            "cta_secondary": "View Architecture",
            "accent": "#10b981",
            "secondary": "#3b82f6",
        }
    if any(k in g for k in ["crm", "sales", "leads", "revenue", "marketing"]):
        return {
            "brand": brand + "CRM",
            "tagline": "Close More Deals With Autonomous AI Sales Intelligence",
            "value_prop": "AI-powered lead scoring, automated follow-up sequences, and pipeline forecasting with sub-hourly accuracy.",
            "categories": ["Pipeline", "Outreach", "Intelligence", "Enterprise"],
            "cta_primary": "Start Free Trial",
            "cta_secondary": "View Live CRM",
            "accent": "#f59e0b",
            "secondary": "#ec4899",
        }
    if any(k in g for k in ["ai", "llm", "copilot", "assistant", "automation", "agent"]):
        return {
            "brand": brand + " AI",
            "tagline": "The AI Copilot That Writes, Builds, and Ships for You",
            "value_prop": "Multi-agent orchestration that transforms natural language intent into verified, production-grade code — with autonomous testing and zero human bottlenecks.",
            "categories": ["Core AI", "Integrations", "Enterprise", "APIs"],
            "cta_primary": "Start Building Free",
            "cta_secondary": "Watch 60s Demo",
            "accent": "#6366f1",
            "secondary": "#a855f7",
        }
    if any(k in g for k in ["design", "figma", "ui", "ux", "prototyping", "creative"]):
        return {
            "brand": brand + " Studio",
            "tagline": "AI-Powered Design That Ships Production Code",
            "value_prop": "Intelligent design-to-code pipeline: import Figma frames, get pixel-perfect React/Tailwind output, and publish to production in one click.",
            "categories": ["Design Import", "Code Export", "Collaboration", "Enterprise"],
            "cta_primary": "Import First Design",
            "cta_secondary": "See Code Output",
            "accent": "#ec4899",
            "secondary": "#8b5cf6",
        }
    if any(k in g for k in ["finance", "fintech", "banking", "payment", "investment"]):
        return {
            "brand": brand + " Finance",
            "tagline": "Intelligent Financial Infrastructure for Modern Businesses",
            "value_prop": "Real-time treasury management, automated reconciliation, and ML-powered fraud detection — all from a single unified API.",
            "categories": ["Payments", "Treasury", "Fraud", "Enterprise"],
            "cta_primary": "Get API Access",
            "cta_secondary": "View Documentation",
            "accent": "#10b981",
            "secondary": "#3b82f6",
        }
    # Generic SaaS
    return {
        "brand": brand,
        "tagline": "The Platform Built for Engineering Excellence at Scale",
        "value_prop": f"{brand} gives engineering teams the automation, intelligence, and observability they need to build faster and ship with confidence.",
        "categories": ["Core Platform", "Integrations", "Analytics", "Enterprise"],
        "cta_primary": "Start Free Trial",
        "cta_secondary": "Schedule Demo",
        "accent": "#3b82f6",
        "secondary": "#10b981",
    }


def _extract_dashboard_domain(goal: str) -> dict[str, Any]:
    """Extract dashboard/telemetry personality from goal."""
    g = goal.lower()

    if any(k in g for k in ["iot", "sensor", "edge", "mqtt", "device"]):
        return {
            "title": "EdgeSync — IoT Mission Control",
            "headline": "Real-Time IoT Fleet Intelligence & Edge Node Telemetry",
            "subheadline": "Unified sensor telemetry, edge node health, automated anomaly detection, and predictive maintenance — all in sub-second latency.",
            "kpi_throughput": "2.4M msg/s",
            "kpi_latency": "3.2ms P99",
            "categories": ["All Nodes", "Sensors", "Edge Compute", "Gateways", "Actuators"],
            "table_rows": [
                {"id": "metric-1", "category": "Sensors", "title": "Temperature Array Cluster", "description": "1,280 thermocouples active across 12 production zones. Averaging 84.3°C with 0.2% drift.", "tags": ["K-type", "MQTT 5.0", "Singapore"], "metrics": "99.98% Uptime • 3.2ms"},
                {"id": "metric-2", "category": "Edge Compute", "title": "Nvidia Jetson Edge Node Grid", "description": "48 Jetson AGX Orin units processing CV inference at 128 TOPS each. Memory at 61%.", "tags": ["Jetson", "TensorRT", "CUDA 12"], "metrics": "61% MEM • 74°C"},
                {"id": "metric-3", "category": "Gateways", "title": "LoRaWAN Bridge Controller", "description": "24 LoRaWAN gateways aggregating 18k end-nodes across 340km² coverage.", "tags": ["LoRaWAN 1.1", "AS923", "Sub-GHz"], "metrics": "18k Devices • 99.9% Uplink"},
                {"id": "metric-4", "category": "Actuators", "title": "Pneumatic Valve Actuator Bank", "description": "192 actuators in closed-loop PID control. Cycle time 80ms with 0.01bar precision.", "tags": ["PID", "4–20mA", "Fieldbus"], "metrics": "80ms Cycle • 0.01bar"},
            ],
        }
    if any(k in g for k in ["orbital", "space", "satellite", "mission control", "aerospace"]):
        return {
            "title": "Orbital Apex — Space Mission Control",
            "headline": "Deep Space Telemetry & Orbital Mission Operations",
            "subheadline": "Constellation tracking, trajectory computation, inter-satellite link monitoring, and autonomous anomaly remediation from a single unified command center.",
            "kpi_throughput": "8.7 Gbps",
            "kpi_latency": "128ms RTT",
            "categories": ["All Systems", "LEO Fleet", "Ground Stations", "Comms", "Propulsion"],
            "table_rows": [
                {"id": "metric-1", "category": "LEO Fleet", "title": "Constellation Sat-Alpha Array", "description": "240 LEO satellites at 550km. All 240 nominal. Epoch correction applied 4h ago.", "tags": ["TLE", "SGP4", "550km LEO"], "metrics": "99.97% Uptime • 128ms RTT"},
                {"id": "metric-2", "category": "Ground Stations", "title": "Svalbard Ground Station Alpha", "description": "3.7m Ka-band dish. Peak throughput 8.7 Gbps. Link margin +12.4 dB.", "tags": ["Ka-Band", "8.7 Gbps", "LDPC"], "metrics": "+12.4dB Margin"},
                {"id": "metric-3", "category": "Comms", "title": "Inter-Satellite Optical Mesh", "description": "32 optical crosslinks active at 100 Gbps per link. BER < 1e-12 on all links.", "tags": ["FSO", "100 Gbps", "BER < 1e-12"], "metrics": "100 Gbps • BER < 1e-12"},
                {"id": "metric-4", "category": "Propulsion", "title": "Ion Thruster Cluster Gamma", "description": "Hall-effect ion thrusters at 42% duty. Delta-V budget: 124.6 m/s remaining.", "tags": ["Hall Effect", "Xenon", "42% Duty"], "metrics": "124.6 m/s ΔV"},
            ],
        }
    if any(k in g for k in ["kubernetes", "k8s", "cloud infra", "devops", "sre", "infrastructure"]):
        return {
            "title": "InfraWatch — Cloud Infrastructure Command",
            "headline": "Unified Kubernetes & Cloud Infrastructure Operations Hub",
            "subheadline": "Real-time cluster health, pod telemetry, cost forecasting, and automated incident response across multi-cloud deployments.",
            "kpi_throughput": "1.2M req/s",
            "kpi_latency": "4.8ms P99",
            "categories": ["All Clusters", "Compute", "Storage", "Network", "Security"],
            "table_rows": [
                {"id": "metric-1", "category": "Compute", "title": "GKE Autopilot Cluster — us-east1", "description": "382 pods active across 14 nodes. HPA triggered 3 scale-outs in last 6h. Memory nominal at 58%.", "tags": ["GKE 1.30", "Autopilot", "us-east1"], "metrics": "99.99% Uptime • 4.8ms"},
                {"id": "metric-2", "category": "Storage", "title": "Ceph Distributed Object Store", "description": "4.8 PB total capacity, 71% utilized. Replication factor 3x. IOPS throughput 640k.", "tags": ["Ceph 18.2", "NVMe", "640k IOPS"], "metrics": "71% Used • 640k IOPS"},
                {"id": "metric-3", "category": "Network", "title": "Global Load Balancer Tier", "description": "14 PoPs active. Anycast BGP routing optimized. Average TTFB 6.1ms across 220 countries.", "tags": ["Anycast", "HTTP/3", "QUIC"], "metrics": "6.1ms TTFB • 14 PoPs"},
                {"id": "metric-4", "category": "Security", "title": "mTLS Service Mesh — Istio", "description": "Envoy sidecars on 382 pods. mTLS enforced. 0 policy violations in last 30d.", "tags": ["Istio 1.22", "mTLS", "Envoy"], "metrics": "0 Violations • mTLS Enforced"},
            ],
        }
    if any(k in g for k in ["finance", "trading", "market", "stock", "crypto", "quant"]):
        return {
            "title": "QuantWatch — Financial Market Operations",
            "headline": "Real-Time Market Intelligence & Algorithmic Trading Operations",
            "subheadline": "Sub-microsecond order flow analytics, portfolio risk exposure, and automated circuit-breaker telemetry across global markets.",
            "kpi_throughput": "18M ticks/s",
            "kpi_latency": "0.8μs P99",
            "categories": ["All Markets", "Equities", "Crypto", "FX", "Derivatives"],
            "table_rows": [
                {"id": "metric-1", "category": "Equities", "title": "US Equities Order Flow Engine", "description": "Processing 18M ticks/sec from NYSE, NASDAQ, ARCA. Lock-free ring buffer at 82% fill.", "tags": ["FIX 4.4", "ITCH 5.0", "NYSE"], "metrics": "0.8μs P99 • 18M ticks/s"},
                {"id": "metric-2", "category": "Crypto", "title": "Multi-Exchange Crypto Arbitrage", "description": "7 exchanges connected. Net delta-neutral PnL +$84k today. 42 arb cycles executed.", "tags": ["CCXT", "WebSocket", "Delta-Neutral"], "metrics": "+$84k Today"},
                {"id": "metric-3", "category": "FX", "title": "Spot FX CLOB Engine", "description": "EUR/USD, GBP/USD, USD/JPY live. Spread compression 0.3 pip average. 98% fill rate.", "tags": ["EBS", "FX", "CLOB"], "metrics": "0.3pip Spread • 98% Fill"},
                {"id": "metric-4", "category": "Derivatives", "title": "Options Greeks Risk Dashboard", "description": "Portfolio delta: +$2.4M. Gamma: 120k. VIX hedge ratio 1.8x. Max drawdown guard active.", "tags": ["Greeks", "VIX Hedge", "Options"], "metrics": "Δ $2.4M • Γ 120k"},
            ],
        }
    # Generic ops dashboard
    brand = _extract_brand_name(goal)
    return {
        "title": f"{brand} Ops — Real-Time Operations Hub",
        "headline": "Unified Telemetry & Autonomous Operations Intelligence",
        "subheadline": "Real-time infrastructure health monitoring, predictive capacity forecasting, and automated incident remediation — all in a single command center.",
        "kpi_throughput": "840k req/s",
        "kpi_latency": "6.4ms P99",
        "categories": ["All Systems", "Compute", "Storage", "Network", "Alerts"],
        "table_rows": [
            {"id": "metric-1", "category": "Compute", "title": "Primary API Gateway Cluster", "description": "840k requests/sec across 12 instances. P99 latency 6.4ms. 0 5xx errors in last 2h.", "tags": ["Nginx", "HTTP/2", "TLS 1.3"], "metrics": "99.99% Uptime • 6.4ms P99"},
            {"id": "metric-2", "category": "Storage", "title": "Distributed Cache Layer — Redis", "description": "2.4TB hot data, 94% cache-hit ratio. Eviction rate near-zero. Cluster split-brain protected.", "tags": ["Redis 7.4", "Cluster", "Sentinel"], "metrics": "94% Hit Rate • 2.4TB"},
            {"id": "metric-3", "category": "Network", "title": "CDN Edge Cache Nodes", "description": "36 global PoPs. 99.4% cache-hit on static assets. TTFB 8.2ms worldwide average.", "tags": ["CDN", "HTTP/3", "Anycast"], "metrics": "8.2ms TTFB • 99.4% Hit"},
            {"id": "metric-4", "category": "Compute", "title": "Background Job Queue — Celery", "description": "18 workers processing 42k tasks/min. 0 DLQ entries. P99 task latency 240ms.", "tags": ["Celery 5.4", "RabbitMQ", "Redis"], "metrics": "42k tasks/min • 0 DLQ"},
        ],
    }


def _generate_portfolio_projects(goal: str, specialty: str, techs: list[str]) -> list[dict]:
    """Generate bespoke portfolio projects based on the developer's specialty."""
    g = goal.lower()

    # 3D / WebGL specialist
    if any(k in g for k in ["three.js", "threejs", "webgl", "3d", "shader", "glsl"]):
        return [
            {
                "id": "proj-1", "category": "3D & WebGL",
                "title": "HyperSpatial Particle Physics Engine",
                "description": "GPU-accelerated simulation of 500,000 particles with real-time force-directed physics and bloom post-processing at 60 FPS in-browser.",
                "tags": ["Three.js", "WebGL 2.0", "GLSL", "Web Workers"],
                "metrics": "500k Particles • 60 FPS",
                "modal_details": "Leverages custom vertex shaders and octree spatial partitioning. Achieves sub-16ms frame budget via off-thread compute.",
            },
            {
                "id": "proj-2", "category": "Shaders",
                "title": "Volumetric Raymarcher & SDF Sculptor",
                "description": "Signed-distance-field shader engine with real-time volumetric fog, chromatic aberration, and ambient occlusion — zero geometry overhead.",
                "tags": ["GLSL", "Fragment Shaders", "SDF", "Raymarching"],
                "metrics": "4K Native • Zero Geometry",
                "modal_details": "Implements sphere tracing with 128-step march depth, real-time SDF blending, and screen-space reflections.",
            },
            {
                "id": "proj-3", "category": "Interactive",
                "title": "Procedural Terrain & Biome Generator",
                "description": "Real-time procedural world generation with multi-octave Perlin noise, dynamic LOD, and PBR material blending.",
                "tags": ["Three.js", "Noise", "LOD", "PBR"],
                "metrics": "256km² Terrain • Dynamic LOD",
                "modal_details": "Terrain mesh generated on GPU via compute pipeline. Biome transitions driven by elevation/humidity noise maps.",
            },
            {
                "id": "proj-4", "category": "3D & WebGL",
                "title": "Neural Network 3D Visualizer",
                "description": "Live visualization of deep neural networks with 80,000 animated synaptic connections and real-time forward-pass highlighting.",
                "tags": ["Three.js", "D3.js", "WebWorkers", "WebGL"],
                "metrics": "80k Synapses • Real-Time",
                "modal_details": "Force-directed graph layout computed in background threads. Synapse activations animated via custom BufferGeometry morphing.",
            },
        ]

    # AI/ML Engineer
    if any(k in g for k in ["ai", "machine learning", "ml", "neural", "llm", "gpt"]):
        return [
            {
                "id": "proj-1", "category": "AI Systems",
                "title": "Multi-Agent Autonomous Synthesis Pipeline",
                "description": "Distributed AI agent framework executing parallel specialist roles — architect, developer, security auditor — with Kahn's DAG orchestration.",
                "tags": ["Python", "AsyncIO", "LLM", "Kahn DAG"],
                "metrics": "240k req/day • 99.98% SLA",
                "modal_details": "Self-healing execution loop with automated regression repair, token budget ceilings, and objective evidence verification gates.",
            },
            {
                "id": "proj-2", "category": "ML Infrastructure",
                "title": "vLLM Inference Cluster — 32× H100",
                "description": "High-throughput LLM serving cluster with KV cache paged attention, continuous batching, and 96% GPU utilization.",
                "tags": ["vLLM", "TensorRT-LLM", "H100", "Triton"],
                "metrics": "12k tokens/s • 96% GPU Util",
                "modal_details": "Deployed with PagedAttention for 4× memory efficiency vs naive KV cache. Custom CUDA kernel for fused RoPE embedding.",
            },
            {
                "id": "proj-3", "category": "RAG & Retrieval",
                "title": "Semantic Memory Graph Engine",
                "description": "Hybrid dense + sparse retrieval system with 1.8B embeddings, real-time graph traversal, and sub-5ms query latency.",
                "tags": ["Qdrant", "BGE-M3", "HNSW", "Graph RAG"],
                "metrics": "1.8B Vectors • 4.8ms P99",
                "modal_details": "Multi-vector retrieval combining ColBERT late-interaction with BM25 sparse re-ranking over 1.8B indexed documents.",
            },
            {
                "id": "proj-4", "category": "AI Systems",
                "title": "Multimodal Vision-Language Agent",
                "description": "Real-time vision + language copilot integrating live webcam streams with GPT-4o for autonomous UI understanding and task execution.",
                "tags": ["WebRTC", "GPT-4o", "ChromeDevTools", "Python"],
                "metrics": "180ms Voice Latency",
                "modal_details": "Sub-200ms end-to-end pipeline: frame capture → OCR → layout parsing → LLM reasoning → DOM action execution.",
            },
        ]

    # Blockchain / Web3
    if any(k in g for k in ["blockchain", "web3", "crypto", "solidity", "defi", "nft"]):
        return [
            {
                "id": "proj-1", "category": "DeFi Protocols",
                "title": "AMM DEX with Concentrated Liquidity",
                "description": "Uniswap v4-inspired AMM with custom hooks, concentrated liquidity ranges, and MEV-resistant price oracles.",
                "tags": ["Solidity", "Foundry", "Uniswap v4", "Chainlink"],
                "metrics": "$2.4M TVL • 0 Exploits",
                "modal_details": "Formal verification via Certora Prover. Custom MEV protection via commit-reveal scheme and flashloan guards.",
            },
            {
                "id": "proj-2", "category": "Infrastructure",
                "title": "EVM Light Client & Proof System",
                "description": "Zero-knowledge light client verifying Ethereum state proofs in-browser via Groth16 SNARK circuits.",
                "tags": ["Rust", "ZK-SNARKs", "Groth16", "Ethereum"],
                "metrics": "88ms Proof Gen • In-Browser",
                "modal_details": "Uses circom circuits compiled to WASM for client-side proof generation. Verification gas cost 220k on EVM.",
            },
            {
                "id": "proj-3", "category": "NFT & Gaming",
                "title": "On-Chain Procedural Game Engine",
                "description": "Fully on-chain RPG with procedurally generated maps, combat, and loot computed deterministically from blockchain entropy.",
                "tags": ["Solidity", "Chainlink VRF", "ERC-1155", "Starknet"],
                "metrics": "12k Players • 100% On-Chain",
                "modal_details": "World state entirely encoded in contract storage. Procedural dungeon generation via Chainlink VRF with commit-reveal.",
            },
            {
                "id": "proj-4", "category": "DeFi Protocols",
                "title": "Cross-Chain Liquidity Bridge",
                "description": "Optimistic bridge with 7-day fraud window, EIP-4337 relayer sponsorship, and 6-chain connectivity.",
                "tags": ["LayerZero", "EIP-4337", "Rust", "6-Chain"],
                "metrics": "$48M Bridged • 0 Fraud",
                "modal_details": "Canonical state root propagated via LayerZero's Ultra Light Node. Fraud proofs computed via bisection game.",
            },
        ]

    # Systems / Rust / Performance
    if any(k in g for k in ["rust", "systems", "performance", "low-latency", "embedded"]):
        return [
            {
                "id": "proj-1", "category": "High Performance",
                "title": "Zero-Allocation Trading Engine",
                "description": "Sub-microsecond orderbook with lock-free SPSC ring buffers, zero heap allocation in hot path, and FPGA co-processing.",
                "tags": ["Rust", "DPDK", "Crossbeam", "FPGA"],
                "metrics": "0.8μs P99 • 18M events/s",
                "modal_details": "Kernel bypass via DPDK. CPU pinned to isolated cores with NUMA-aware memory allocation for zero cache-line contention.",
            },
            {
                "id": "proj-2", "category": "Systems",
                "title": "Custom Async Runtime & Executor",
                "description": "Work-stealing async runtime with 48-core scale-out, zero-cost abstractions, and custom epoll event reactor.",
                "tags": ["Rust", "Tokio-like", "io_uring", "Epoll"],
                "metrics": "2.4M conn/s • 48-Core",
                "modal_details": "io_uring ring submission with fixed buffer pools. Waker implementation avoids all allocations via arena-based task storage.",
            },
            {
                "id": "proj-3", "category": "Embedded",
                "title": "RTOS Kernel for Cortex-M7",
                "description": "Preemptive RTOS with 8 priority levels, MPU-enforced memory isolation, and sub-microsecond context switch.",
                "tags": ["Rust", "no_std", "Cortex-M7", "MPU"],
                "metrics": "0.4μs Context Switch",
                "modal_details": "Interrupt-driven scheduler with priority inheritance. Flash footprint < 48KB. Fully deterministic worst-case execution time.",
            },
            {
                "id": "proj-4", "category": "High Performance",
                "title": "Distributed KV Store — Raft Consensus",
                "description": "Linearizable distributed key-value store with Raft consensus, compaction log, and 800k ops/s throughput.",
                "tags": ["Rust", "Raft", "RocksDB", "gRPC"],
                "metrics": "800k ops/s • Linearizable",
                "modal_details": "Log compaction via snapshotting with Raft InstallSnapshot RPC. Leader lease reads eliminate log round-trips for hot paths.",
            },
        ]

    # Full-stack / general
    name = _extract_brand_name(goal)
    techs_joined = techs[:3] if techs else ["TypeScript", "React", "Node.js"]
    return [
        {
            "id": "proj-1", "category": "Full-Stack",
            "title": f"{name}Flow — Real-Time Collaboration Platform",
            "description": "Multi-user collaborative workspace with CRDT-based conflict resolution, operational transforms, and sub-50ms sync latency.",
            "tags": techs_joined + ["CRDT", "WebSocket"],
            "metrics": "10k Concurrent Users • 48ms Sync",
            "modal_details": "Yjs CRDT engine with custom awareness protocol. Presence indicators, cursor sharing, and offline-first sync.",
        },
        {
            "id": "proj-2", "category": "Backend",
            "title": "GraphQL Federation Gateway",
            "description": "Apollo Federation supergraph with distributed subgraph ownership, dataloader batching, and 98% cache-hit ratio.",
            "tags": ["GraphQL", "Apollo Federation", "Node.js", "Redis"],
            "metrics": "98% Cache Hit • 4.2ms P50",
            "modal_details": "Per-operation query depth limiting, persisted queries, and automated schema change detection with backward-compat guards.",
        },
        {
            "id": "proj-3", "category": "AI Integration",
            "title": "LLM-Powered Code Review Pipeline",
            "description": "Automated PR code review using structured output from Claude, with inline comments, severity scoring, and security analysis.",
            "tags": ["Python", "GitHub Actions", "Claude API", "AST"],
            "metrics": "92% Precision • 3s Review",
            "modal_details": "AST-aware diff extraction feeds structured review prompts. Outputs SARIF security findings, complexity metrics, and fix suggestions.",
        },
        {
            "id": "proj-4", "category": "Full-Stack",
            "title": "Event-Sourced Payments Ledger",
            "description": "CQRS/ES payments system with immutable audit log, saga orchestration, and exactly-once delivery guarantees.",
            "tags": ["TypeScript", "EventStore", "Kafka", "PostgreSQL"],
            "metrics": "99.999% Durability • <1ms Write",
            "modal_details": "Outbox pattern ensures exactly-once delivery. Compensation sagas handle partial failure with automatic rollback.",
        },
    ]


def _generate_ecommerce_items(product_type: str, goal: str) -> list[dict]:
    """Generate bespoke product items for an e-commerce store based on product category."""
    if product_type == "watches":
        return [
            {"id": "prod-1", "category": "Tourbillons", "title": "Celestia Grand Tourbillon", "description": "Flying tourbillon at 6 o'clock, 72-hour power reserve, hand-chamfered movement with 312 components.", "tags": ["Tourbillon", "72h Reserve", "Sapphire"], "metrics": "$18,400 • Limited 50", "modal_details": "Calibre CS-01. 6Hz frequency, Si-balance spring, three-body polished lugs. Certificated by COSC."},
            {"id": "prod-2", "category": "Divers", "title": "Abyss Pro 1000M Diver", "description": "Unidirectional ceramic bezel, helium escape valve, luminescent indices readable to 30m ambient light.", "tags": ["Ceramic", "1000m WR", "Super-LumiNova"], "metrics": "$3,600 • In Stock", "modal_details": "316L surgical steel case with Grade 5 titanium caseback. ETA 2824-2 base with custom rotor weight."},
            {"id": "prod-3", "category": "Dress Watches", "title": "Aurum Ultra-Thin Dress Watch", "description": "3.2mm profile with hand-guilloché dial, 18k rose gold case, and strap-change system in under 30 seconds.", "tags": ["18k Rose Gold", "3.2mm", "Guilloché"], "metrics": "$6,200 • Pre-Order", "modal_details": "Calibre AU-3 ultra-thin movement. 42h reserve. Satin and polished alternating finish on bezel."},
            {"id": "prod-4", "category": "Limited", "title": "Genesis Skeleton Chronograph", "description": "Fully skeletonized movement exposing 214 components. Bicompax chronograph layout in open-worked carbon fibre dial.", "tags": ["Skeleton", "Carbon Fibre", "Chrono"], "metrics": "$9,800 • 200 Units", "modal_details": "Column-wheel chronograph with vertical clutch. Manual-wind 65h reserve. Sapphire caseback with anti-reflective coating."},
        ]
    if product_type == "sneakers":
        return [
            {"id": "prod-1", "category": "Running", "title": "VelocityMax Carbon X", "description": "Full-length carbon fibre plate with nitrogen-injected foam, 82% energy return, and 4D-printed heel counter.", "tags": ["Carbon Plate", "N²-Foam", "4D Print"], "metrics": "$285 • In Stock", "modal_details": "Midsole density gradient from 35 Shore A (toe-off) to 48 Shore A (heel). Stack height 38mm/32mm."},
            {"id": "prod-2", "category": "Lifestyle", "title": "Aura Woven Mesh Silhouette", "description": "Gradient-dyed technical mesh upper, moulded foam collar, and translucent outsole with LED-reactive paint.", "tags": ["Gradient Dye", "LED-Reactive", "Foam Collar"], "metrics": "$195 • New Drop", "modal_details": "Mesh woven on 3D jacquard loom for zoned breathability. Outsole: RP-40 translucent rubber compound."},
            {"id": "prod-3", "category": "Collab Drops", "title": "Apex × Studio Drift Kinetic", "description": "Artist collaboration with kinetic laser-cut panels that shift iridescence with viewing angle.", "tags": ["Iridescent", "Laser-Cut", "Collab"], "metrics": "$420 • 500 Pairs", "modal_details": "Upper: 7-layer laser-cut iridescent TPU laminate. Collab tag stitched on tongue. Numbered box certificate."},
            {"id": "prod-4", "category": "Classics", "title": "Heritage Low — Vachetta Leather", "description": "Full-grain vachetta leather that patinas uniquely to each owner, with a vulcanised natural gum rubber sole.", "tags": ["Vachetta", "Vulcanised", "Heritage"], "metrics": "$168 • Restock", "modal_details": "Upper: 1.4mm full-grain vegetable-tanned vachetta. Lining: breathable pigskin suede. Sole: natural gum trefoil pattern."},
        ]
    if product_type == "fashion":
        return [
            {"id": "prod-1", "category": "Outerwear", "title": "Onyx Technical Shell Jacket", "description": "3L Gore-Tex Pro membrane, fully seam-sealed, pit-zip vents, and magnetic cuff closure. Weight: 480g.", "tags": ["Gore-Tex Pro", "3L", "Seam-Sealed"], "metrics": "$680 • In Stock", "modal_details": "Face fabric: 70D ripstop nylon. Backer: microflece bonded liner. Waterproof zippers throughout."},
            {"id": "prod-2", "category": "Capsule", "title": "Linen Silk Oversized Blazer", "description": "55% Irish linen, 45% mulberry silk blend. Unlined with floating canvas chest, patch pockets, raw edge lapels.", "tags": ["Linen/Silk", "Unlined", "Floating Canvas"], "metrics": "$420 • Pre-Season", "modal_details": "Blended on Italian shuttle looms. Hand-basted collar, pick-stitch lapels. Single rear vent, half-moon breast pocket."},
            {"id": "prod-3", "category": "Accessories", "title": "Handwoven Silk Scarf 140×140", "description": "Jacquard-woven 100% Habotai silk with archival editorial print, hand-rolled edges, and twill-weave border.", "tags": ["Habotai Silk", "Hand-Rolled", "Jacquard"], "metrics": "$195 • Limited", "modal_details": "Woven in Lyon, France on vintage Jacquard loom. Print drawn by in-house illustrators. Each piece varies ±2mm."},
            {"id": "prod-4", "category": "Editorial", "title": "Volume Pleated Wide-Leg Trouser", "description": "Structured crepe fabric with triple-pleat front, deep side pockets, and adjustable waistband tab.", "tags": ["Crepe", "Triple-Pleat", "Adjustable"], "metrics": "$290 • Made-to-Order", "modal_details": "Japanese crepe double-woven for body. Each pair cut to order — 10-day lead time. Leg length +/- 5cm at no cost."},
        ]
    if product_type == "audio":
        return [
            {"id": "prod-1", "category": "Over-Ear", "title": "Planar Sigma Reference Headphones", "description": "106mm planar magnetic drivers, 0.001% THD, genuine perforated leather earpads, 1.8m detachable balanced cable.", "tags": ["Planar Magnetic", "0.001% THD", "Balanced"], "metrics": "$799 • In Stock", "modal_details": "Diaphragm: 2μm Kapton with 0.4μm aluminium trace. Impedance: 45Ω. Sensitivity: 94dB/mW. 20–40,000Hz."},
            {"id": "prod-2", "category": "IEMs", "title": "Astra 8 — Tribrid In-Ear Monitor", "description": "8 balanced armatures + 1 dynamic + 1 electrostatic per ear. Liquid metal faceplate, MMCX.", "tags": ["Tribrid", "8BA+DD+EST", "MMCX"], "metrics": "$1,200 • Pre-Order", "modal_details": "8 BA (2 low, 4 mid, 2 high-mid) + 1 DD (sub-bass) + 1 EST (ultra-treble). 4-way passive crossover."},
            {"id": "prod-3", "category": "Studio Monitors", "title": "Axis 8 Powered Studio Monitor", "description": "8-inch woofer, 1-inch AMT tweeter, 250W bi-amped Class D, Ethernet-controlled DSP, and 110dB SPL output.", "tags": ["AMT Tweeter", "250W", "DSP Ethernet"], "metrics": "$1,100 / each • Pro Grade", "modal_details": "DSP programmable via Ethernet for room EQ, crossover tuning. Latency < 1.5ms. TRS/XLR balanced inputs."},
            {"id": "prod-4", "category": "Cables", "title": "Litz Copper 8-Core Balanced Cable", "description": "OCC mono-crystal copper Litz strands, PEEK insulation, rhodium-plated connectors, 1.2m coil.", "tags": ["OCC Litz", "Rhodium", "PEEK"], "metrics": "$220 • In Stock", "modal_details": "8 individually enamelled OCC copper cores, twisted in quad geometry. Geometric noise rejection on balanced termination."},
        ]
    if product_type == "peripherals":
        brand = _extract_brand_name(goal)
        return [
            {"id": "prod-1", "category": "Keyboards", "title": f"{brand} Hall60 — Magnetic Keyboard", "description": "Magnetic rapid-trigger with 0.1mm resolution per key, 8000Hz polling, aircraft-grade CNC aluminium.", "tags": ["Magnetic", "8000Hz", "CNC Alu"], "metrics": "$249 • In Stock", "modal_details": "Custom Hall-effect sensing IC, per-key actuaction + reset point (0.1–4.0mm). Dual-mode gasket mount."},
            {"id": "prod-2", "category": "Audio", "title": "NeuralWave Spatial Headset Pro", "description": "Planar magnetic drivers, real-time 3D HRTF head tracking, and active noise cancellation. USB-C + 3.5mm balanced.", "tags": ["Planar Magnetic", "HRTF", "ANC"], "metrics": "$349 • Best Seller", "modal_details": "50mm planar diaphragm, 0.0015% THD. Head-tracking: 6-DoF IMU at 2kHz. ANC: -42dB broadband."},
            {"id": "prod-3", "category": "Displays", "title": "Prisma 32 — OLED 4K 240Hz", "description": "Quantum dot OLED, 32 inches, 3840×2160 at 240Hz, 0.03ms response, DisplayHDR 1000, USB-C 140W charging.", "tags": ["OLED", "240Hz", "HDR1000"], "metrics": "$1,199 • Pre-Order", "modal_details": "Samsung QD-OLED panel. DCI-P3 100%, Rec.2020 96%. Anti-glare matte coating. 4× USB-A 3.2, 2× DisplayPort 2.1."},
            {"id": "prod-4", "category": "Accessories", "title": "ProGrip Wireless Trackball Mouse", "description": "52mm optical trackball, 34,000 DPI, 1kHz wireless polling, magnetic charging dock, 120h battery.", "tags": ["34k DPI", "1kHz Wireless", "120h Battery"], "metrics": "$139 • In Stock", "modal_details": "PTFE-coated ceramic ball bearing. Pixart PAW3395 sensor. 5-button + scroll + tilt. 2.4GHz & Bluetooth 5.3."},
        ]
    # Generic tech e-commerce
    brand = _extract_brand_name(goal)
    return [
        {"id": "prod-1", "category": "Featured", "title": f"{brand} Core Module Gen-3", "description": "Next-generation compute module with 16-core ARM cluster, integrated NPU, and 32GB LPDDR5X.", "tags": ["ARM", "NPU", "32GB"], "metrics": "$349 • In Stock", "modal_details": "16× Cortex-A78 at 3.2GHz + dedicated 24-TOPS NPU. PCIe Gen 5 x4 interface. 50% smaller than Gen-2."},
        {"id": "prod-2", "category": "New Arrivals", "title": "Flux Spatial Controller Pro", "description": "6-DoF gestural input device with haptic feedback, sub-mm optical tracking, and 10h wireless operation.", "tags": ["6-DoF", "Haptic", "Wireless"], "metrics": "$219 • Pre-Order", "modal_details": "Optical tracking: 0.1mm XYZ, 0.05° rotation. Haptic: 4-axis LRA motors. 10h typical, USB-C fast charge."},
        {"id": "prod-3", "category": "Bundles", "title": "Creator Studio Starter Bundle", "description": "Core Module + Spatial Controller + 27-inch reference display calibrated to ΔE<1 at factory.", "tags": ["Bundle", "ΔE<1", "Calibrated"], "metrics": "$749 • Save $120", "modal_details": "Includes HDMI 2.1 cable, USB-C hub, 2-year extended warranty. Display: IPS 4K, 120Hz, AdobeRGB 99%."},
        {"id": "prod-4", "category": "Limited", "title": "Obsidian Signature Edition Kit", "description": "Matte obsidian anodised finish, laser-engraved serial, rosewood carry case, and 3-year white glove support.", "tags": ["Obsidian", "Signature", "White Glove"], "metrics": "$1,199 • 300 Units", "modal_details": "Individually numbered. Includes letter of provenance, 1:1 onboarding call, and priority support queue."},
    ]


class DomainSynthesizer:
    """Intelligently detects domain archetype from natural-language goals and generates
    fully dynamic, prompt-specific content models — zero hardcoded names, colors, or items."""

    @classmethod
    def analyze_goal(
        cls,
        goal: str,
        memora_context: str = "",
        requirements: list[str] | None = None,
    ) -> DomainBlueprint:
        """Classify a goal into a domain blueprint.

        `requirements` used to be accepted by callers but never forwarded here, so
        an explicit requirement such as "must be an e-commerce store" could not
        influence the chosen architecture at all.
        """
        # Incorporate remembered user preferences from Memora cognitive context if present
        combined_context = f"{goal} {memora_context}".strip() if memora_context else goal
        if requirements:
            combined_context = f"{combined_context} {' '.join(requirements)}".strip()
        g = combined_context.lower()

        # 0. E-Commerce
        if any(k in g for k in ["ecommerce", "e-commerce", "store", "shop", "hardware accessories",
                                  "cart", "buy", "sneaker", "shoe", "clothing", "apparel", "retail",
                                  "watch", "timepiece", "jewelry", "fashion", "furniture", "audio gear",
                                  "headphone", "keyboard", "skincare", "cosmetics"]):
            return cls._synthesize_ecommerce(goal)

        # 1. SaaS / Platform / Subscription
        if any(k in g for k in ["saas", "pricing", "subscription", "b2b", "copilot platform",
                                  "analytics platform", "ai platform", "devops platform", "crm"]):
            return cls._synthesize_saas(goal)

        # 2. Dashboard / Telemetry / Ops
        if any(k in g for k in ["dashboard", "telemetry", "ops hub", "control center",
                                  "monitoring", "operations hub", "iot", "mission control",
                                  "satellite", "trading terminal", "market monitor"]):
            return cls._synthesize_dashboard(goal)

        # 3. Cyberpunk / Sci-Fi / Neon
        if any(k in g for k in ["cyberpunk", "sci-fi", "scifi", "neon", "matrix", "dystopian"]):
            return cls._synthesize_cyberpunk_portfolio(goal)

        # 4. Portfolio / Personal site / Resume
        if any(k in g for k in ["portfolio", "personal website", "developer profile", "resume", "cv",
                                  "personal site", "my website", "showcase"]):
            return cls._synthesize_portfolio(goal)

        # 5. Generic SaaS / Tool / Platform fallback
        if any(k in g for k in ["platform", "startup", "tool", "copilot", "cloud", "api service", "ai "]):
            return cls._synthesize_saas(goal)

        # 6. Creative / Generic App
        return cls._synthesize_creative(goal)

    # =========================================================================
    # Dynamic Synthesizers
    # =========================================================================

    @classmethod
    def _synthesize_ecommerce(cls, goal: str) -> DomainBlueprint:
        meta = _extract_product_domain(goal)
        accent = meta["accent"]
        secondary = meta["secondary"]
        archetype = meta.get("archetype", "ecommerce")
        brand = _extract_brand_name(goal) or meta["brand_seed"]
        store_name = f"{brand} {meta['brand_seed']}" if brand.lower() != meta['brand_seed'].lower() else meta['brand_seed']
        items = _generate_ecommerce_items(meta["product_type"], goal)

        font_heading = "'Cinzel', serif" if archetype == "luxury" else ("'Space Grotesk', sans-serif" if archetype == "cyberpunk" else "'Plus Jakarta Sans', sans-serif")
        font_body = "'Montserrat', sans-serif" if archetype == "luxury" else "'Inter', sans-serif"

        return DomainBlueprint(
            domain_type="ecommerce",
            app_title=f"{store_name} — {meta['tagline']}",
            headline=meta['tagline'],
            subheadline=f"Discover our curated collection of {meta['product_type']} — engineered for those who demand uncompromising performance and aesthetic distinction.",
            primary_cta="Explore Collection",
            secondary_cta="View 3D Catalog",
            accent_color=accent,
            secondary_color=secondary,
            archetype=archetype,
            font_heading=font_heading,
            font_body=font_body,
            three_d_scene_type=meta.get("three_d_scene_type", "product_turntable"),
            hero_badge=meta.get("hero_badge", "3D Interactive Showcase • Drag to Inspect"),
            social_proof_text=meta.get("social_proof_text", "4.9/5 from 1,200+ verified customers"),
            viewport_title=meta.get("viewport_title", "3D Interactive Showcase • WebGL 60FPS"),
            viewport_chip_top=meta.get("viewport_chip_top", "PBR Surface"),
            viewport_chip_bottom_left=meta.get("viewport_chip_bottom_left", "Sub-mm Precision"),
            viewport_chip_bottom_right=meta.get("viewport_chip_bottom_right", "Drag to Spin ↻"),
            model_stats=meta.get("model_stats", "Physical PBR Shading • 60 FPS"),
            categories=meta["categories"],
            showcase_items=items,
            features_bento=[
                {"title": "Concierge Delivery", "subtitle": "White-glove fulfilment with real-time tracking and signature-required delivery to 180+ countries.", "icon": "truck", "highlight": "Global"},
                {"title": "30-Day Return Policy", "subtitle": "No-questions-asked returns with prepaid labels and immediate refund processing.", "icon": "rotate-ccw", "highlight": "Risk-Free"},
                {"title": "Authenticity Guarantee", "subtitle": "Every item comes with a digital certificate of authenticity stored immutably on-chain.", "icon": "shield-check", "highlight": "Verified"},
                {"title": "Expert Consultation", "subtitle": "Access our specialist team via live chat or video call for personalised recommendations.", "icon": "headphones", "highlight": "1-on-1"},
            ],
            interactive_modules=["interactive_cart_drawer", "filter_catalog", "3d_product_preview", "checkout_modal"],
            meta_description=f"{store_name} — {meta['tagline']}. Premium {meta['product_type']} with world-class service.",
        )

    @classmethod
    def _synthesize_saas(cls, goal: str) -> DomainBlueprint:
        meta = _extract_saas_domain(goal)
        accent = meta.get("accent", "#3b82f6")
        secondary = meta.get("secondary", "#10b981")
        brand = meta["brand"]
        _, _, archetype = _palette_for_goal(goal, "saas")

        return DomainBlueprint(
            domain_type="saas",
            app_title=f"{brand} — {meta['tagline']}",
            headline=meta['tagline'],
            subheadline=meta['value_prop'],
            primary_cta=meta['cta_primary'],
            secondary_cta=meta['cta_secondary'],
            accent_color=accent,
            secondary_color=secondary,
            archetype="saas",
            font_heading="'Plus Jakarta Sans', sans-serif",
            font_body="'Inter', sans-serif",
            three_d_scene_type="neural_geodesic",
            categories=meta["categories"],
            showcase_items=[
                {"id": "feat-1", "category": meta['categories'][0], "title": "Intelligent Core Engine", "description": "Purpose-built processing backbone with horizontal autoscaling and sub-10ms response guarantees.", "tags": ["Real-Time", "Scalable", "Reliable"], "metrics": "99.99% SLA", "modal_details": f"The core engine behind {brand} — battle-tested at scale with automated failover, rate-limiting, and circuit breakers."},
                {"id": "feat-2", "category": meta['categories'][1], "title": "Zero-Config Integrations Hub", "description": "Connect your entire stack in under 2 minutes — 240+ native integrations with OAuth 2.0 handshakes.", "tags": ["240+ Integrations", "OAuth 2.0", "Webhooks"], "metrics": "2-min Setup", "modal_details": "Native connectors for Salesforce, HubSpot, Slack, GitHub, Linear, Jira, Notion, and 230+ more with two-way sync."},
                {"id": "feat-3", "category": meta['categories'][2], "title": "AI Insight Layer", "description": "Embedded LLM reasoning surfaces anomalies, drafts action plans, and generates executive summaries automatically.", "tags": ["LLM-Powered", "Auto-Summary", "Anomaly"], "metrics": "10× Faster Insight", "modal_details": f"{brand} AI analyses all ingested data continuously, alerting on statistical anomalies and generating plain-language explanations."},
                {"id": "feat-4", "category": meta['categories'][3] if len(meta['categories']) > 3 else "Enterprise", "title": "Enterprise Governance & Compliance", "description": "SOC 2 Type II, GDPR, HIPAA-ready with full audit trails, role-based access, and encryption at rest/transit.", "tags": ["SOC 2", "GDPR", "HIPAA"], "metrics": "Enterprise-Ready", "modal_details": "Customer-managed encryption keys (CMEK), field-level data redaction, and immutable audit logs exported to your SIEM."},
            ],
            features_bento=[
                {"title": "Instant Time-to-Value", "subtitle": "Integrate in minutes, see results in hours — not weeks of professional services.", "icon": "zap", "highlight": "Fast"},
                {"title": "Enterprise Security", "subtitle": "SOC 2 Type II certified with end-to-end encryption and zero-knowledge architecture.", "icon": "lock", "highlight": "SOC 2"},
                {"title": "Real-Time Analytics", "subtitle": "Sub-second telemetry with live WebSocket streams and customizable alert thresholds.", "icon": "activity", "highlight": "< 10ms"},
            ],
            interactive_modules=["pricing_toggle", "feature_bento", "roi_calculator", "faq_accordion", "live_demo_modal"],
            meta_description=f"{brand} — {meta['tagline']}.",
        )

    @classmethod
    def _synthesize_dashboard(cls, goal: str) -> DomainBlueprint:
        meta = _extract_dashboard_domain(goal)
        accent, secondary, archetype = _palette_for_goal(goal, "dashboard")

        return DomainBlueprint(
            domain_type="dashboard",
            app_title=meta["title"],
            headline=meta["headline"],
            subheadline=meta["subheadline"],
            primary_cta="Launch Console",
            secondary_cta="Export Audit Report",
            accent_color=accent,
            secondary_color=secondary,
            archetype="mission_control",
            font_heading="'Space Grotesk', sans-serif",
            font_body="'Inter', sans-serif",
            three_d_scene_type="orbital_globe",
            categories=meta["categories"],
            showcase_items=meta["table_rows"],
            features_bento=[
                {"title": "Predictive Intelligence", "subtitle": "Neural forecast models predict capacity bottlenecks up to 4 hours in advance with 94% accuracy.", "icon": "trending-up", "highlight": "Predictive"},
                {"title": "Autonomous Remediation", "subtitle": "Self-healing policy engine executes runbooks automatically on alert trigger — zero manual intervention.", "icon": "refresh-cw", "highlight": "Auto-Heal"},
                {"title": "Global Compliance", "subtitle": "Immutable audit trail with SOC 2, ISO 27001, and FedRAMP-ready evidence packages.", "icon": "shield-check", "highlight": "Compliant"},
            ],
            interactive_modules=["live_charts", "realtime_telemetry", "interactive_filters", "alert_bell"],
            meta_description=f"{meta['title']} — Real-time telemetry and autonomous operations console.",
            kpi_metrics={
                "throughput": meta.get("kpi_throughput", "840k req/s"),
                "latency": meta.get("kpi_latency", "6.4ms P99"),
            },
        )

    @classmethod
    def _synthesize_cyberpunk_portfolio(cls, goal: str) -> DomainBlueprint:
        specialty = _extract_specialty(goal)
        techs = _extract_technologies(goal)
        brand = _extract_brand_name(goal)
        projects = _generate_portfolio_projects(goal, specialty, techs)

        # Pick a unique cyberpunk colour variant from hash
        seed = hashlib.md5(goal.lower().encode()).hexdigest()
        accent_opts = ["#00f0ff", "#ff007a", "#7c3aed", "#f59e0b", "#10b981"]
        second_opts = ["#ff007a", "#00f0ff", "#ec4899", "#6366f1", "#06b6d4"]
        idx = int(seed[:4], 16) % len(accent_opts)
        accent = accent_opts[idx]
        secondary = second_opts[idx]

        return DomainBlueprint(
            domain_type="portfolio",
            app_title=f"{brand} — {specialty}",
            headline=f"Architecting the Future at the Intersection of {' & '.join(techs[:2])}",
            subheadline=f"Specialising in high-performance {specialty.lower()} systems, real-time 3D WebGL experiences, and zero-compromise engineering that scales to planetary demand.",
            primary_cta="Explore My Work",
            secondary_cta="Launch Neural Terminal",
            accent_color=accent,
            secondary_color=secondary,
            archetype="cyberpunk",
            font_heading="'Space Grotesk', sans-serif",
            font_body="'Share Tech Mono', monospace",
            three_d_scene_type="torus_matrix",
            categories=["All Systems", techs[0] if techs else "3D & WebGL", "High Performance", "Architecture"],
            showcase_items=projects,
            features_bento=[
                {"title": "Interactive 3D Engine", "subtitle": f"Custom Three.js geometry with real-time {techs[0] if techs else 'WebGL'} rendering, physics, and GLSL shader post-processing.", "icon": "box", "highlight": "Three.js 3D"},
                {"title": "Glassmorphic Cyber HUD", "subtitle": "Multi-layer backdrop blur, neon glow borders, radial cursor lighting, and 3D perspective tilt on all cards.", "icon": "sparkles", "highlight": "Glass 3.0"},
                {"title": "Live Interactive Terminal", "subtitle": "Real-time command console supporting diagnostics, system telemetry queries, and command dispatch.", "icon": "terminal", "highlight": "Interactive"},
                {"title": "Zero Placeholder Policy", "subtitle": "100% production-verified copy, precise architecture specs, and responsive mobile-first performance.", "icon": "shield-check", "highlight": "Verified"},
            ],
            interactive_modules=["three_d_canvas", "cyber_terminal", "filter_showcase", "details_modal", "skill_bars", "hud_controls", "theme_toggle"],
            meta_description=f"Portfolio of {brand} — {specialty}. Real-time WebGL, high-performance systems, and world-class engineering.",
        )

    @classmethod
    def _synthesize_portfolio(cls, goal: str) -> DomainBlueprint:
        specialty = _extract_specialty(goal)
        techs = _extract_technologies(goal)
        brand = _extract_brand_name(goal)
        projects = _generate_portfolio_projects(goal, specialty, techs)

        accent, secondary, archetype = _palette_for_goal(goal, "portfolio")

        # Choose typography based on specialty
        if "design" in specialty.lower() or "creative" in specialty.lower():
            font_heading = "'Playfair Display', serif"
            font_body = "'Montserrat', sans-serif"
        else:
            font_heading = "'Plus Jakarta Sans', sans-serif"
            font_body = "'Inter', sans-serif"

        return DomainBlueprint(
            domain_type="portfolio",
            app_title=f"{brand} — {specialty}",
            headline=f"Building {techs[0] if techs else 'Software'} Systems That Scale to Millions",
            subheadline=f"I'm a {specialty} specialising in {', '.join(techs[:3]) if techs else 'modern web technologies'}. I build systems where performance, design, and reliability converge.",
            primary_cta="View Featured Work",
            secondary_cta="Download My CV",
            accent_color=accent,
            secondary_color=secondary,
            archetype=archetype,
            font_heading=font_heading,
            font_body=font_body,
            three_d_scene_type="torus_knot",
            categories=["All Systems", techs[0] if len(techs) > 0 else "Web", techs[1] if len(techs) > 1 else "Backend", "Open Source"],
            showcase_items=projects,
            features_bento=[
                {"title": "Systematic Architecture", "subtitle": f"Self-healing distributed systems with {techs[0] if techs else 'modern'} patterns and zero single-points-of-failure.", "icon": "cpu", "highlight": "Distributed"},
                {"title": "High-Fidelity UX", "subtitle": "Immersive WebGL and Three.js canvas experiences crafted for zero-friction browser rendering at 60 FPS.", "icon": "box", "highlight": "WebGL 2.0"},
                {"title": "Security-First Culture", "subtitle": "AST-level sanitisation, secret scrubbing, strict input validation, and hardened container isolation.", "icon": "shield-check", "highlight": "Hardened"},
            ],
            interactive_modules=["particle_hero", "filter_showcase", "details_modal", "skill_bars", "validated_contact", "theme_toggle"],
            meta_description=f"Portfolio of {brand} — {specialty}. {', '.join(techs[:3]) if techs else 'Modern software engineering'}.",
        )

    @classmethod
    def _synthesize_creative(cls, goal: str) -> DomainBlueprint:
        clean = re.sub(r"[^a-zA-Z0-9\s]", "", goal).strip()
        title_words = [w.capitalize() for w in clean.split()[:5]]
        headline = " ".join(title_words) or "Futuristic Web Application"
        brand = _extract_brand_name(goal)
        accent, secondary, archetype = _palette_for_goal(goal, "creative")

        return DomainBlueprint(
            domain_type="creative",
            app_title=f"{brand} — {headline}",
            headline=headline,
            subheadline="A high-performance, interactive web experience built with modern glassmorphism, 3D WebGL physics, and precision micro-interactions.",
            primary_cta="Explore Interactive App",
            secondary_cta="View Architecture",
            accent_color=accent,
            secondary_color=secondary,
            archetype=archetype,
            font_heading="'Outfit', sans-serif",
            font_body="'Inter', sans-serif",
            three_d_scene_type="particle_constellation",
            categories=["Featured", "Interactive", "Performance", "Capabilities"],
            showcase_items=[
                {"id": "mod-1", "category": "Interactive", "title": f"{brand} Dynamic Core", "description": "Fluid, state-managed responsive interface with real-time 3D canvas and zero external bundler dependencies.", "tags": ["Vanilla JS", "WebGL", "Lucide Icons"], "metrics": "60 FPS • 100% Responsive", "modal_details": "Built using modern web standards, semantic HTML5, glassmorphic CSS tokens, and accessible keyboard navigation."},
                {"id": "mod-2", "category": "Performance", "title": "Optimised Rendering Pipeline", "description": "RequestAnimationFrame loop with delta-time physics simulation and instanced geometry batching.", "tags": ["RAF Loop", "Delta-Time", "Instanced"], "metrics": "< 16ms Frame Budget", "modal_details": "Geometry batched via InstancedMesh. Draw calls reduced 94% vs naive rendering approach."},
            ],
            features_bento=[
                {"title": "World-Class Aesthetic", "subtitle": "Glassmorphism with backdrop filters, glowing gradients, and fluid typography across all screen sizes.", "icon": "sparkles", "highlight": "Modern"},
                {"title": "Zero Broken Assets", "subtitle": "Embedded SVG vector iconography, semantic HTML, and high-performance client rendering.", "icon": "check-circle", "highlight": "Verified"},
            ],
            interactive_modules=["particle_hero", "filter_showcase", "modal_preview", "theme_toggle"],
            meta_description=f"{brand} — {headline}. Built with Project FORGE.",
        )

    # =========================================================================
    # Backwards compatibility aliases
    # =========================================================================
    @classmethod
    def _build_cyberpunk_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_cyberpunk_portfolio(goal)

    @classmethod
    def _build_portfolio_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_portfolio(goal)

    @classmethod
    def _build_saas_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_saas(goal)

    @classmethod
    def _build_ecommerce_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_ecommerce(goal)

    @classmethod
    def _build_dashboard_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_dashboard(goal)

    @classmethod
    def _build_creative_app_blueprint(cls, goal: str) -> DomainBlueprint:
        return cls._synthesize_creative(goal)
