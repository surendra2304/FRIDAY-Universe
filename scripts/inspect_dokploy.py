import subprocess
import json

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

def query(sql):
    cmd = ["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql]
    return subprocess.check_output(cmd).decode().strip()

print("--- USERS ---")
print(query("SELECT id, email, \"firstName\" FROM \"user\";"))

print("--- PROJECTS ---")
print(query("SELECT \"projectId\", name FROM project;"))

print("--- ENVIRONMENTS ---")
print(query("SELECT \"environmentId\", name FROM environment;"))
