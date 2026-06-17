import subprocess
import sys


def run(command):
    print(f"Running: {' '.join(command)}", flush=True)
    subprocess.check_call(command)


python = sys.executable

run([python, "-m", "pip", "install", "-r", "requirements.txt"])
run([python, "manage.py", "collectstatic", "--noinput"])
run([python, "manage.py", "migrate", "--noinput"])
run([python, "manage.py", "ensure_default_admin"])

