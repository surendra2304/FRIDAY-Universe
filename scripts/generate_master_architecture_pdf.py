import os
import sys
import shutil
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 7)
        self.setFillColor(colors.HexColor("#475569"))
        
        # Header on pages > 1
        if self._pageNumber > 1:
            self.drawString(36, 11 * inch - 24, "THE FRIDAY UNIVERSE — DEFINITIVE MASTER ARCHITECTURE & TECHNICAL CODEX")
            self.setFont("Helvetica", 7)
            self.drawRightString(8.5 * inch - 36, 11 * inch - 24, "SOVEREIGN 10-AGENT ECOSYSTEM // SPECIFICATION V3.0.0")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(36, 11 * inch - 28, 8.5 * inch - 36, 11 * inch - 28)
        
        # Footer on all pages
        self.setFont("Helvetica", 7)
        self.drawString(36, 20, "CONFIDENTIAL & PROPRIETARY — FRIDAY MASTER ARCHITECTURE SPECIFICATION")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 36, 20, page_text)
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(36, 28, 8.5 * inch - 36, 28)
        self.restoreState()

def build_pdf(pdf_path):
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    # Typography Hierarchy
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=3
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=colors.HexColor('#2563EB'),
        spaceAfter=6
    )

    desc_style = ParagraphStyle(
        'DocDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11.5,
        textColor=colors.HexColor('#475569'),
        spaceAfter=8
    )

    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11.5,
        leading=14.5,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'Heading2_Custom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=colors.HexColor('#1E293B'),
        spaceBefore=7,
        spaceAfter=3,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10.5,
        textColor=colors.HexColor('#334155'),
        spaceAfter=5
    )

    bullet_style = ParagraphStyle(
        'Bullet_Custom',
        parent=body_style,
        leftIndent=12,
        firstLineIndent=-8,
        spaceAfter=3
    )

    code_style = ParagraphStyle(
        'Code_Custom',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#0F172A')
    )

    table_header = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#FFFFFF')
    )

    table_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=6.5,
        leading=8.5,
        textColor=colors.HexColor('#1E293B')
    )

    story = []

    def make_table(headers, rows, col_widths):
        data = [[Paragraph(h, table_header) for h in headers]]
        for row in rows:
            data.append([Paragraph(cell, table_cell) if isinstance(cell, str) else cell for cell in row])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#FFFFFF'), colors.HexColor('#F8FAFC')])
        ]))
        return t

    def make_callout(title, text_content, bg_hex="#EFF6FF", border_hex="#3B82F6"):
        title_p = Paragraph(f"<b>{title}</b>", ParagraphStyle('CallTitle', parent=body_style, fontName='Helvetica-Bold', textColor=colors.HexColor(border_hex), fontSize=7.5, leading=10))
        body_p = Paragraph(text_content, ParagraphStyle('CallBody', parent=body_style, fontSize=7, leading=9.5))
        box = Table([[title_p], [body_p]], colWidths=[540])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor(bg_hex)),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor(border_hex)),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return box

    def make_code_box(code_lines):
        code_p = Paragraph("<br/>".join(code_lines), code_style)
        box = Table([[code_p]], colWidths=[540])
        box.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F1F5F9')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        return box

    # =========================================================================
    # COVER / HEADER
    # =========================================================================
    story.append(Paragraph("THE FRIDAY UNIVERSE", title_style))
    story.append(Paragraph("DEFINITIVE MASTER ARCHITECTURE & TECHNICAL CODEX — SPECIFICATION V3.0.0", subtitle_style))
    story.append(Paragraph(
        "<b>Authoritative Engineering Specification:</b> Unified 10-Agent Sovereign AI Operating System, Dual AMD Micro Server Fleet "
        "(<code>140.245.208.100</code> & <code>140.245.243.168</code>), Dual Oracle Cloud Autonomous 23ai Relational & Vector Stores, "
        "Zero-Disk In-Memory Persistence, and Granular GitHub Actions CI/CD Synchronization.",
        desc_style
    ))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563EB"), spaceAfter=8))

    # =========================================================================
    # SECTION 1: EXECUTIVE SUMMARY & CORE INVARIANTS
    # =========================================================================
    story.append(Paragraph("1. Executive Summary & Sovereign Multi-Agent Philosophy", h1_style))
    story.append(Paragraph(
        "<b>The FRIDAY Universe</b> is an enterprise-grade autonomous cognitive architecture comprising ten specialized agent subsystems. "
        "The system operates across high-efficiency Oracle Cloud Infrastructure (OCI) Always Free hardware ($0.00 compute boundary) with zero persistent "
        "SQLite or PostgreSQL files on local VM disks. All relational state, vector embeddings, and audit trails reside in two Oracle Autonomous 23ai cloud databases.",
        body_style
    ))

    story.append(make_callout(
        "FIVE NON-NEGOTIABLE OPERATIONAL INVARIANTS",
        "<b>1. Strict Proper Naming Only:</b> Exact names: <code>FRIDAY</code>, <code>Inference</code>, <code>Memora</code>, <code>Stratex</code>, <code>Futuris</code>, <code>IntelX</code>, <code>Forge</code>, <code>VyralX</code>, <code>Sentinel</code>, <code>Cortex</code>. No hyphens or abbreviations.<br/>"
        "<b>2. Zero Local Disk SQLite/Postgres:</b> No <code>.db</code> or <code>.sqlite</code> files on persistent VM storage. Temporary in-memory buffers strictly use Linux tmpfs (<code>/dev/shm</code> in RAM).<br/>"
        "<b>3. 1 GB Physical RAM Budget:</b> Both AMD micro VMs are capped at 1 GB RAM each. Single-worker Uvicorn (<code>--workers 1</code>), explicit cgroup limits (<code>MemoryMax</code>), and zero memory bloat.<br/>"
        "<b>4. Systemd Specifier Escaping:</b> Database passwords with <code>%21%23</code> must be stored in <code>/etc/default/friday_universe.env</code>. Never place them inline in <code>.service</code> files.<br/>"
        "<b>5. Fail-Closed Security & Immutability:</b> Forge code modifications require Sentinel verification before merge. Return new objects rather than mutating state.",
        bg_hex="#FEF2F2", border_hex="#EF4444"
    ))
    story.append(Spacer(1, 6))

    # =========================================================================
    # SECTION 2: DUAL-SERVER INFRASTRUCTURE TOPOGRAPHY
    # =========================================================================
    story.append(Paragraph("2. Dual-Server Infrastructure Topography", h1_style))
    story.append(Paragraph(
        "The 10 autonomous agents are physically distributed across two Oracle Cloud Always Free AMD Micro VMs (<code>VM.Standard.E2.1.Micro</code>, 1 OCPU, 1 GB RAM, 8 GB swapfile) in the AP-Hyderabad-1 region:",
        body_style
    ))

    srv_headers = ["Fleet Tier", "Public IP / Hostname", "Private IP", "Hosted Agents & Mesh Ports", "Memory Allocation & Cgroup Caps"]
    srv_rows = [
        [
            "<b>Server 1<br/>Core Fleet</b><br/>(The Brain)",
            "<code>140.245.208.100</code><br/><code>friday-amd-vnic</code>",
            "<code>10.0.0.121</code>",
            "• <b>FRIDAY</b> (:10000) — Core Gateway<br/>"
            "• <b>Inference</b> (:8001) — Model Router<br/>"
            "• <b>Memora</b> (:8002) — Vector Memory<br/>"
            "• <b>Stratex</b> (:8003) — Trading Desk<br/>"
            "• <b>Futuris</b> (:8004) — Forecasting<br/>"
            "• <b>IntelX</b> (:8005) — Deep Research<br/>"
            "• <b>Forge</b> (:8006) — Code Synthesizer",
            "<b>Physical RAM:</b> 956 MB (1 GB)<br/>"
            "<b>Swapfile:</b> 8,191 MB (8 GB)<br/>"
            "<b>FRIDAY:</b> MemoryMax=200M<br/>"
            "<b>Memora:</b> MemoryMax=200M<br/>"
            "<b>Others:</b> MemoryMax=180M each<br/>"
            "<b>Target DB:</b> <code>friday_universe_db</code>"
        ],
        [
            "<b>Server 2<br/>Specialist Fleet</b><br/>(Studio & Ops)",
            "<code>140.245.243.168</code><br/><code>friday-amd-2-vnic</code>",
            "<code>10.0.0.120</code>",
            "• <b>VyralX</b> (:8010) — Video Production<br/>"
            "• <b>Sentinel</b> (:8008) — Security Shield<br/>"
            "• <b>Cortex</b> (:8009) — CRM & Web Engine",
            "<b>Physical RAM:</b> 956 MB (1 GB)<br/>"
            "<b>Swapfile:</b> 8,191 MB (8 GB)<br/>"
            "<b>VyralX:</b> MemoryMax=250M<br/>"
            "<b>Sentinel:</b> MemoryMax=200M<br/>"
            "<b>Cortex:</b> MemoryMax=200M<br/>"
            "<b>Target DB:</b> <code>vyralx_db</code> (VyralX) / Core (Others)"
        ]
    ]
    story.append(make_table(srv_headers, srv_rows, [80, 105, 65, 150, 140]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Systemd Service Execution Table", h2_style))
    svc_headers = ["Agent", "Server", "Port", "Systemd Service", "Working Directory & Execution Command", "Memory Limit"]
    svc_rows = [
        ["<b>FRIDAY</b>", "Server 1", "<code>10000</code>", "<code>FRIDAY.service</code>", "<code>/opt/friday_universe/FRIDAY</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1</code>", "200M"],
        ["<b>Inference</b>", "Server 1", "<code>8001</code>", "<code>Inference.service</code>", "<code>/opt/friday_universe/Inference</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --workers 1</code>", "180M"],
        ["<b>Memora</b>", "Server 1", "<code>8002</code>", "<code>Memora.service</code>", "<code>/opt/friday_universe/Memora</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1</code>", "200M"],
        ["<b>Stratex</b>", "Server 1", "<code>8003</code>", "<code>Stratex.service</code>", "<code>/opt/friday_universe/Stratex</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8003 --workers 1</code>", "180M"],
        ["<b>Futuris</b>", "Server 1", "<code>8004</code>", "<code>Futuris.service</code>", "<code>/opt/friday_universe/Futuris</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn futuris.api.app:app --host 0.0.0.0 --port 8004 --workers 1</code>", "180M"],
        ["<b>IntelX</b>", "Server 1", "<code>8005</code>", "<code>IntelX.service</code>", "<code>/opt/friday_universe/IntelX</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn intelx.app.main:app --host 0.0.0.0 --port 8005 --workers 1</code>", "180M"],
        ["<b>Forge</b>", "Server 1", "<code>8006</code>", "<code>Forge.service</code>", "<code>/opt/friday_universe/Forge</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1</code>", "180M"],
        ["<b>VyralX</b>", "Server 2", "<code>8010</code>", "<code>VyralX.service</code>", "<code>/opt/friday_universe/VyralX</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1</code>", "250M"],
        ["<b>Sentinel</b>", "Server 2", "<code>8008</code>", "<code>Sentinel.service</code>", "<code>/opt/friday_universe/Sentinel</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn sentinel.apps.api.main:app --host 0.0.0.0 --port 8008 --workers 1</code>", "200M"],
        ["<b>Cortex</b>", "Server 2", "<code>8009</code>", "<code>Cortex.service</code>", "<code>/opt/friday_universe/Cortex</code><br/><code>/opt/friday_universe/venv/bin/python -m uvicorn apps.api.src.cortex_api.main:app --host 0.0.0.0 --port 8009 --workers 1</code>", "200M"]
    ]
    story.append(make_table(svc_headers, svc_rows, [55, 45, 35, 75, 275, 55]))

    # =========================================================================
    # SECTION 3: ORACLE AUTONOMOUS 23ai CLOUD DATABASES
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("3. Dual Oracle Autonomous 23ai Database Architecture", h1_style))
    story.append(Paragraph(
        "All persistent state across all agents lives in two Always Free Oracle Autonomous Transaction Processing (ATP) 23ai instances in <code>ap-hyderabad-1</code> "
        "connecting over TLS Port <code>1521</code> (one-way TLS; no client wallet required). Zero local database files are written to VM disk.",
        body_style
    ))

    db_headers = ["Database Identifier", "Service Name & DSN Details", "Primary Owner", "Dedicated Tenancy", "Core Schema Tables"]
    db_rows = [
        [
            "<b>friday_universe_db</b><br/>(Core Fleet DB)",
            "<code>g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com</code><br/>"
            "Host: <code>adb.ap-hyderabad-1.oraclecloud.com</code><br/>"
            "Port: <code>1521</code> (Protocol: TCPS, SSL match: yes)",
            "<code>ADMIN</code><br/><code>FridayUniverse2026!#Core</code>",
            "FRIDAY, Inference, Memora, Stratex, Futuris, IntelX, Forge, Sentinel, Cortex",
            "• <code>MEMORA_MEMORIES</code> (23ai HNSW native vector)<br/>"
            "• <code>FUTURIS_FORECASTS</code> & 12 schema tables<br/>"
            "• <code>API_KEYS</code> (unified IntelX/Cortex auth)<br/>"
            "• <code>RESEARCH_RUNS</code>, <code>CLAIMS</code>, <code>EVIDENCE</code><br/>"
            "• <code>FORGE_BUILDS</code>, <code>STRATEX_TRADES</code><br/>"
            "• <code>SENTINEL_SCANS</code>, <code>AUDIT_EVENTS</code>"
        ],
        [
            "<b>vyralx_db</b><br/>(Specialist Media DB)",
            "<code>g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com</code><br/>"
            "Host: <code>adb.ap-hyderabad-1.oraclecloud.com</code><br/>"
            "Port: <code>1521</code> (Protocol: TCPS, SSL match: yes)",
            "<code>ADMIN</code><br/><code>FridayUniverse2026!#Vyral</code>",
            "Exclusively dedicated to <b>VyralX</b>",
            "• <code>VYRALX_PROJECTS</code>, <code>VYRALX_SCRIPTS</code><br/>"
            "• <code>VYRALX_STORYBOARDS</code>, <code>RENDER_JOBS</code><br/>"
            "• <code>VYRALX_MEDIA_ASSETS</code>, <code>PUBLISH_QUEUE</code><br/>"
            "• <code>VIDEO_METRICS</code>, <code>AGENT_TASKS</code>"
        ]
    ]
    story.append(make_table(db_headers, db_rows, [95, 130, 85, 95, 135]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Key Oracle 23ai Architectural Invariants", h2_style))
    story.append(Paragraph(
        "• <b>Native 23ai Vector Columns:</b> Memora utilizes Oracle 23ai native <code>VECTOR</code> data types with HNSW (Hierarchical Navigable Small World) index structures, executing sub-second semantic cosine similarity queries directly inside the database engine.<br/>"
        "• <b>Unified API_KEYS Schema:</b> IntelX and Cortex share a single consolidated <code>API_KEYS</code> table in <code>friday_universe_db</code> with nullable columns and sensible defaults (<code>tenant_id</code>, <code>site_id</code>, <code>key_prefix</code>, <code>role</code>, <code>is_active</code>, <code>revoked</code>), preventing DDL conflicts.<br/>"
        "• <b>Zero-Disk Linux tmpfs Caching:</b> Any local SQLite caches (e.g., Inference rate limits, Forge Memora fallback) are stored in <code>/dev/shm</code> (pure RAM tmpfs). No SQLite files touch persistent storage.",
        body_style
    ))

    # =========================================================================
    # SECTION 4: DEEP SUBSYSTEM SPECIFICATIONS
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("4. Deep Technical Subsystem Specifications", h1_style))
    story.append(Paragraph(
        "Detailed functional roles, technology stacks, internal endpoints, and safety gates for each of the 10 sovereign agents:",
        body_style
    ))

    agent_specs = [
        ("FRIDAY", "Cognitive Orchestrator & Action Gateway", "10000", "Server 1", "FRIDAY.service",
         "FastAPI, Uvicorn, WebSockets, Asyncio, Pydantic V2",
         "Central human-in-the-loop orchestrator, task planner, voice/chat companion, and mesh dispatcher.",
         "POST /api/v1/tasks (task envelope), GET /api/v1/tasks/{id} (status), POST /api/v1/actions/approve (human gate), GET /health"),
        ("Inference", "Sovereign Multi-Model Routing Gateway", "8001", "Server 1", "Inference.service",
         "FastAPI, HTTPX Pool, Groq SDK, Cerebras, OpenRouter, Google GenAI",
         "High-throughput multi-model inference router with automated fallback across Groq, Cerebras, OpenRouter, and Gemini.",
         "POST /v1/chat/completions (OpenAI compatible), POST /v1/task/execute (structured reasoning), GET /health"),
        ("Memora", "Cognitive Memory Fabric & Vector Database", "8002", "Server 1", "Memora.service",
         "FastAPI, Oracle Database 23ai Native VECTOR, HNSW Indexing",
         "Sole sovereign long-term memory authority enforcing cryptographic provenance, multi-tier scoping (Private, Shared, Universal), and prompt injection isolation.",
         "POST /v1/memories (ingest), POST /v1/memories/search (semantic vector search), GET /health"),
        ("Stratex", "Quantitative Trading Desk & Risk Ledger", "8003", "Server 1", "Stratex.service",
         "FastAPI, NumPy, Pandas, CCXT, Binance Futures Testnet SDK",
         "Algorithmic execution desk, continuous market surveillance, risk governance, and quantitative backtesting. Zero real-money risk.",
         "POST /api/v1/orders (pre-trade risk validate), POST /api/v1/emergency-halt (atomic kill-switch), GET /health"),
        ("Futuris", "Predictive Forecasting & Calibration Engine", "8004", "Server 1", "Futuris.service",
         "FastAPI, APScheduler, SciPy, Statsmodels, SQLAlchemy 2.0 Async",
         "Scenario forecasting, probabilistic modeling, uncertainty estimation, and historical Brier score calibration.",
         "POST /v1/forecast/scenario (multi-branch forecast), GET /v1/forecast/regime (regime distributions), GET /health (12 tables verified)"),
        ("IntelX", "Deep Evidence Research & Fact Verification", "8005", "Server 1", "IntelX.service",
         "FastAPI, BeautifulSoup4, Trafilatura, DuckDuckGo / SearXNG Connectors",
         "Deep web research, fact-checking, citation extraction, news ingestion, and claim corroboration against primary sources.",
         "POST /v1/research/query (deep gather), POST /v1/verify/claim (corroborate assertion), GET /health"),
        ("Forge", "Autonomous Software Synthesizer & Build Engine", "8006", "Server 1", "Forge.service",
         "FastAPI, Rope, Pytest, AST, Tree-Sitter, SQLAlchemy 2.0 Async",
         "Full-stack autonomous software engineer: specification parsing, multi-file code synthesis, automated test generation, and verification.",
         "POST /api/v1/synthesize (DAG build), GET /api/v1/tasks/{id}/verify (10-point test battery), GET /health"),
        ("VyralX", "Autonomous Video Production & Multi-Channel Studio", "8010", "Server 2", "VyralX.service",
         "FastAPI, MoviePy, FFmpeg, FFprobe, eSpeak NG, YouTube Data API v3",
         "End-to-end video production, AI scriptwriting, audio synthesis, visual assembly, automated captioning, rendering, and YouTube publication.",
         "POST /api/v1/projects (scene plan), POST /api/v1/render (FFmpeg compose), POST /api/v1/publish/youtube (chunked upload), GET /health"),
        ("Sentinel", "Zero-Trust Cybersecurity Gatekeeper & Audit Shield", "8008", "Server 2", "Sentinel.service",
         "FastAPI, Cryptography, Jose JWT, SSL/TLS Audit Daemons",
         "Ecosystem security officer: cryptographic HMAC audit ledger, continuous TLS/DNS monitoring, static code vulnerability analysis, and zero-trust perimeter defense.",
         "POST /v1/security/audit (fail-closed code review gate), POST /v1/audit/record (signed audit ledger), GET /health"),
        ("Cortex", "Autonomous Operations Engine & Governed CRM", "8009", "Server 2", "Cortex.service",
         "FastAPI, Next.js (Exported SPA in apps/dashboard/out), SQLAlchemy Async",
         "Powers ecosystem web presence, landing pages, operator dashboard API, CRM telemetry, and event-driven self-healing.",
         "GET / (landing page & status), POST /v1/events (telemetry ingest), GET /health (tenant isolation verify)")
    ]

    for name, title, port, srv, unit, stack, mission, routes in agent_specs:
        story.append(Paragraph(f"<b>{name}</b> — {title} (Port {port} | {srv})", h2_style))
        story.append(Paragraph(
            f"<b>Framework Stack:</b> {stack}<br/>"
            f"<b>Service Unit:</b> <code>{unit}</code><br/>"
            f"<b>Primary Mission:</b> {mission}<br/>"
            f"<b>Key API Routes:</b> <code>{routes}</code>",
            body_style
        ))
        story.append(Spacer(1, 3))

    # =========================================================================
    # SECTION 5: MONOREPO & CI/CD PIPELINE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("5. Unified GitHub Monorepo & Granular CI/CD Deployment", h1_style))
    story.append(Paragraph(
        "Development is centralized in a unified monorepo while deployment and standalone repository distribution are handled through automated GitHub Actions workflows.",
        body_style
    ))

    story.append(Paragraph(
        "• <b>Monorepo Remote:</b> <code>https://github.com/surendra2304/FRIDAY-Universe.git</code> (Branch: <code>main</code>)<br/>"
        "• <b>Local Workspace Path:</b> <code>D:\\FRIDAY Universe</code><br/>"
        "• <b>Remote Target Path:</b> <code>/opt/friday_universe</code> on both Server 1 and Server 2.",
        body_style
    ))

    cicd_headers = ["Workflow File", "Trigger Condition", "Primary Mechanism", "Deployment Target & Action"]
    cicd_rows = [
        [
            "<b>deploy-monorepo.yml</b><br/>"
            "(Selective Fleet Deploy)",
            "Push to <code>main</code><br/>(Path-filtered)",
            "<code>dorny/paths-filter@v3</code> detects modified agent subdirectories (e.g. <code>FRIDAY/**</code>, <code>VyralX/**</code>). "
            "Executes parallel SSH tasks via <code>appleboy/ssh-action</code>.",
            "Connects to Server 1 or Server 2 based on agent location. Pulls updated code into <code>/opt/friday_universe/<Agent></code> "
            "and triggers <code>sudo systemctl restart <Agent>.service</code>. Unchanged agents remain running without restart."
        ],
        [
            "<b>mirror-subrepos.yml</b><br/>"
            "(Subtree Synchronization)",
            "Push to <code>main</code><br/>(All commits)",
            "Executes <code>git subtree split</code> across all 10 agent folders and force-pushes the clean commit history directly to each standalone repository.",
            "Syncs to 10 distinct GitHub repositories under <code>surendra2304/<AgentName>.git</code>, maintaining isolated histories for independent packaging."
        ]
    ]
    story.append(make_table(cicd_headers, cicd_rows, [110, 85, 165, 180]))
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 6: PROVEN GOTCHAS & PRODUCTION RUNBOOK
    # =========================================================================
    story.append(Paragraph("6. Proven Production Coding Gotchas & Self-Healing Runbook", h1_style))
    story.append(Paragraph(
        "All engineers and AI agents modifying FRIDAY Universe code must adhere to these battle-tested resolutions to avoid production crashes:",
        body_style
    ))

    gotcha_headers = ["Issue / Error Signature", "Root Technical Cause", "Enforced Architecture Resolution"]
    gotcha_rows = [
        [
            "<b>SQLAlchemy Oracle JSON Compile Error</b><br/>"
            "<code>Compiler can't render element of type JSON</code>",
            "SQLAlchemy 2.0 <code>OracleTypeCompiler</code> lacks a native handler for generic <code>JSON</code> / <code>JSONB</code> types.",
            "Register the native Oracle 23ai compiler hook in model definitions:<br/>"
            "<code>@compiles(JSON, 'oracle')<br/>def _compile(t, c, **kw): return 'JSON'</code>"
        ],
        [
            "<b>Oracle JSON Path Parameter Error</b><br/>"
            "<code>ORA-40454: path expression not a literal</code>",
            "SQLAlchemy binds JSON dictionary indexing (<code>json_getitem_op</code>) as a bind variable, which Oracle SQL rejects in <code>JSON_VALUE</code>.",
            "Wrap path expressions in <code>literal_column</code> when querying Oracle:<br/>"
            "<code>func.json_value(col, literal_column(\"'$.priority'\"))</code>"
        ],
        [
            "<b>Systemd Credential Specifier Bug</b><br/>"
            "<code>Failed to resolve specifiers ... invalid slot</code>",
            "Systemd interprets <code>%</code> in passwords (e.g. <code>%21%23</code>) as format specifiers and discards the line.",
            "Store credentials in <code>/etc/default/friday_universe.env</code> and reference them via <code>EnvironmentFile=/etc/default/...</code>. Never inline."
        ],
        [
            "<b>Async Dialect Rejection</b><br/>"
            "<code>create_async_engine requires async driver</code>",
            "Passing <code>oracle+oracledb://</code> to <code>create_async_engine()</code> fails because async execution requires the async dialect.",
            "Dynamically convert connection strings:<br/>"
            "<code>if url.startswith('oracle+oracledb://'): url = 'oracle+oracledb_async://' + url[len('oracle+oracledb://'):]</code>"
        ],
        [
            "<b>Shared API_KEYS Conflict</b><br/>"
            "<code>ORA-00904: API_KEYS.REVOKED invalid identifier</code>",
            "IntelX and Cortex both declare an <code>api_keys</code> table with different column definitions in <code>friday_universe_db</code>.",
            "The table in <code>friday_universe_db</code> is unified with a superset schema. Non-shared columns are nullable and carry sensible defaults."
        ]
    ]
    story.append(make_table(gotcha_headers, gotcha_rows, [110, 155, 275]))
    story.append(Spacer(1, 8))

    # =========================================================================
    # SECTION 7: INTER-AGENT RPC MATRIX & ENVIRONMENT CATALOG
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("7. Inter-Agent RPC Contracts & Environment Catalog", h1_style))
    story.append(Paragraph(
        "Inter-agent communication flows over internal private IP REST endpoints with required mutual authentication headers:",
        body_style
    ))

    mesh_headers = ["Caller Agent", "Target Agent", "Target Private URL & Port", "Action & Protocol", "Security Policy"]
    mesh_rows = [
        ["<b>FRIDAY</b>", "Inference", "<code>http://10.0.0.121:8001/ask</code>", "Task reasoning & prompt decomposition", "Bearer token authentication"],
        ["<b>FRIDAY</b>", "Memora", "<code>http://10.0.0.121:8002/api/v1/memories/search</code>", "Vector semantic similarity search", "Bearer token + Scoped ACL"],
        ["<b>Stratex</b>", "Futuris", "<code>http://10.0.0.121:8004/v1/forecast/regime</code>", "Query market regime probability", "Advisory insight only"],
        ["<b>Stratex</b>", "Sentinel", "<code>http://10.0.0.120:8008/v1/audit/record</code>", "Submit trade audit record for HMAC signing", "Tamper-evident cryptographic ledger"],
        ["<b>Forge</b>", "Sentinel", "<code>http://10.0.0.120:8008/v1/security/audit</code>", "Pre-delivery code vulnerability audit", "Strict fail-closed veto power"],
        ["<b>Cortex</b>", "IntelX", "<code>http://10.0.0.121:8005/v1/research/query</code>", "Competitor & factual web research", "Asynchronous poll; cited confidence"],
        ["<b>VyralX</b>", "Inference", "<code>http://10.0.0.121:8001/v1/task/execute</code>", "Original video script & scene generation", "Graceful cached draft fallback"]
    ]
    story.append(make_table(mesh_headers, mesh_rows, [60, 60, 155, 145, 120]))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Master Environment Variable Catalog (/etc/default/friday_universe.env)", h2_style))
    env_lines = [
        "# Database Credentials (Loaded via EnvironmentFile in systemd units)",
        "DATABASE_URL=oracle+oracledb://ADMIN:FridayUniverse2026%21%23Core@(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))",
        "ORACLE_CORE_URL=oracle+oracledb://ADMIN:FridayUniverse2026%21%23Core@(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))",
        "ORACLE_CORE_ASYNC_URL=oracle+oracledb_async://ADMIN:FridayUniverse2026%21%23Core@(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridaycore_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))",
        "ORACLE_VYRAL_URL=oracle+oracledb://ADMIN:FridayUniverse2026%21%23Vyral@(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))",
        "ORACLE_VYRAL_ASYNC_URL=oracle+oracledb_async://ADMIN:FridayUniverse2026%21%23Vyral@(description=(retry_count=20)(retry_delay=3)(address=(protocol=tcps)(port=1521)(host=adb.ap-hyderabad-1.oraclecloud.com))(connect_data=(service_name=g7e6177242670c3_fridayvyralx_medium.adb.oraclecloud.com))(security=(ssl_server_dn_match=yes)))",
        "",
        "# Cryptographic Security Keys",
        "SENTINEL_AUDIT_HMAC_KEY=c36209e9fbe54d008d51a660d2ecb0b023f9906649f8269e8bb95b217dc3ad3e",
        "SENTINEL_AUDIT_SIGNING_KEY=c36209e9fbe54d008d51a660d2ecb0b023f9906649f8269e8bb95b217dc3ad3e",
        "SENTINEL_API_KEY=sentinel_jF-bgAo6XWDQqV-TaRW1MiG36QbC3YUY6c",
        "",
        "# Private Mesh Network URLs (Internal IP Interconnect)",
        "FRIDAY_URL=http://10.0.0.121:10000",
        "INFERENCE_URL=http://10.0.0.121:8001",
        "MEMORA_URL=http://10.0.0.121:8002",
        "STRATEX_URL=http://10.0.0.121:8003",
        "FUTURIS_URL=http://10.0.0.121:8004",
        "INTELX_URL=http://10.0.0.121:8005",
        "FORGE_URL=http://10.0.0.121:8006",
        "VYRALX_URL=http://10.0.0.120:8010",
        "SENTINEL_URL=http://10.0.0.120:8008",
        "CORTEX_URL=http://10.0.0.120:8009"
    ]
    story.append(make_code_box(env_lines))
    story.append(Spacer(1, 10))

    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=6))
    story.append(Paragraph(
        "<i>Document certified and compiled by Antigravity AI Project Coordinator for the FRIDAY Universe. "
        "All specifications, schemas, endpoints, and architectural invariants documented herein represent the authoritative ground truth for sovereign ecosystem continuity.</i>",
        desc_style
    ))

    # Build the document
    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"Successfully generated Master Architecture PDF: {pdf_path}")

if __name__ == "__main__":
    out_pdf = r"D:\FRIDAY Universe\FRIDAY_UNIVERSE_MASTER_ARCHITECTURE.pdf"
    readme_pdf = r"D:\FRIDAY Universe\README.pdf"
    artifact_dir = Path(r"C:\Users\Surendra\.gemini\antigravity\brain\5178919f-c72f-409f-90f8-4c6c5b761afb")

    # 1. Generate PDF
    build_pdf(out_pdf)

    # 2. Copy to README.pdf
    shutil.copy2(out_pdf, readme_pdf)
    print(f"Successfully updated README.pdf: {readme_pdf}")

    # 3. Copy to Artifact Directory
    if artifact_dir.exists():
        art_pdf = artifact_dir / "FRIDAY_UNIVERSE_MASTER_ARCHITECTURE.pdf"
        shutil.copy2(out_pdf, art_pdf)
        print(f"Successfully copied to Artifacts: {art_pdf}")
