"""
tools/universe_dashboard.py — FRIDAY Universe Web Dashboard.

A self-contained FastAPI app that serves a web UI showing:
- All 10 agents' health status
- Dispatch bus routing
- Metrics and alerts
- Audit trail
- Event bus activity

Priority 3: Make It Visible (Dashboard)
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Add all paths
for p in [
    ROOT / "FRIDAY/apps/core/src",
    ROOT / "Cortex/apps/api/src",
    ROOT / "Inference",
    ROOT / "Memora/apps/api",
    ROOT / "Forge",
    ROOT / "VyralX",
    ROOT / "IntelX",
    ROOT / "Sentinel/sentinel/apps/api/src",
    ROOT / "Stratex",
    ROOT / "Futuris",
]:
    p = str(p)
    if p not in sys.path:
        sys.path.insert(0, p)

sys.path.insert(0, str(ROOT / "tools"))

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="FRIDAY Universe Dashboard", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Load workflow engine
try:
    import universe_workflow_engine
    _workflow_engine = universe_workflow_engine.UniverseWorkflowEngine()
except Exception:
    _workflow_engine = None

# Load self-improvement engine
try:
    import universe_self_improvement
    _self_improvement = universe_self_improvement.AgentSelfImprovement()
    _knowledge_sharing = universe_self_improvement.KnowledgeSharingEngine()
    _decision_propagation = universe_self_improvement.DecisionPropagationEngine()
except Exception:
    _self_improvement = None
    _knowledge_sharing = None
    _decision_propagation = None


def _load_engine(name, relpath):
    """Load a module engine via importlib."""
    path = str(ROOT / relpath)
    full_name = f"_dash_{name}"
    spec = importlib.util.spec_from_file_location(full_name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = mod
    spec.loader.exec_module(mod)
    return mod.engine


# ── Load all engines at startup ────────────────────────────────────────────

engines = {}


def _init_engines():
    """Initialize all engines."""
    engine_paths = {
        "dispatch_bus": "FRIDAY/apps/core/src/friday_core/universe_dispatch_bus.py",
        "auth": "FRIDAY/apps/core/src/friday_core/universe_auth.py",
        "gateway": "FRIDAY/apps/core/src/friday_core/universe_gateway.py",
        "config": "FRIDAY/apps/core/src/friday_core/universe_config.py",
        "metrics": "FRIDAY/apps/core/src/friday_core/universe_metrics.py",
        "health": "FRIDAY/apps/core/src/friday_core/universe_health_monitor.py",
        "mesh": "FRIDAY/apps/core/src/friday_core/agent_mesh_router.py",
        "events": "FRIDAY/apps/core/src/friday_core/universe_event_bus.py",
        "state": "FRIDAY/apps/core/src/friday_core/universe_state_manager.py",
        "audit": "FRIDAY/apps/core/src/friday_core/universe_audit_trail.py",
        "router": "FRIDAY/apps/core/src/friday_core/universe_task_router.py",
        "kg": "FRIDAY/apps/core/src/friday_core/universe_knowledge_graph.py",
    }
    for name, path in engine_paths.items():
        try:
            engines[name] = _load_engine(name, path)
        except Exception as e:
            print(f"Warning: Failed to load {name}: {e}")


_init_engines()


# ── API Endpoints ───────────────────────────────────────────────────────────

@app.get("/api/health")
async def api_health():
    """Get health status of all engines."""
    health = {"engines": {}, "timestamp": time.time()}
    for name, eng in engines.items():
        try:
            if name == "health":
                snap = eng.get_universe_health()
                health["engines"][name] = {
                    "total_agents": snap.total_agents,
                    "healthy_agents": snap.healthy_agents,
                }
            elif name == "gateway":
                agents = eng.get_all_agents_health()
                health["engines"][name] = {"agents": len(agents)}
            elif name == "config":
                health["engines"][name] = {"agents": len(eng.get_all_agents())}
            elif name == "metrics":
                report = eng.calculate_metrics()
                health["engines"][name] = {
                    "total_requests": report.total_requests,
                    "total_errors": report.total_errors,
                    "avg_latency_ms": report.avg_latency_ms,
                }
            else:
                health["engines"][name] = {"status": "loaded"}
        except Exception as e:
            health["engines"][name] = {"status": "error", "error": str(e)}
    return health


@app.get("/api/agents")
async def api_agents():
    """Get all registered agents."""
    if "config" not in engines:
        return {"error": "Config engine not loaded"}
    agents = engines["config"].get_all_agents()
    return {"agents": [a.model_dump() if hasattr(a, "model_dump") else str(a) for a in agents], "count": len(agents)}


@app.get("/api/dispatch")
async def api_dispatch():
    """Dispatch a test task to an agent."""
    if "dispatch_bus" not in engines:
        return {"error": "Dispatch bus not loaded"}
    receipt = engines["dispatch_bus"].dispatch("Inference", "health_check", {"test": True})
    return {
        "task_id": receipt.task_id,
        "agent": receipt.agent,
        "status": receipt.status,
        "result": receipt.result,
        "latency_ms": receipt.latency_ms,
    }


@app.get("/api/dispatch/batch")
async def api_dispatch_batch():
    """Dispatch test tasks to all 9 agents."""
    if "dispatch_bus" not in engines:
        return {"error": "Dispatch bus not loaded"}
    batch = engines["dispatch_bus"].dispatch_batch([
        {"agent": "Inference", "action": "reason", "payload": {}},
        {"agent": "Memora", "action": "recall", "payload": {}},
        {"agent": "Cortex", "action": "decide", "payload": {}},
        {"agent": "Stratex", "action": "trade", "payload": {}},
        {"agent": "Forge", "action": "build", "payload": {}},
        {"agent": "Sentinel", "action": "scan", "payload": {}},
        {"agent": "IntelX", "action": "analyze", "payload": {}},
        {"agent": "Futuris", "action": "forecast", "payload": {}},
        {"agent": "VyralX", "action": "create", "payload": {}},
    ])
    return {"count": len(batch), "receipts": [
        {"task_id": r.task_id, "agent": r.agent, "status": r.status, "latency_ms": r.latency_ms}
        for r in batch
    ]}


@app.get("/api/metrics")
async def api_metrics():
    """Get metrics report."""
    if "metrics" not in engines:
        return {"error": "Metrics engine not loaded"}
    report = engines["metrics"].calculate_metrics()
    return {
        "total_requests": report.total_requests,
        "total_errors": report.total_errors,
        "avg_latency_ms": report.avg_latency_ms,
        "p50_latency_ms": report.p50_latency_ms,
        "p95_latency_ms": report.p95_latency_ms,
        "p99_latency_ms": report.p99_latency_ms,
        "overall_health_score": report.overall_health_score,
        "alert_count": report.alert_count,
    }


@app.get("/api/audit")
async def api_audit(limit: int = 20):
    """Get recent audit entries."""
    if "audit" not in engines:
        return {"error": "Audit engine not loaded"}
    results = engines["audit"].search(limit=limit)
    return results


@app.get("/api/events")
async def api_events(limit: int = 20):
    """Get recent events."""
    if "events" not in engines:
        return {"error": "Events engine not loaded"}
    # Publish a test event
    event = engines["events"].publish_event("dashboard_view", {"viewer": "web"}, "FRIDAY")
    return {"event_id": event.event_id, "event_type": "dashboard_view", "source": "FRIDAY"}


@app.get("/api/mesh/route")
async def api_mesh_route(task: str, domain: str = "trading"):
    """Route a task through the mesh router."""
    if "mesh" not in engines:
        return {"error": "Mesh engine not loaded"}
    decision = engines["mesh"].route_task(task, domain)
    return {
        "routed_to": decision.routed_to,
        "confidence": decision.confidence,
        "reason": decision.reason,
    }


@app.get("/api/state")
async def api_state():
    """Get all state."""
    if "state" not in engines:
        return {"error": "State engine not loaded"}
    # Set a test state
    engines["state"].set_state("dashboard_visit", {"timestamp": time.time()}, "FRIDAY")
    all_state = engines["state"].get_all_state()
    return {"states": all_state, "count": len(all_state)}


# ── Workflow API Endpoints ───────────────────────────────────────────────────

@app.get("/api/workflow/capabilities")
async def api_workflow_capabilities():
    """Get all agent capabilities."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    return _workflow_engine.discover_all()

