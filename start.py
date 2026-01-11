# start.py
import os
import subprocess
import sys

port = os.environ.get("PORT")
if not port:
    print("ERROR: PORT not defined", flush=True)
    sys.exit(1)

print(f"Starting Daphne on port {port}", flush=True)

# Migration + static files
subprocess.run(["python", "manage.py", "migrate", "--noinput"], check=True)
subprocess.run(["python", "manage.py", "collectstatic", "--noinput"], check=True)

# Lancer Daphne
subprocess.run([
    "daphne",
    "-b", "0.0.0.0",
    "-p", port,
    "config.asgi:application"
], check=True)
