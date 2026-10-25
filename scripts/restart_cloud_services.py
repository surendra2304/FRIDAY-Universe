import subprocess
import sys
import time

KEY_PATH = r"C:\Users\Surendra\.ssh\friday_universe_oracle.key"
SERVER1_IP = "140.245.208.100"
SERVER2_IP = "140.245.243.168"

def run_ssh(host, cmd):
    res = subprocess.run(
        ["ssh", "-n", "-i", KEY_PATH, "-o", "BatchMode=yes", f"ubuntu@{host}", cmd],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return res.returncode, res.stdout, res.stderr

print("1. Updating Server 1...")
s1_cmd = """
pkill -9 -f "8002|dashboard.py|8006" || true
sleep 1
cd /opt/friday_universe/Memora && nohup /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --workers 1 </dev/null >/dev/null 2>&1 &
cd /opt/friday_universe/Stratex && nohup /opt/friday_universe/venv/bin/python dashboard.py </dev/null >/dev/null 2>&1 &
cd /opt/friday_universe/Forge && nohup /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8006 --workers 1 </dev/null >/dev/null 2>&1 &
sleep 3
"""
rc1, out1, err1 = run_ssh(SERVER1_IP, s1_cmd)
print("Server 1 result:", rc1, out1, err1)

print("2. Updating Server 2...")
s2_cmd = """
pkill -9 -f "8009|8010" || true
sleep 1
cd /opt/friday_universe/VyralX && nohup /opt/friday_universe/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --workers 1 </dev/null >/dev/null 2>&1 &
cd /opt/friday_universe/Cortex && nohup /opt/friday_universe/venv/bin/python -m uvicorn apps.api.src.cortex_api.main:app --host 0.0.0.0 --port 8009 --workers 1 </dev/null >/dev/null 2>&1 &
sleep 3
"""
rc2, out2, err2 = run_ssh(SERVER2_IP, s2_cmd)
print("Server 2 result:", rc2, out2, err2)

print("3. Checking health on Server 1...")
rc, out, _ = run_ssh(SERVER1_IP, "curl -s http://localhost:8002/health; echo; curl -s http://localhost:8003/api/v1/trading/engines/autohedge/consensus -X POST -H 'Content-Type: application/json' -d '{}'; echo; curl -s http://localhost:8006/api/v1/forge/browser/health-report; echo")
print("Server 1 Endpoints:\n", out)

print("4. Checking health on Server 2...")
rc, out, _ = run_ssh(SERVER2_IP, "curl -s http://localhost:8010/api/v1/vyralx/engines/hyperframes/aspect-ratios; echo; curl -s http://localhost:8009/api/v1/cortex/inbox/digest; echo")
print("Server 2 Endpoints:\n", out)