@app.get("/api/workflow/agents")
async def api_workflow_agents():
    """Get all registered agents with capabilities."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    agents = _workflow_engine._capabilities.all_agents()
    return {"agents": [
        {"name": a.agent_name, "capabilities": a.capabilities,
         "base_url": a.base_url, "status": a.status}
        for a in agents
    ]}

@app.get("/api/workflow/run/trading")
async def api_workflow_trading():
    """Run the trading analysis workflow."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    wf = _workflow_engine.run_trading_analysis()
    return {"workflow_id": wf.workflow_id, "status": wf.status,
            "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
            "total_steps": len(wf.steps)}

@app.get("/api/workflow/run/security")
async def api_workflow_security():
    """Run the security scan workflow."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    wf = _workflow_engine.run_security_scan()
    return {"workflow_id": wf.workflow_id, "status": wf.status,
            "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
            "total_steps": len(wf.steps)}

@app.get("/api/workflow/run/content")
async def api_workflow_content():
    """Run the content creation workflow."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    wf = _workflow_engine.run_content_creation()
    return {"workflow_id": wf.workflow_id, "status": wf.status,
            "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
            "total_steps": len(wf.steps)}

@app.get("/api/workflow/run/code")
async def api_workflow_code():
    """Run the code development workflow."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    wf = _workflow_engine.run_code_development()
    return {"workflow_id": wf.workflow_id, "status": wf.status,
            "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
            "total_steps": len(wf.steps)}

@app.get("/api/workflow/run/forecast")
async def api_workflow_forecast():
    """Run the forecast pipeline workflow."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    wf = _workflow_engine.run_forecast_pipeline()
    return {"workflow_id": wf.workflow_id, "status": wf.status,
            "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
            "total_steps": len(wf.steps)}

