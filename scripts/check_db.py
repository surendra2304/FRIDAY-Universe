import subprocess

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]
res = subprocess.check_output(f'docker exec {cid} psql -U dokploy -d dokploy -t -c "SELECT count(*) FROM \\"user\\";"', shell=True).decode().strip()
print(f"USER_COUNT={res}")
