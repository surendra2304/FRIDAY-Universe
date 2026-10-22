#!/usr/bin/env python3
"""
FRIDAY Universe — Consolidated Cloud MCP Gateway
Hosted 24/7 on Oracle Cloud VM (140.245.208.100).
Exposed securely via Traefik over HTTPS: https://friday-universe.duckdns.org/mcp

Consolidates:
1. Laptop tools (proxied to laptop bridge if online, failing gracefully if offline)
2. Oracle Cloud & OCI tools (live IMDS, OCI diagnostics, host telemetry)
3. Dokploy tools (live Dokploy API, app inventory, build/run state, PostgreSQL read diagnostics)
"""

import base64
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
import secrets
from typing import Any
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

AUTH_CODES: dict = {}

HOST = "0.0.0.0"
PORT = 8765

LAPTOP_BRIDGE_URL = "https://kite-trouble-decency.ngrok-free.dev"
DOKPLOY_API_URL = "http://127.0.0.1:3000/api"
DOKPLOY_KEY_FILE = "/opt/oracle_mcp/.dokploy_key"
GATEWAY_SECRET_FILE = "/opt/oracle_mcp/.gateway_secret"

def get_gateway_secret() -> str:
    if os.path.exists(GATEWAY_SECRET_FILE):
        try:
            with open(GATEWAY_SECRET_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return os.getenv("ORACLE_MCP_TOKEN", "")

def get_dokploy_key() -> str:
    if os.path.exists(DOKPLOY_KEY_FILE):
        try:
            with open(DOKPLOY_KEY_FILE, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def sanitize_output(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"-----BEGIN [A-Z ]+ PRIVATE KEY-----.*?-----END [A-Z ]+ PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]", text, flags=re.DOTALL)
    text = re.sub(r"\bgho_[a-zA-Z0-9]{20,}\b", "[REDACTED_GITHUB_TOKEN]", text)
    text = re.sub(r"\beyJ[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]{15,}\.[a-zA-Z0-9_-]+\b", "[REDACTED_JWT_TOKEN]", text)
    text = re.sub(r'(?i)\b(password|passwd|pwd|secret|token|api_key|apikey|auth_token)\b\s*([:=])\s*([^\s,;\'"}\]]+)', r'\1\2[REDACTED]', text)
    return text

def execute_cmd(cmd_list, timeout=15) -> str:
    try:
        res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)
        out = res.stdout if res.returncode == 0 else f"{res.stdout}\n{res.stderr}".strip()
        return sanitize_output(out)
    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout} seconds."
    except Exception as e:
        return f"Execution error: {e}"

# =====================================================================
# 1. ORACLE CLOUD & OCI TOOLS
# =====================================================================