@app.get("/api/workflow/all")
async def api_workflow_all():
    """Run all workflow templates."""
    if _workflow_engine is None:
        return {"error": "Workflow engine not loaded"}
    workflows = []
    for name, func in [("trading", _workflow_engine.run_trading_analysis),
                        ("security", _workflow_engine.run_security_scan),
                        ("content", _workflow_engine.run_content_creation),
                        ("code", _workflow_engine.run_code_development),
                        ("forecast", _workflow_engine.run_forecast_pipeline)]:
        wf = func()
        workflows.append({"name": name, "status": wf.status,
                          "steps_completed": sum(1 for s in wf.steps if s.status == "completed"),
                          "total_steps": len(wf.steps)})
    return {"workflows": workflows, "count": len(workflows)}


# ── Self-Improvement API Endpoints ──────────────────────────────────────────

@app.get("/api/self-improvement/report")
async def api_self_improvement_report():
    """Get self-improvement report."""
    if _self_improvement is None:
        return {"error": "Self-improvement engine not loaded"}
    return _self_improvement.get_improvement_report()

@app.get("/api/self-improvement/cycle/{agent}")
async def api_self_improvement_cycle(agent: str):
    """Run an improvement cycle for an agent."""
    if _self_improvement is None:
        return {"error": "Self-improvement engine not loaded"}
    return _self_improvement.run_improvement_cycle(agent)

