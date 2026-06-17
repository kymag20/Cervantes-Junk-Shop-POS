import os
import subprocess
import sys


def run(command):
    print(f"Running: {' '.join(command)}", flush=True)
    subprocess.check_call(command)


python = sys.executable

run([python, "manage.py", "migrate", "--noinput"])
run([python, "manage.py", "ensure_default_admin"])

print("Starting Gunicorn...", flush=True)
os.execvp("gunicorn", ["gunicorn", "junkshop_pos.wsgi:application"])

