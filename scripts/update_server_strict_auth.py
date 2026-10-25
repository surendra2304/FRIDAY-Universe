import subprocess

SSH_CMD = [
    "ssh", "-o", "BatchMode=yes",
    "-i", r"USER_HOME\.ssh\friday_universe_oracle.key",
    "ubuntu@140.245.208.100",
    "sudo python3 -"
]

REMOTE_SCRIPT = r"""
with open("/opt/oracle_mcp/server.py", "r", encoding="utf-8") as f:
    code = f.read()

import re

# 1. Update GATEWAY_SECRET definition
new_sec_def = 'GATEWAY_SECRET_FILE = "/opt/oracle_mcp/.gateway_secret"\n\ndef get_gateway_secret() -> str:\n    if os.path.exists(GATEWAY_SECRET_FILE):\n        try:\n            with open(GATEWAY_SECRET_FILE, "r", encoding="utf-8") as f:\n                return f.read().strip()\n        except Exception:\n            pass\n    return os.getenv("ORACLE_MCP_TOKEN", "")'

code = re.sub(r'GATEWAY_SECRET = os\.getenv\(.*?\)', new_sec_def, code)

# 2. Update check_auth
new_auth = '''    def check_auth(self) -> bool:
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
        return False'''

code = re.sub(r'    def check_auth\(self\).*?return False', new_auth, code, flags=re.DOTALL)

# 3. Update do_POST to require authentication for EVERY tool call
new_do_post = '''    def do_POST(self):
        p = urlparse(self.path).path
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

        # MCP Protocol Handshake & Discovery: Open for client negotiation
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

        elif method == "ping":
            self.send_json(200, {"jsonrpc": "2.0", "id": rpc_id, "result": {}})
            return

        elif method == "tools/call":
            # STRICT AUTHENTICATION: Every tool call requires authentication
            if not is_authenticated:
                self.send_json(401, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": {
                        "code": -32001,
                        "message": "Unauthorized. Bearer token or x-api-key required for all tool calls."
                    }
                })
                return

            tool_name = params.get("name")
            args = params.get("arguments", {})

            # Write-capable tools require safety confirmation=True
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

        self.send_json(400, {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method {method} not supported"}})'''

code = re.sub(r'    def do_POST\(self\):.*?Method \{method\} not supported"\}\)', new_do_post, code, flags=re.DOTALL)

with open("/opt/oracle_mcp/server.py", "w", encoding="utf-8") as f:
    f.write(code)

import subprocess
res = subprocess.run(["systemctl", "restart", "oracle-cloud-mcp"], capture_output=True, text=True)
print("Systemd restart exit:", res.returncode)
"""

proc = subprocess.run(SSH_CMD, input=REMOTE_SCRIPT, capture_output=True, text=True)
print("REMOTE OUT:", proc.stdout)
if proc.stderr:
    print("REMOTE ERR:", proc.stderr)
