import subprocess
import json

SSH_CMD = [
    "ssh", "-o", "BatchMode=yes",
    "-i", r"C:\Users\Surendra\.ssh\friday_universe_oracle.key",
    "ubuntu@140.245.208.100",
    "sudo python3 -"
]

REMOTE_SCRIPT = r'''
import json, urllib.request, os, subprocess

with open('/opt/oracle_mcp/.dokploy_key') as f:
    key = f.read().strip()

req = urllib.request.Request('http://127.0.0.1:3000/api/project.all', headers={'x-api-key': key, 'Accept': 'application/json'})
projects = json.loads(urllib.request.urlopen(req).read().decode())

# Running docker services
swarm_res = subprocess.run(['docker', 'service', 'ls', '--format', '{{.Name}}\t{{.Replicas}}'], capture_output=True, text=True)
running_services = dict([line.split('\t') for line in swarm_res.stdout.strip().split('\n') if '\t' in line])

# Running containers
ps_res = subprocess.run(['docker', 'ps', '--format', '{{.Names}}'], capture_output=True, text=True)
running_containers = ps_res.stdout.strip().split('\n')

disk_apps = os.listdir('/etc/dokploy/applications') if os.path.exists('/etc/dokploy/applications') else []

results = []
for proj in projects:
    for env in proj.get('environments', []):
        for a in env.get('applications', []):
            aid = a.get('applicationId')
            
            # Fetch detailed app info
            one_req = urllib.request.Request(f'http://127.0.0.1:3000/api/application.one?applicationId={aid}', headers={'x-api-key': key})
            try:
                detail = json.loads(urllib.request.urlopen(one_req).read().decode())
            except Exception:
                detail = a
                
            name = detail.get('name')
            app_name = detail.get('appName', '')
            repo = detail.get('repository')
            branch = detail.get('branch')
            auto = detail.get('autoDeploy')
            status = detail.get('applicationStatus')
            
            # Built on disk check
            built = False
            for d in disk_apps:
                if d == app_name or (name and (d == f'friday-{name.lower()}' or d == f'{name.lower()}' or (name.lower() == 'friday' and d == 'friday-core'))):
                    built = True
                    break

            replicas = '0/0'
            for s_name, s_rep in running_services.items():
                if (app_name and app_name in s_name) or (name and name.lower() in s_name.lower()):
                    replicas = s_rep
                    break

            is_running = any((app_name and app_name in c) or (name and (name.lower() in c.lower() or (name.lower() == 'friday' and 'core' in c.lower()))) for c in running_containers if not c.startswith('dokploy'))
            is_healthy = status in ('done', 'idle')

            results.append({
                'name': name,
                'applicationId': aid,
                'appName': app_name,
                'repository': repo,
                'branch': branch,
                'autoDeploy': auto,
                'registered': True,
                'built_on_disk': built,
                'replicas': replicas,
                'running': is_running,
                'status': status,
                'healthy': is_healthy
            })

results.sort(key=lambda x: x['name'])
print(json.dumps(results, indent=2))
'''

proc = subprocess.run(SSH_CMD, input=REMOTE_SCRIPT, capture_output=True, text=True)
if proc.returncode != 0:
    print(f"ERROR: {proc.stderr}")
else:
    print(proc.stdout)
