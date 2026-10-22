#!/usr/bin/env python3
import json
import urllib.request

LAPTOP_URL = "https://kite-trouble-decency.ngrok-free.dev/mcp"

def call_laptop_mcp(name: str, args: dict):
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
        LAPTOP_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "ngrok-skip-browser-warning": "true"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    print("--- Testing Laptop Bridge: laptop_execute_command ---")
    res = call_laptop_mcp("laptop_execute_command", {"command": "Get-Date"})
    print("Result:", json.dumps(res, indent=2))
