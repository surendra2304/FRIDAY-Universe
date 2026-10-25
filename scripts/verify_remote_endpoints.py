import subprocess
import json

KEY_PATH = r"C:\Users\Surendra\.ssh\friday_universe_oracle.key"
S1 = "140.245.208.100"
S2 = "140.245.243.168"

def ssh_exec(host, command):
    p = subprocess.run(
        ["ssh", "-n", "-i", KEY_PATH, "-o", "BatchMode=yes", f"ubuntu@{host}", command],
        capture_output=True,
        text=True,
        timeout=15
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()

print("--- Testing Stratex AutoHedge on S1 ---")
# send valid json via curl with escaped quotes
payload = json.dumps({"signals": [0.5, 0.7, 0.2]})
curl_cmd = f"curl -s -X POST http://localhost:8003/api/v1/trading/engines/autohedge/consensus -H 'Content-Type: application/json' -d '{payload}'"
rc, out, err = ssh_exec(S1, curl_cmd)
print("Returncode:", rc)
print("Output:", out)
if err:
    print("Error:", err)

print("\n--- Testing Stratex Technicals on S1 ---")
payload2 = json.dumps({"prices": [10.0 + i for i in range(30)], "window": 14})
curl_cmd2 = f"curl -s -X POST http://localhost:8003/api/v1/trading/engines/fincept/technical -H 'Content-Type: application/json' -d '{payload2}'"
rc, out, err = ssh_exec(S1, curl_cmd2)
print("Returncode:", rc)
print("Output:", out)

print("\n--- Testing VyralX Claude-Ads on S2 ---")
payload3 = json.dumps({"platform": "google", "daily_budget": 100.0, "campaign_type": "search"})
curl_cmd3 = f"curl -s -X POST http://localhost:8010/api/v1/vyralx/engines/ads/campaign -H 'Content-Type: application/json' -d '{payload3}'"
rc, out, err = ssh_exec(S2, curl_cmd3)
print("Returncode:", rc)
print("Output:", out)
