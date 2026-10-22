import subprocess

cid = subprocess.check_output("docker ps -q --filter name=dokploy-postgres", shell=True).decode().strip().split()[0]

def query(sql):
    cmd = ["docker", "exec", cid, "psql", "-U", "dokploy", "-d", "dokploy", "-c", sql]
    return subprocess.check_output(cmd).decode().strip()

print("--- ORGANIZATIONS OR MEMBERS ---")
print(query("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
print("--- MEMBER ---")
print(query("SELECT * FROM member;"))
