import subprocess

TRAEFIK_YML = """http:
  routers:
    mcp-router-http:
      rule: Host(`friday-universe.duckdns.org`) && (PathPrefix(`/mcp`) || PathPrefix(`/.well-known`) || PathPrefix(`/oauth`))
      priority: 2500
      service: mcp-service
      entryPoints:
        - web
    mcp-router-https:
      rule: Host(`friday-universe.duckdns.org`) && (PathPrefix(`/mcp`) || PathPrefix(`/.well-known`) || PathPrefix(`/oauth`))
      priority: 2500
      service: mcp-service
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt
  services:
    mcp-service:
      loadBalancer:
        servers:
          - url: http://172.18.0.1:8765
        passHostHeader: true
"""

SSH_CMD = [
    "ssh", "-o", "BatchMode=yes",
    "-i", r"C:\Users\Surendra\.ssh\friday_universe_oracle.key",
    "ubuntu@140.245.208.100",
    "sudo python3 -"
]

REMOTE_SCRIPT = f"""
with open("/etc/dokploy/traefik/dynamic/mcp.yml", "w") as f:
    f.write('''{TRAEFIK_YML}''')
print("SUCCESS: Traefik mcp.yml written.")
"""

proc = subprocess.run(SSH_CMD, input=REMOTE_SCRIPT, capture_output=True, text=True)
print("OUT:", proc.stdout)
if proc.stderr:
    print("ERR:", proc.stderr)