@app.get("/api/knowledge/all")
async def api_knowledge_all():
    """Get all shared knowledge."""
    if _knowledge_sharing is None:
        return {"error": "Knowledge sharing engine not loaded"}
    items = _knowledge_sharing.get_knowledge_graph()
    return {"items": len(items), "knowledge": [
        {"source": k.source_agent, "target": k.target_agent,
         "type": k.knowledge_type, "content": k.content[:50]}
        for k in items
    ]}

@app.get("/api/knowledge/retrieve/{agent}")
async def api_knowledge_retrieve(agent: str):
    """Retrieve knowledge for an agent."""
    if _knowledge_sharing is None:
        return {"error": "Knowledge sharing engine not loaded"}
    items = _knowledge_sharing.retrieve_knowledge(agent)
    return {"items": len(items), "knowledge": [
        {"source": k.source_agent, "type": k.knowledge_type, "content": k.content[:50]}
        for k in items
    ]}

@app.get("/api/decisions/all")
async def api_decisions_all():
    """Get all decisions."""
    if _decision_propagation is None:
        return {"error": "Decision propagation engine not loaded"}
    decisions = _decision_propagation.get_all_decisions()
    return {"decisions": len(decisions), "items": [
        {"source": d.source_agent, "type": d.decision_type,
         "content": d.content[:50], "propagated_to": d.propagated_to}
        for d in decisions
    ]}

@app.get("/api/decisions/agent/{agent}")
async def api_decisions_agent(agent: str):
    """Get decisions for an agent."""
    if _decision_propagation is None:
        return {"error": "Decision propagation engine not loaded"}
    decisions = _decision_propagation.get_decisions_for_agent(agent)
    return {"decisions": len(decisions), "items": [
        {"source": d.source_agent, "type": d.decision_type, "content": d.content[:50]}
        for d in decisions
    ]}


