import subprocess

SSH_CMD = [
    "ssh", "-o", "BatchMode=yes",
    "-i", r"USER_HOME\.ssh\friday_universe_oracle.key",
    "ubuntu@140.245.208.100",
    "sudo python3 -"
]

REMOTE_SCRIPT = r'''
with open("/opt/oracle_mcp/server.py", "r", encoding="utf-8") as f:
    content = f.read()

# Replace check_auth and do_POST
old_target = """    def check_auth(self) -> bool:
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
        return False"""

new_auth = """    def check_auth(self) -> bool:
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
        
        dokploy_key = get_dokploy_key()
        if token and (token == GATEWAY_SECRET or (dokploy_key and token == dokploy_key)):
            return True
        return False"""

old_post = """    def do_POST(self):
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

        self.send_json(400, {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method {method} not supported"}})"""

new_post = """    def do_POST(self):
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

        # MCP Protocol Handshake & Discovery: Always allowed to establish connection
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
            tool_name = params.get("name")
            args = params.get("arguments", {})

            # Write-capable tools strictly require authentication
            WRITE_TOOLS = {"dokploy_deploy_app"}
            if tool_name in WRITE_TOOLS and not is_authenticated:
                self.send_json(200, {
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "result": {
                        "isError": True,
                        "content": [{
                            "type": "text",
                            "text": json.dumps({
                                "error": "Unauthorized",
                                "message": f"Write-capable tool '{tool_name}' requires authentication. Provide valid Bearer token or append ?token=<GATEWAY_SECRET> to the MCP endpoint URL."
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

        self.send_json(400, {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": -32601, "message": f"Method {method} not supported"}})"""

if old_target in content and old_post in content:
    content = content.replace(old_target, new_auth).replace(old_post, new_post)
    with open("/opt/oracle_mcp/server.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: server.py updated.")
else:
    print("WARNING: Exact strings not matched, writing direct replacement...")
    # fallback find and replace
    import re
    content = re.sub(r'def check_auth\(self\).*?return False', new_auth.strip(), content, flags=re.DOTALL)
    content = re.sub(r'def do_POST\(self\):.*?Method \{method\} not supported"\}\)', new_post.strip(), content, flags=re.DOTALL)
    with open("/opt/oracle_mcp/server.py", "w", encoding="utf-8") as f:
        f.write(content)
    print("SUCCESS: server.py updated via regex.")

import subprocess
res = subprocess.run(["systemctl", "restart", "oracle-cloud-mcp"], capture_output=True, text=True)
print("Systemd restart exit:", res.returncode, res.stdout, res.stderr)
'''

proc = subprocess.run(SSH_CMD, input=REMOTE_SCRIPT, capture_output=True, text=True)
print("OUT:", proc.stdout)
print("ERR:", proc.stderr)
