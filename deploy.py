import paramiko

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect("192.168.100.12", username="root", password="rongqizhizao1.!", timeout=10)

# Check recent 500 errors
stdin, stdout, stderr = ssh.exec_command(
    "cd /mnt/wxj/latte-pr-agent && docker compose logs webhook-server --tail=50 2>&1 | grep -E '500|ERROR|error|Traceback' -A3"
)
print("=== 500 errors ===")
print(stdout.read().decode())                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           

# Test all main endpoints
endpoints = [
    "GET /health",
    "GET /reviews?page=1",
    "GET /reviews/1",
    "GET /reviews/1/findings",
    "GET /settings",
    "GET /stats",
    "GET /repos",
]
for ep in endpoints:
    method, path = ep.split(" ", 1)
    stdin, stdout, stderr = ssh.exec_command(f"curl -s -o /dev/null -w '%{{http_code}}' -X {method} http://localhost:8003{path} 2>&1")
    code = stdout.read().decode().strip()
    status = "✅" if code == "200" else "❌"
    print(f"{status} {ep} → {code}")

ssh.close()
