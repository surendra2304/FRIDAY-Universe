import json
import subprocess

def check():
    # 1. ACME domains
    try:
        raw = subprocess.check_output("sudo cat /etc/dokploy/traefik/dynamic/acme.json", shell=True).decode()
        data = json.loads(raw)
        certs = data.get("letsencrypt", {}).get("Certificates", [])
        print("=== SSL CERTIFICATES IN ACME.JSON ===")
        for c in certs:
            domain = c.get("certificate", {}).get("domain", {})
            print(f"Domain: {domain.get('main')} | Sans: {domain.get('sans')}")
    except Exception as e:
        print("Error reading acme.json:", e)

    # 2. Check docker services and networks
    try:
        ps = subprocess.check_output("docker ps --format 'table {{.Names}}\t{{.Ports}}'", shell=True).decode()
        print("\n=== RUNNING DOCKER CONTAINERS ===")
        print(ps)
    except Exception as e:
        print("Error docker ps:", e)

if __name__ == "__main__":
    check()