# ── Dashboard HTML ─────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FRIDAY Universe Dashboard</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0a1a; color: #e0e0e0; min-height: 100vh; }
.header { background: linear-gradient(135deg, #1a1a3a, #2a1a4a); padding: 20px 30px; border-bottom: 2px solid #4a4a8a; }
.header h1 { color: #fff; font-size: 24px; }
.header p { color: #888; font-size: 14px; margin-top: 5px; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 20px; margin-bottom: 20px; }
.card { background: #151525; border: 1px solid #2a2a4a; border-radius: 12px; padding: 20px; }
.card h3 { color: #fff; font-size: 16px; margin-bottom: 15px; }
.stat { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #2a2a3a; }
.stat-label { color: #888; font-size: 13px; }
.stat-value { color: #4fc3f7; font-weight: bold; font-size: 14px; }
.stat-value.green { color: #4caf50; }
.stat-value.red { color: #f44336; }
.stat-value.yellow { color: #ff9800; }
.agent-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; }
.agent { background: #1a1a2a; border: 1px solid #2a2a4a; border-radius: 8px; padding: 12px; }
.agent-name { font-weight: bold; color: #fff; }
.agent-status { font-size: 12px; margin-top: 4px; }
.agent-status.online { color: #4caf50; }
.agent-status.offline { color: #f44336; }
.agent-status.unknown { color: #ff9800; }
button { background: #4a4a8a; color: white; border: none; padding: 10px 20px; border-radius: 8px; cursor: pointer; font-size: 14px; margin: 5px; transition: background 0.2s; }
button:hover { background: #6a6aaa; }
.results { background: #0d0d1a; border: 1px solid #2a2a4a; border-radius: 8px; padding: 15px; margin-top: 15px; font-family: monospace; font-size: 13px; white-space: pre-wrap; word-break: break-all; max-height: 300px; overflow-y: auto; }
.section-title { color: #fff; font-size: 18px; margin: 25px 0 15px; padding-bottom: 8px; border-bottom: 1px solid #2a2a4a; }
.footer { text-align: center; color: #666; font-size: 12px; padding: 20px; margin-top: 20px; }
</style>
</head>
<body>
<div class="header">
  <h1>🔷 FRIDAY Universe Dashboard</h1>
  <p>Monitoring 10 agents across the FRIDAY Universe</p>
</div>
<div class="container">
  <div class="section-title">Engine Status</div>
  <div class="grid" id="engines"></div>

  <div class="section-title">Agent Registry</div>
  <div class="grid" id="agents"></div>

  <div class="section-title">Quick Actions</div>
  <div class="card">
    <button onclick="dispatchTest()">Test Dispatch</button>
    <button onclick="dispatchBatch()">Batch Dispatch (All 9)</button>
    <button onclick="routeMesh()">Mesh Route</button>
    <button onclick="getMetrics()">Refresh Metrics</button>
    <button onclick="getAudit()">View Audit</button>
    <button onclick="getEvents()">View Events</button>
    <div class="results" id="output">Click a button to see results...</div>
  </div>
</div>
<div class="footer">FRIDAY Universe Dashboard v1.0 | Powered by FastAPI</div>

<script>
async function api(path) {
  try {
    const r = await fetch(path);
    return await r.json();
  } catch(e) { return {error: e.message}; }
}

async function loadEngines() {
  const data = await api('/api/health');
  const el = document.getElementById('engines');
  el.innerHTML = Object.entries(data.engines || {}).map(([name, info]) => {
    const status = info.status === 'loaded' ? 'green' : (info.status === 'error' ? 'red' : 'yellow');
    return `<div class="card"><h3>${name}</h3>
      <div class="stat"><span class="stat-label">Status</span><span class="stat-value ${status}">${info.status || 'ok'}</span></div>
      ${info.total_requests !== undefined ? `<div class="stat"><span class="stat-label">Requests</span><span class="stat-value">${info.total_requests}</span></div>` : ''}
      ${info.total_errors !== undefined ? `<div class="stat"><span class="stat-label">Errors</span><span class="stat-value ${info.total_errors > 0 ? 'red' : 'green'}">${info.total_errors}</span></div>` : ''}
      ${info.avg_latency_ms !== undefined ? `<div class="stat"><span class="stat-label">Avg Latency</span><span class="stat-value">${info.avg_latency_ms}ms</span></div>` : ''}
      ${info.agents !== undefined ? `<div class="stat"><span class="stat-label">Agents</span><span class="stat-value">${info.agents}</span></div>` : ''}
      ${info.total_agents !== undefined ? `<div class="stat"><span class="stat-label">Total Agents</span><span class="stat-value">${info.total_agents}</span></div>` : ''}
    </div>`;
  }).join('');
}

async function loadAgents() {
  const data = await api('/api/agents');
  const el = document.getElementById('agents');
  if (data.error) { el.innerHTML = `<div class="card"><p>${data.error}</p></div>`; return; }
  el.innerHTML = '<div class="agent-grid">' + (data.agents || []).map(a => {
    const name = a.agent_name || a.name || 'Unknown';
    return `<div class="agent"><div class="agent-name">${name}</div>
      <div class="agent-status unknown">port: ${a.port || a.base_url || 'N/A'}</div></div>`;
  }).join('') + '</div>';
}

function showOutput(data) {
  document.getElementById('output').textContent = JSON.stringify(data, null, 2);
}

async function dispatchTest() { showOutput(await api('/api/dispatch')); }
async function dispatchBatch() { showOutput(await api('/api/dispatch/batch')); }
async function routeMesh() { showOutput(await api('/api/mesh/route?task=analyze+trading&domain=trading')); }
async function getMetrics() { showOutput(await api('/api/metrics')); }
async function getAudit() { showOutput(await api('/api/audit?limit=10')); }
async function getEvents() { showOutput(await api('/api/events?limit=10')); }

loadEngines();
loadAgents();
setInterval(loadEngines, 10000);
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML."""
    return HTMLResponse(DASHBOARD_HTML)


if __name__ == "__main__":
    import uvicorn
    print("🔷 Starting FRIDAY Universe Dashboard on http://0.0.0.0:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
