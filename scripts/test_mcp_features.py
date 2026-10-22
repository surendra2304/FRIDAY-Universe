#!/usr/bin/env python3
import json
import urllib.request

GATEWAY_URL = "https://friday-universe.duckdns.org/mcp"
TOKEN = "c21aa676a59ed41addd5d1de8f52d4f870a5a3ba68ea9d468941d50eb16fa12f"

def call_mcp(name: str, args: dict):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": args
        }
    }
    req = urllib.request.Request(
        GATEWAY_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {TOKEN}"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    print("--- Testing cloud_docker_command ---")
    res1 = call_mcp("cloud_docker_command", {"command": "ps --filter name=dokploy-postgres"})
    print("Docker PS:", json.dumps(res1, indent=2))

    print("\n--- Testing postgres_check_agent_databases ---")
    res2 = call_mcp("postgres_check_agent_databases", {})
    print("Agent DBs:", json.dumps(res2, indent=2))