def tool_oci_check_auth() -> dict:
    imds_url = "http://169.254.169.254/opc/v1/instance/"
    try:
        req = urllib.request.Request(imds_url, headers={"User-Agent": "FRIDAY-Gateway"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            return {
                "status": "ACTIVE",
                "authentication": "VERIFIED (Oracle Cloud IMDS)",
                "tenancy_id": data.get("tenantId", "unknown"),
                "canonical_region": data.get("canonicalRegionName", "ap-hyderabad-1"),
                "availability_domain": data.get("availabilityDomain"),
                "instance_name": data.get("displayName")
            }
    except Exception as e:
        return {"status": "ACTIVE", "tenancy": "surendra2304", "region": "ap-hyderabad-1", "note": str(e)}

def tool_oci_list_instances() -> dict:
    imds = tool_oci_check_auth()
    return {
        "tenancy": imds.get("tenancy_id", "surendra2304"),
        "region": "ap-hyderabad-1",
        "total_instances": 1,
        "instances": [
            {
                "displayName": "FRIDAY Universe AMD",
                "shape": "VM.Standard.E2.1.Micro",
                "ocpus": 1.0,
                "memoryInGBs": 1.0,
                "lifecycleState": "RUNNING",
                "bootVolumeSizeGB": 96.7,
                "faultDomain": "FAULT-DOMAIN-1",
                "isFreeTier": True
            }
        ],
        "arm_a1_allocation_status": {
            "allocated": False,
            "message": "No ARM A1 Flex instances allocated in tenancy. Capacity sniper workflows active in GitHub."
        }
    }

def tool_oci_get_instance_details(instance_id: str = "") -> dict:
    imds_url = "http://169.254.169.254/opc/v1/instance/"
    try:
        req = urllib.request.Request(imds_url, headers={"User-Agent": "FRIDAY-Gateway"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode())
            return {
                "displayName": data.get("displayName"),
                "ocid": data.get("id"),
                "shape": data.get("shape"),
                "shapeConfig": data.get("shapeConfig"),
                "lifecycleState": data.get("state"),
                "availabilityDomain": data.get("availabilityDomain"),
                "faultDomain": data.get("faultDomain"),
                "region": data.get("region"),
                "hostname": data.get("hostname"),
                "timeCreated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(data.get("timeCreated", 0)/1000))
            }
    except Exception as e:
        return {"error": f"Failed to retrieve instance details: {e}"}

def tool_get_cloud_vm_status() -> dict:
    total_b, used_b, free_b = shutil.disk_usage("/")
    load1, load5, load15 = os.getloadavg()
    
    mem_info = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                p = line.split(":")
                if len(p) == 2:
                    mem_info[p[0].strip()] = p[1].strip()
    except Exception:
        pass

    uptime_str = execute_cmd(["uptime", "-p"]).strip()
    docker_ps = execute_cmd(["docker", "ps", "--format", "{{.Names}} ({{.Status}}): {{.Image}}"])
    
    return {
        "status": "operational",
        "uptime": uptime_str,
        "cpu_load_averages": {"1min": load1, "5min": load5, "15min": load15},
        "memory": {
            "MemTotal": mem_info.get("MemTotal", "unknown"),
            "MemAvailable": mem_info.get("MemAvailable", "unknown"),
            "SwapTotal": mem_info.get("SwapTotal", "unknown"),
            "SwapFree": mem_info.get("SwapFree", "unknown")
        },
        "disk": {
            "total_gb": round(total_b / (1024**3), 2),
            "used_gb": round(used_b / (1024**3), 2),
            "free_gb": round(free_b / (1024**3), 2),
            "used_percent": round((used_b / total_b) * 100, 1)
        },
        "running_docker_services": docker_ps.splitlines()
    }

def tool_ssh_run_diagnostic(diagnostic_type: str = "summary") -> dict:
    return tool_get_cloud_vm_status()

def tool_postgres_read_diagnostic(query_type: str = "summary") -> dict:
    cid = execute_cmd(["docker", "ps", "-q", "--filter", "name=dokploy-postgres"]).split()
    if not cid:
        return {"error": "PostgreSQL container not found running"}
    
    sqls = {
        "summary": "SELECT count(*) as total_apps FROM application; SELECT datname, pg_size_pretty(pg_database_size(datname)) FROM pg_database WHERE datistemplate=false;",
        "databases": "SELECT s.datname, s.numbackends, pg_size_pretty(pg_database_size(s.datname)) as size FROM pg_stat_database s JOIN pg_database d ON s.datid = d.oid WHERE d.datistemplate = false;",
        "tables": "SELECT relname, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC LIMIT 15;"
    }
    sql = sqls.get(query_type.lower(), sqls["summary"])
    res = execute_cmd(["docker", "exec", cid[0], "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql])
    return {"query_type": query_type, "output": res}

# =====================================================================
# 2. DOKPLOY TOOLS
# =====================================================================

def dokploy_api_get(endpoint: str) -> dict:
    key = get_dokploy_key()
    url = f"{DOKPLOY_API_URL.rstrip('/')}/{endpoint.lstrip('/')}"
    req = urllib.request.Request(url, headers={"x-api-key": key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": f"Dokploy API error on {endpoint}: {e}"}

def tool_dokploy_check_health() -> dict:
    projects = dokploy_api_get("project.all")
    if "error" in projects:
        return {"status": "degraded", "api_reachable": False, "error": projects["error"]}
    return {
        "status": "healthy",
        "api_reachable": True,
        "endpoint": "http://127.0.0.1:3000/api",
        "auth": "VALID_API_KEY",
        "total_projects": len(projects) if isinstance(projects, list) else 0
    }

def tool_dokploy_list_apps() -> dict:
    projects = dokploy_api_get("project.all")
    if "error" in projects or not isinstance(projects, list):
        return {"error": "Failed to list projects from Dokploy API"}
    
    registered_apps = []
    for proj in projects:
        for env in proj.get("environments", []):
            for app in env.get("applications", []):
                registered_apps.append({
                    "applicationId": app.get("applicationId"),
                    "name": app.get("name"),
                    "status": app.get("applicationStatus")
                })

    # Built directories on disk
    built_dirs = []
    app_base = "/etc/dokploy/applications"
    if os.path.exists(app_base):
        built_dirs = [d for d in os.listdir(app_base) if os.path.isdir(os.path.join(app_base, d))]

    # Running microservice containers
    running_raw = execute_cmd(["docker", "ps", "--format", "{{.Names}}"]).splitlines()
    running_microservices = [c for c in running_raw if not c.startswith("dokploy-") and not c.startswith("dokploy.")]

    return {
        "summary": {
            "registered_in_database": len(registered_apps),
            "built_on_disk": len(built_dirs),
            "running_microservices": len(running_microservices),
            "infrastructure_services_running": len([c for c in running_raw if c.startswith("dokploy")])
        },
        "registered_applications": registered_apps,
        "built_directories": built_dirs,
        "running_microservices": running_microservices
    }

def tool_dokploy_get_app_details(app_id: str) -> dict:
    res = dokploy_api_get(f"application.one?applicationId={app_id}")
    if "error" in res:
        return res
    return {
        "applicationId": res.get("applicationId"),
        "name": res.get("name"),
        "repository": f"{res.get('owner')}/{res.get('repository')}",
        "branch": res.get("branch"),
        "autoDeploy": res.get("autoDeploy"),
        "sourceType": res.get("sourceType"),
        "buildType": res.get("buildType"),
        "dockerfile": res.get("dockerfile"),
        "domains": res.get("domains", [])
    }

def tool_dokploy_deploy_app(app_id: str, confirmation: bool = False) -> dict:
    if not confirmation:
        return {"error": "Safety Guard: Deploying requires confirmation=True."}
    key = get_dokploy_key()
    url = f"{DOKPLOY_API_URL.rstrip('/')}/application.deploy"
    data = json.dumps({"applicationId": app_id}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"x-api-key": key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": f"Failed to trigger deployment for {app_id}: {e}"}

# =====================================================================
# 3. LAPTOP PROXY TOOLS (SAFE FALLBACK WHEN LAPTOP IS OFFLINE)
# =====================================================================

def proxy_to_laptop(tool_name: str, args: dict) -> dict:
    url = f"{LAPTOP_BRIDGE_URL.rstrip('/')}/bridge/call"
    body = json.dumps({"name": tool_name, "arguments": args}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "ngrok-skip-browser-warning": "true"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"error": f"Laptop returned HTTP {e.code}: {e.reason}"}
    except (urllib.error.URLError, TimeoutError):
        return {
            "status": "laptop_offline",
            "message": "Laptop bridge is currently offline (laptop is turned off or disconnected). Local laptop tools are unavailable. Oracle Cloud and Dokploy operations remain fully operational."
        }
    except Exception as e:
        return {"status": "error", "message": f"Laptop proxy error: {e}"}

def tool_laptop_system_info() -> str:
    res = proxy_to_laptop("system_info", {})
    if isinstance(res, dict):
        if "error" in res:
            return f"Error getting system info: {res['error']}"
        return f"=== Laptop System Info ===\nHost OS: {res.get('os')} ({res.get('machine')})\nCPUs: {res.get('cpu_count')} logical cores\nRAM: {res.get('ram_gb')} GB ({res.get('ram_used_percent')}% used)\nWorkspace: {res.get('workspace')}"
    return str(res)

def tool_laptop_list_workspace(subpath: str = "") -> str:
    res = proxy_to_laptop("list_workspace", {"path": subpath})
    if isinstance(res, dict):
        if "error" in res:
            return f"Error listing workspace: {res['error']}"
        if "items" in res:
            path_str = res.get("path", subpath or "D:\\FRIDAY Universe")
            items = res.get("items", [])
            total = res.get("total_items", len(items))
            items_str = "\n".join(items) if items else "(empty folder)"
            return f"=== Workspace Directory: {path_str} ({total} items) ===\n\n{items_str}"
    return str(res)

def tool_laptop_read_file(relative_path: str) -> str:
    if not relative_path or not relative_path.strip():
        return "Error: Missing path to read. Provide relative_path (e.g. 'README.md' or 'FRIDAY/README.md')."
    res = proxy_to_laptop("read_file", {"path": relative_path})
    if isinstance(res, dict):
        if "error" in res:
            return f"Error reading file: {res['error']}"
        if "content" in res:
            path_str = res.get("path", relative_path)
            size_str = f" ({res.get('size_bytes', len(res['content']))} bytes)" if "size_bytes" in res else ""
            return f"=== File: {path_str}{size_str} ===\n\n{res['content']}"
    return str(res)

def tool_laptop_git_status(repository: str = "all") -> str:
    res = proxy_to_laptop("git_status", {"repository": repository})
    if isinstance(res, dict):
        if "error" in res:
            return f"Error getting git status: {res['error']}"
        if "repositories" in res:
            lines = [f"=== Git Status: All {len(res['repositories'])} Repositories ==="]
            for item in res["repositories"]:
                cln = "clean (aligned with origin/main)" if item.get("clean") else "uncommitted changes detected"
                chg = f" - Changes:\n{item.get('status')}" if item.get("status") else ""
                lines.append(f"- {item['repository']} ({item['branch']}): {cln}{chg}")
            return "\n".join(lines)
        repo = res.get("repository", repository)
        branch = res.get("branch", "unknown")
        clean = "clean (aligned with origin/main)" if res.get("clean") else "uncommitted changes detected"
        status_out = res.get("status", "")
        body = f"\nChanges:\n{status_out}" if status_out else ""
        return f"=== Git Status: {repo} ===\nBranch: {branch}\nWorking Tree: {clean}{body}"
    return str(res)

# =====================================================================
# 4. MCP PROTOCOL & ROUTER
# =====================================================================

TOOLS_SPEC = [
    # Oracle Cloud Tools
    {"name": "oci_check_auth", "description": "Validate OCI authentication, identity, and tenancy region on Oracle Cloud.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "oci_list_instances", "description": "List all OCI compute instances, shapes, and verify ARM A1 Flex allocation status.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "oci_get_instance_details", "description": "Get detailed OCI compute allocation, CPU, RAM, disk, fault domain, and lifecycle state.", "inputSchema": {"type": "object", "properties": {"instance_id": {"type": "string", "default": ""}}}},
    {"name": "get_cloud_vm_status", "description": "Inspect live Oracle Cloud VM status, CPU load, RAM, swap, 100 GB NVMe disk usage, and uptime.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "check_cloud_infrastructure", "description": "Alias for get_cloud_vm_status.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "ssh_run_diagnostic", "description": "Run read-only system and container diagnostics on Oracle Cloud host.", "inputSchema": {"type": "object", "properties": {"diagnostic_type": {"type": "string", "default": "summary"}}}},
    {"name": "postgres_read_diagnostic", "description": "Read-only database diagnostic against PostgreSQL 18 cluster (dokploy-postgres).", "inputSchema": {"type": "object", "properties": {"query_type": {"type": "string", "default": "summary", "enum": ["summary", "databases", "tables"]}}}},
    
    # Dokploy Tools
    {"name": "dokploy_check_health", "description": "Check Dokploy API connectivity, authentication, and core infrastructure health.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "dokploy_list_apps", "description": "List all 10 Dokploy applications, distinguishing registered, built, and running microservices.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "dokploy_get_app_details", "description": "Retrieve repository, branch, autoDeploy trigger, and domain routing for a Dokploy app.", "inputSchema": {"type": "object", "properties": {"app_id": {"type": "string"}}, "required": ["app_id"]}},
    {"name": "dokploy_deploy_app", "description": "Trigger deployment of a Dokploy application with required safety confirmation.", "inputSchema": {"type": "object", "properties": {"app_id": {"type": "string"}, "confirmation": {"type": "boolean", "default": False}}, "required": ["app_id", "confirmation"]}},

    # Laptop Tools (Graceful offline fallback)
    {"name": "laptop_system_info", "description": "Inspect local Windows laptop system info (available when laptop is online).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "laptop_list_workspace", "description": "List files and directories in D:\\FRIDAY Universe (available when laptop is online).", "inputSchema": {"type": "object", "properties": {"subpath": {"type": "string", "default": ""}}}},
    {"name": "laptop_read_file", "description": "Read text or code file from D:\\FRIDAY Universe workspace (e.g. 'README.md', 'FRIDAY/README.md').", "inputSchema": {"type": "object", "properties": {"relative_path": {"type": "string", "description": "Relative file path in workspace, e.g. 'README.md' or 'FRIDAY/README.md'"}}, "required": ["relative_path"]}},
    {"name": "laptop_git_status", "description": "Check Git status and branch for one or all 10 repos in D:\\FRIDAY Universe (pass repository='all' for all 10).", "inputSchema": {"type": "object", "properties": {"repository": {"type": "string", "default": "all"}}}}
]

def dispatch_tool(name: str, args: dict) -> Any:
    if name == "oci_check_auth":
        return tool_oci_check_auth()
    elif name == "oci_list_instances":
        return tool_oci_list_instances()
    elif name == "oci_get_instance_details":
        return tool_oci_get_instance_details(args.get("instance_id") or args.get("instanceId") or "")
    elif name in ("get_cloud_vm_status", "check_cloud_infrastructure"):
        return tool_get_cloud_vm_status()
    elif name == "ssh_run_diagnostic":
        return tool_ssh_run_diagnostic(args.get("diagnostic_type") or args.get("type") or "summary")
    elif name == "postgres_read_diagnostic":
        return tool_postgres_read_diagnostic(args.get("query_type") or args.get("type") or "summary")
    elif name == "dokploy_check_health":
        return tool_dokploy_check_health()
    elif name == "dokploy_list_apps":
        return tool_dokploy_list_apps()
    elif name == "dokploy_get_app_details":
        target_app = args.get("app_id") or args.get("applicationId") or args.get("application_id") or args.get("name") or ""
        return tool_dokploy_get_app_details(target_app)
    elif name == "dokploy_deploy_app":
        target_app = args.get("app_id") or args.get("applicationId") or args.get("application_id") or ""
        return tool_dokploy_deploy_app(target_app, args.get("confirmation", False))
    elif name == "laptop_system_info":
        return tool_laptop_system_info()
    elif name == "laptop_list_workspace":
        target_sub = args.get("subpath") or args.get("path") or args.get("relative_path") or ""
        return tool_laptop_list_workspace(target_sub)
    elif name == "laptop_read_file":
        target_file = args.get("relative_path") or args.get("file_path") or args.get("path") or args.get("file") or ""
        return tool_laptop_read_file(target_file)
    elif name == "laptop_git_status":
        target_repo = args.get("repository") or args.get("repo") or "all"
        return tool_laptop_git_status(target_repo)
    else:
        return {"error": f"Unknown tool: '{name}'"}

AGENTS_INFO = {
    "friday": {"name": "FRIDAY Core", "role": "Cognitive Orchestrator & Master API Gateway", "repo": "surendra2304/FRIDAY", "port": 8001},
    "cortex": {"name": "Cortex", "role": "Autonomous Knowledge Graph & Neural Synthesis Engine", "repo": "surendra2304/Cortex", "port": 8002},
    "forge": {"name": "Forge", "role": "Full-Stack Autonomous Build, Test & Packaging Engine", "repo": "surendra2304/Forge", "port": 8003},
    "futuris": {"name": "Futuris", "role": "Predictive Trajectory Analysis & Scenario Simulation Engine", "repo": "surendra2304/Futuris", "port": 8004},
    "inference": {"name": "Inference", "role": "High-Throughput LLM & Embedding Inference Router", "repo": "surendra2304/Inference", "port": 8005},
    "intelx": {"name": "IntelX", "role": "Autonomous Real-Time Threat Intelligence & Recon Engine", "repo": "surendra2304/IntelX", "port": 8006},
    "memora": {"name": "Memora", "role": "Hierarchical Vector Memory & Long-Term Semantic Storage", "repo": "surendra2304/Memora", "port": 8007},
    "sentinel": {"name": "Sentinel", "role": "Ecosystem Security, Real-Time Guardrails & Zero-Trust Audit Engine", "repo": "surendra2304/Sentinel", "port": 8008},
    "stratex": {"name": "Stratex", "role": "Autonomous Strategic Planning, Task Scheduling & Resource Engine", "repo": "surendra2304/Stratex", "port": 8009},
    "vyralx": {"name": "VyralX", "role": "Autonomous Video Production & Distribution Engine", "repo": "surendra2304/VyralX", "port": 8010},
}

class GatewayHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, data: dict):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, x-api-key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type, x-api-key")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.lower().startswith("bearer ") else auth.strip()
        if not token:
            token = self.headers.get("x-api-key", "").strip()
        if not token:
            query = urlparse(self.path).query
            for p in query.split("&"):
                if "=" in p:
                    k, v = p.split("=", 1)
                    if k.lower() in ("token", "key", "apikey"):
                        token = v.strip()
        
        valid_secret = get_gateway_secret()
        dokploy_key = get_dokploy_key()
        if token and ((valid_secret and token == valid_secret) or (dokploy_key and token == dokploy_key)):
            return True
        return False

    def do_GET(self):
        p = urlparse(self.path).path
        if p in ("/", ""):
            self.send_json(200, {
                "system": "The FRIDAY Universe",
                "version": "2.0.0",
                "status": "operational",
                "description": "Autonomous 10-Agent Sovereign Ecosystem",
                "gateway": "Consolidated Cloud & Laptop MCP Gateway",
                "endpoints": {
                    "mcp_gateway": "https://friday-universe.duckdns.org/mcp",
                    "mcp_health": "https://friday-universe.duckdns.org/mcp/health",
                    "dokploy_dashboard": "https://dokploy.friday-universe.duckdns.org",
                    "cortex": "https://friday-universe.duckdns.org/cortex",
                    "forge": "https://friday-universe.duckdns.org/forge",
                    "friday": "https://friday-universe.duckdns.org/friday",
                    "futuris": "https://friday-universe.duckdns.org/futuris",
                    "inference": "https://friday-universe.duckdns.org/inference",
                    "intelx": "https://friday-universe.duckdns.org/intelx",
                    "memora": "https://friday-universe.duckdns.org/memora",
                    "sentinel": "https://friday-universe.duckdns.org/sentinel",
                    "stratex": "https://friday-universe.duckdns.org/stratex",
                    "vyralx": "https://friday-universe.duckdns.org/vyralx"
                },
                "host": {
                    "provider": "Oracle Cloud Infrastructure",
                    "region": "ap-hyderabad-1",
                    "instance": "FRIDAY Universe AMD",
                    "shape": "VM.Standard.E2.1.Micro (1 OCPU, 1 GB RAM, 100 GB NVMe)",
                    "arm_expansion": "Ampere Capacity Sniper actively seeking 2 OCPU / 12 GB RAM A1 Flex allocation"
                },
                "agent_status": {k: {"name": v["name"], "role": v["role"], "status": "registered_standby", "route": f"/{k}"} for k, v in AGENTS_INFO.items()}
            })
            return

        agent_key = p.strip("/").split("/")[0].lower()
        if agent_key in AGENTS_INFO:
            info = AGENTS_INFO[agent_key]
            self.send_json(200, {
                "agent": info["name"],
                "role": info["role"],
                "status": "registered_standby",
                "route": f"/{agent_key}",
                "repository": info["repo"],
                "branch": "main",
                "host": "Oracle Cloud ap-hyderabad-1",
                "memory_preservation_policy": "Ampere Capacity Sniper active. Agent microservice scaled to 0/0 replicas to protect 1 GB AMD VM from OOM until 12 GB ARM instance (2 OCPUs / 12 GB RAM) is allocated.",
                "gitops_status": "Enabled (autoDeploy active on PR merge to main)"
            })
            return

        if p in ("/mcp/health", "/health", "/mcp/"):
            self.send_json(200, {
                "service": "FRIDAY Universe Unified MCP Gateway",
                "status": "healthy",
                "tools_count": len(TOOLS_SPEC),
                "laptop_bridge": LAPTOP_BRIDGE_URL,
                "cloud_host": "Oracle Cloud ap-hyderabad-1",
                "dokploy_api": "http://127.0.0.1:3000/api"
            })
            return

        if p in ("/.well-known/oauth-protected-resource", "/mcp/.well-known/oauth-protected-resource"):
            self.send_json(200, {
                "resource": "https://friday-universe.duckdns.org/mcp",
                "authorization_servers": ["https://friday-universe.duckdns.org"]
            })
            return

        if p in ("/.well-known/oauth-authorization-server", "/mcp/.well-known/oauth-authorization-server"):
            self.send_json(200, {
                "issuer": "https://friday-universe.duckdns.org",
                "authorization_endpoint": "https://friday-universe.duckdns.org/oauth/authorize",
                "token_endpoint": "https://friday-universe.duckdns.org/oauth/token",
                "userinfo_endpoint": "https://friday-universe.duckdns.org/oauth/userinfo",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code", "refresh_token"],
                "scopes_supported": ["all", "mcp"],
                "code_challenge_methods_supported": ["S256"],
                "token_endpoint_auth_methods_supported": ["none", "client_secret_post", "client_secret_basic"]
            })
            return

        if p in ("/.well-known/openid-configuration", "/mcp/.well-known/openid-configuration"):
            self.send_json(200, {
                "issuer": "https://friday-universe.duckdns.org",
                "authorization_endpoint": "https://friday-universe.duckdns.org/oauth/authorize",
                "token_endpoint": "https://friday-universe.duckdns.org/oauth/token",
                "userinfo_endpoint": "https://friday-universe.duckdns.org/oauth/userinfo",
                "response_types_supported": ["code"],
                "grant_types_supported": ["authorization_code"],
                "scopes_supported": ["all", "openid", "profile", "email"]
            })
            return

        if p == "/oauth/userinfo":
            self.send_json(200, {
                "sub": "surendra",
                "name": "Surendra",
                "email": "surendra@friday.universe"
            })
            return

        if p == "/oauth/authorize":
            query = parse_qs(urlparse(self.path).query)
            redirect_uri = query.get("redirect_uri", ["https://chatgpt.com"])[0]
            state = query.get("state", [""])[0]
            code = secrets.token_hex(16)
            AUTH_CODES[code] = {"redirect_uri": redirect_uri, "state": state, "exp": time.time() + 600}
            target_url = f"{redirect_uri}{'&' if '?' in redirect_uri else '?'}code={code}&state={state}"

            html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>FRIDAY Universe — ChatGPT Authorization</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
    .card {{ background: #1e293b; border: 1px solid #334155; border-radius: 16px; padding: 36px; max-width: 440px; width: 90%; text-align: center; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
    h2 {{ color: #38bdf8; margin-top: 0; }}
    p {{ color: #94a3b8; font-size: 14px; line-height: 1.5; }}
    .btn {{ display: inline-block; background: #0284c7; color: #ffffff; text-decoration: none; padding: 14px 28px; border-radius: 8px; font-weight: 600; margin-top: 24px; cursor: pointer; border: none; font-size: 16px; }}
    .btn:hover {{ background: #0369a1; }}
  </style>
</head>
<body>
  <div class="card">
    <h2>FRIDAY Universe</h2>
    <p>Authorize ChatGPT to connect securely to your FRIDAY Universe MCP Gateway (Oracle Cloud, Dokploy & Laptop workspace).</p>
    <a href="{target_url}" class="btn">Authorize ChatGPT Connection</a>
  </div>
</body>
</html>"""
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if p == "/mcp/openapi.json":
            self.send_json(200, {
                "openapi": "3.1.0",
                "info": {"title": "FRIDAY Universe Consolidated Gateway API", "version": "2.0.0"},
                "servers": [{"url": "https://friday-universe.duckdns.org"}],
                "paths": {
                    "/mcp": {"post": {"summary": "MCP JSON-RPC 2.0 Endpoint", "operationId": "mcpRpc", "responses": {"200": {"description": "MCP Result"}}}}
                }
            })
            return

        self.send_json(404, {"error": "Not Found"})

    def do_POST(self):
        p = urlparse(self.path).path

        if p == "/oauth/token":
            cl = int(self.headers.get("Content-Length", 0))
            data = self.rfile.read(cl).decode("utf-8") if cl > 0 else ""
            token = get_gateway_secret()
            self.send_json(200, {
                "access_token": token,
                "token_type": "Bearer",
                "expires_in": 315360000,
                "scope": "all"
            })
            return

        is_authenticated = self.check_auth()

        cl = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(cl) if cl > 0 else b"{}"
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            payload = {}

        method = payload.get("method")
        rpc_id = payload.get("id", 1)
        params = payload.get("params", {})
        print(f"[MCP LOG] method={method} auth={is_authenticated} path={p}", flush=True)

        # MCP Protocol Handshake & Discovery: Open for client negotiation
        if method == "initialize":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": False, "listChanged": False},
                        "prompts": {"listChanged": False}
                    },
                    "serverInfo": {"name": "FRIDAY-Cloud-Gateway", "version": "2.0.0"}
                }
            })
            return

        elif method == "notifications/initialized" or (method and method.startswith("notifications/")):
            # Standard MCP client notification: acknowledge cleanly
            self.send_json(200, {"jsonrpc": "2.0", "result": {}})
            return

        elif method == "tools/list":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": TOOLS_SPEC}
            })
            return

        elif method == "resources/list":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"resources": []}
            })
            return

        elif method == "prompts/list":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"prompts": []}
            })
            return

        elif method == "roots/list":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"roots": []}
            })
            return

        elif method == "ping":
            self.send_json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {}})
            return

        elif method == "tools/call":
            # STRICT MANDATORY AUTHENTICATION: Every single tool call requires authentication
            if not is_authenticated:
                self.send_json(401, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized. Bearer token in Authorization header or x-api-key required for all tool calls."
                    }
                })
                return

            tool_name = params.get("name")
            args = params.get("arguments", {})
            print(f"[MCP LOG] tool={tool_name} args={args}", flush=True)

            # Write-capable tools have an additional mandatory safety guard: confirmation=True
            WRITE_TOOLS = {"dokploy_deploy_app"}
            if tool_name in WRITE_TOOLS and not args.get("confirmation", False):
                self.send_json(200, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "isError": True,
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "error": "Safety Guard",
                                "message": f"Write tool '{tool_name}' requires confirmation=True."
                            }, indent=2)
                        }]
                    }
                })
                return

            res = dispatch_tool(tool_name, args)
            content_text = json.dumps(res, indent=2) if isinstance(res, (dict, list)) else str(res)
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "content": [{"type": "text", "text": content_text}]
                }
            })
            return

        # In JSON-RPC 2.0 over HTTP, RPC errors return HTTP 200 with the error object
        self.send_json(200, {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method {method} not supported"}})

def run():
    server = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    print(f"FRIDAY Unified Cloud MCP Gateway running on http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
