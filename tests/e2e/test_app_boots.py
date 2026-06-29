"""End-to-end smoke tests for the KinGVisher Streamlit app.

Two complementary checks:

1. ``test_app_imports_and_reaches_dry_run`` runs the script with ``DRY_RUN=true``.
   The app imports every dependency, loads its ``.env`` configuration and then
   stops itself — so an import error, a missing file or a broken dependency
   upgrade fails here quickly.

2. ``test_streamlit_server_serves_health`` boots a real Streamlit server and
   waits for the ``/_stcore/health`` endpoint, proving the service actually
   comes up end-to-end.
"""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
APP = "kingvisher-knowledge_graph_visualizer.py"
APP_TITLE_MARKER = b"KinGVisher"

pytestmark = pytest.mark.e2e


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_app_imports_and_reaches_dry_run():
    env = {**os.environ, "DRY_RUN": "true"}
    proc = subprocess.run(
        [sys.executable, APP],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    combined = proc.stdout + proc.stderr
    assert "Traceback (most recent call last)" not in combined, combined[-2000:]
    assert "ModuleNotFoundError" not in combined, combined[-2000:]
    # The app self-terminates via SIGTERM in dry-run mode; importing succeeded.
    assert "dry run enabled" in combined.lower() or proc.returncode in (0, -signal.SIGTERM, 143)


def test_streamlit_server_serves_health():
    port = _free_port()
    cmd = [
        sys.executable, "-m", "streamlit", "run", APP,
        "--server.headless=true",
        f"--server.port={port}",
        "--server.address=127.0.0.1",
        "--browser.gatherUsageStats=false",
    ]
    proc = subprocess.Popen(
        cmd, cwd=REPO_ROOT,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 120
        healthy = False
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read() if proc.stdout else ""
                pytest.fail(f"streamlit exited early (code {proc.returncode}):\n{out[-2000:]}")
            try:
                r = requests.get(f"{base}/_stcore/health", timeout=2)
                if r.status_code == 200 and r.text.strip().lower() == "ok":
                    healthy = True
                    break
            except requests.RequestException:
                pass
            time.sleep(1)
        assert healthy, "Streamlit /_stcore/health never became ok"

        root = requests.get(f"{base}/", timeout=10)
        assert root.status_code == 200
        assert b"<title>" in root.content
    finally:
        proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()
