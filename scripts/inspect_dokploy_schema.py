import subprocess

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

def query(sql):
    cmd = ["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql]
    return subprocess.check_output(cmd).decode().strip()

print("--- PROJECT SCHEMA ---")
print(query("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'project';"))

print("--- ENVIRONMENT SCHEMA ---")
print(query("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'environment';"))

print("--- USER/ORGANIZATION ---")
print(query("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'user';"))
