"""
Start All Agents
Launches all agent servers + the pipeline orchestrator in separate terminal windows.
Run: python start_all.py
"""

import subprocess
import sys
import time
import requests
import os

AGENTS = [
    {"name": "Agent 1  (Transcript)",      "module": "Agent1.api.main:app",       "port": 8004},
    {"name": "Agent 2  (Competitor Free)",  "module": "Agent2_Free.api.main:app",  "port": 8001},
    {"name": "Agent 3  (YouTube/Gemini)",   "module": "Agent3.api.main:app",       "port": 8002},
    {"name": "Agent 3F (Free)",             "module": "Agent3_Free.api.main:app",  "port": 8003},
    {"name": "Agent 4  (Insights)",         "module": "Agent4.api.main:app",       "port": 8005},
    {"name": "Agent 5  (Synthesis)",        "module": "Agent5.api.main:app",       "port": 8006},
    {"name": "Agent 6  (Briefs)",           "module": "Agent6.api.main:app",       "port": 8007},
    {"name": "Agent 7  (Copilot)",          "module": "Agent7.api.main:app",       "port": 8008},
    {"name": "Pipeline (Orchestrator)",     "module": "pipeline:app",              "port": 8000},
]


def is_running(port: int) -> bool:
    try:
        requests.get(f"http://localhost:{port}/health", timeout=2)
        return True
    except Exception:
        return False


def start_agent(agent: dict):
    port = agent["port"]
    name = agent["name"]
    module = agent["module"]

    if is_running(port):
        print(f"  ✓ {name} already running on port {port}")
        return None

    print(f"  ▶ Starting {name} on port {port}...")

    if sys.platform == "win32":
        proc = subprocess.Popen(
            f'start "{name}" cmd /k uvicorn {module} --port {port} --host 0.0.0.0',
            shell=True,
            cwd=os.getcwd(),
        )
    else:
        proc = subprocess.Popen(
            ["uvicorn", module, "--port", str(port), "--host", "0.0.0.0"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return proc


def wait_for_all(timeout: int = 45):
    print("\nWaiting for all agents to be ready...")
    deadline = time.time() + timeout
    while time.time() < deadline:
        statuses = [(a["name"], a["port"], is_running(a["port"])) for a in AGENTS]
        all_up = all(s[2] for s in statuses)
        if all_up:
            print("\n✅ All agents ready!\n")
            for name, port, _ in statuses:
                print(f"  {name:35} → http://localhost:{port}/docs")
            return True
        time.sleep(2)

    print("\n⚠ Some agents may not have started:")
    for a in AGENTS:
        status = "✓ running" if is_running(a["port"]) else "✗ not ready"
        print(f"  {a['name']:35} port {a['port']}: {status}")
    return False


if __name__ == "__main__":
    print("=" * 55)
    print("  Founder Intelligence System — Starting All Agents")
    print("=" * 55 + "\n")

    for agent in AGENTS:
        start_agent(agent)
        time.sleep(0.5)  # slight delay between starts

    wait_for_all()

    print("\nPipeline Orchestrator: http://localhost:8000/docs")
    print("Press Ctrl+C to stop this script (agents keep running in their windows)\n")
