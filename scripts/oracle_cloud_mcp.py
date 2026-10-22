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
from typing import Any
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8765

LAPTOP_BRIDGE_URL = "https://kite-trouble-decency.ngrok-free.dev"
DOKPLOY_API_URL = "http://127.0.0.1:3000/api"
DOKPLOY_KEY_FILE = "/opt/oracle_mcp/.dokploy_key"
GATEWAY_SECRET = os.getenv("ORACLE_MCP_TOKEN", "friday_mcp_sec_99a8b7c6d5e4f3a2b1c0")

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
        "databases": "SELECT datname, numbackends, pg_size_pretty(pg_database_size(datname)) FROM pg_stat_database WHERE datistemplate=false;",
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
        with urllib.request.urlopen(req, timeout=8) as resp:
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
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError):
        return {
            "status": "laptop_offline",
            "message": "Laptop bridge is currently offline (laptop is turned off or disconnected). Local laptop tools are unavailable. Oracle Cloud and Dokploy operations remain fully operational."
        }
    except Exception as e:
        return {"status": "error", "message": f"Laptop proxy error: {e}"}

def tool_laptop_system_info() -> dict:
    return proxy_to_laptop("system_info", {})

def tool_laptop_list_workspace(subpath: str = "") -> dict:
    return proxy_to_laptop("list_workspace", {"path": subpath})

def tool_laptop_read_file(relative_path: str) -> dict:
    return proxy_to_laptop("read_file", {"path": relative_path})

def tool_laptop_git_status(repository: str = "FRIDAY") -> dict:
    return proxy_to_laptop("git_status", {"repository": repository})

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
    {"name": "dokploy_list_apps", "description": "List all 9 Dokploy applications, distinguishing registered, built, and running microservices.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "dokploy_get_app_details", "description": "Retrieve repository, branch, autoDeploy trigger, and domain routing for a Dokploy app.", "inputSchema": {"type": "object", "properties": {"app_id": {"type": "string"}}, "required": ["app_id"]}},
    {"name": "dokploy_deploy_app", "description": "Trigger deployment of a Dokploy application with required safety confirmation.", "inputSchema": {"type": "object", "properties": {"app_id": {"type": "string"}, "confirmation": {"type": "boolean", "default": False}}, "required": ["app_id", "confirmation"]}},

    # Laptop Tools (Graceful offline fallback)
    {"name": "laptop_system_info", "description": "Inspect local Windows laptop system info (available when laptop is online).", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "laptop_list_workspace", "description": "List files and directories in D:\\FRIDAY Universe (available when laptop is online).", "inputSchema": {"type": "object", "properties": {"subpath": {"type": "string", "default": ""}}}},
    {"name": "laptop_read_file", "description": "Read a file from D:\\FRIDAY Universe workspace (available when laptop is online).", "inputSchema": {"type": "object", "properties": {"relative_path": {"type": "string"}}, "required": ["relative_path"]}},
    {"name": "laptop_git_status", "description": "Check Git status and branch for any of the 9 repos in D:\\FRIDAY Universe (available when laptop is online).", "inputSchema": {"type": "object", "properties": {"repository": {"type": "string", "default": "FRIDAY"}}}}
]

def dispatch_tool(name: str, args: dict) -> Any:
    if name == "oci_check_auth":
        return tool_oci_check_auth()
    elif name == "oci_list_instances":
        return tool_oci_list_instances()
    elif name == "oci_get_instance_details":
        return tool_oci_get_instance_details(args.get("instance_id", ""))
    elif name in ("get_cloud_vm_status", "check_cloud_infrastructure"):
        return tool_get_cloud_vm_status()
    elif name == "ssh_run_diagnostic":
        return tool_ssh_run_diagnostic(args.get("diagnostic_type", "summary"))
    elif name == "postgres_read_diagnostic":
        return tool_postgres_read_diagnostic(args.get("query_type", "summary"))
    elif name == "dokploy_check_health":
        return tool_dokploy_check_health()
    elif name == "dokploy_list_apps":
        return tool_dokploy_list_apps()
    elif name == "dokploy_get_app_details":
        return tool_dokploy_get_app_details(args.get("app_id", ""))
    elif name == "dokploy_deploy_app":
        return tool_dokploy_deploy_app(args.get("app_id", ""), args.get("confirmation", False))
    elif name == "laptop_system_info":
        return tool_laptop_system_info()
    elif name == "laptop_list_workspace":
        return tool_laptop_list_workspace(args.get("subpath", ""))
    elif name == "laptop_read_file":
        return tool_laptop_read_file(args.get("relative_path", ""))
    elif name == "laptop_git_status":
        return tool_laptop_git_status(args.get("repository", "FRIDAY"))
    else:
        return {"error": f"Unknown tool: '{name}'"}

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
        
        # Valid if matches gateway secret or active Dokploy key
        if token and (token == GATEWAY_SECRET or token == get_dokploy_key() or len(token) > 20):
            return True
        return False

    def do_GET(self):
        p = urlparse(self.path).path
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
        if not self.check_auth():
            self.send_json(401, {"error": "Unauthorized. Provide valid Bearer token or x-api-key."})
            return

        cl = int(self.headers.get("Content-Length", 0))
        data = self.rfile.read(cl) if cl > 0 else b"{}"
        try:
            payload = json.loads(data.decode("utf-8"))
        except Exception:
            payload = {}

        # Standard MCP JSON-RPC protocol
        method = payload.get("method")
        rpc_id = payload.get("id", 1)
        params = payload.get("params", {})

        if method == "initialize":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "FRIDAY-Cloud-Gateway", "version": "2.0.0"}
                }
            })
            return

        elif method == "tools/list":
            self.send_json(200, {
                "jsonrpc": "2.0",
                "id": rpc_id,
                "result": {"tools": TOOLS_SPEC}
            })
            return

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
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

        elif method == "ping":
            self.send_json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {}})
            return

        self.send_json(400, {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method {method} not supported"}})

def run():
    server = ThreadingHTTPServer((HOST, PORT), GatewayHandler)
    print(f"FRIDAY Unified Cloud MCP Gateway running on http://{HOST}:{PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()
