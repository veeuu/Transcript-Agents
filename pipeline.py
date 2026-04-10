"""
End-to-End Pipeline Orchestrator
Runs all agents in sequence and passes outputs as inputs to the next stage.

Flow:
  Agent 1  (Transcript)     → internal notes
  Agent 2  (Competitor)     → competitor signals
  Agent 3  (YouTube/Reddit) → social signals
  Agent 4  (Insight)        → structured problems
  Agent 5  (Synthesis)      → product insights
  Agent 6  (Brief)          → feature briefs
  Agent 7  (Copilot)        → query interface (loaded, ready to answer)
"""

import os
import sys
import json
import time
import subprocess
import requests
from dotenv import load_dotenv

load_dotenv()

# ── Agent API base URLs ───────────────────────────────────────────────────────
AGENT1_URL  = os.environ.get("AGENT1_URL",  "http://localhost:8004")
AGENT2_URL  = os.environ.get("AGENT2_URL",  "http://localhost:8001")
AGENT3_URL  = os.environ.get("AGENT3_URL",  "http://localhost:8003")
AGENT4_URL  = os.environ.get("AGENT4_URL",  "http://localhost:8005")
AGENT5_URL  = os.environ.get("AGENT5_URL",  "http://localhost:8006")
AGENT6_URL  = os.environ.get("AGENT6_URL",  "http://localhost:8007")
AGENT7_URL  = os.environ.get("AGENT7_URL",  "http://localhost:8008")

# ── Agent server definitions ──────────────────────────────────────────────────
AGENT_SERVERS = [
    {"name": "Agent1",  "module": "Agent1.api.main:app",       "port": 8004, "url": AGENT1_URL},
    {"name": "Agent2",  "module": "Agent2_Free.api.main:app",   "port": 8001, "url": AGENT2_URL},
    {"name": "Agent3",  "module": "Agent3_Free.api.main:app",   "port": 8003, "url": AGENT3_URL},
    {"name": "Agent4",  "module": "Agent4.api.main:app",        "port": 8005, "url": AGENT4_URL},
    {"name": "Agent5",  "module": "Agent5.api.main:app",        "port": 8006, "url": AGENT5_URL},
    {"name": "Agent6",  "module": "Agent6.api.main:app",        "port": 8007, "url": AGENT6_URL},
    {"name": "Agent7",  "module": "Agent7.api.main:app",        "port": 8008, "url": AGENT7_URL},
]

_agent_processes = {}  # track spawned subprocesses


def _is_running(url: str) -> bool:
    try:
        requests.get(f"{url}/health", timeout=3)
        return True
    except Exception:
        return False


def _start_agent(agent: dict):
    name = agent["name"]
    port = agent["port"]
    module = agent["module"]
    url = agent["url"]

    if _is_running(url):
        print(f"[STARTUP] {name} already running on port {port}")
        return

    print(f"[STARTUP] Starting {name} on port {port}...")
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", module, "--port", str(port), "--host", "0.0.0.0"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _agent_processes[name] = proc


def ensure_agents_running(agents: list = None):
    """Start any agent servers that aren't already running."""
    targets = agents or AGENT_SERVERS
    # start all in parallel
    for agent in targets:
        _start_agent(agent)

    # wait for all to be healthy (up to 30s)
    print("[STARTUP] Waiting for agents to be ready...")
    deadline = time.time() + 30
    while time.time() < deadline:
        all_up = all(_is_running(a["url"]) for a in targets)
        if all_up:
            print("[STARTUP] ✅ All agents ready")
            return
        time.sleep(2)

    # report which ones are still down
    for a in targets:
        status = "✓" if _is_running(a["url"]) else "✗ NOT READY"
        print(f"[STARTUP] {a['name']} port {a['port']}: {status}")

TIMEOUT = 300  # seconds per step


def _post(url: str, payload: dict, label: str) -> dict:
    print(f"\n[PIPELINE] ▶ {label}")
    try:
        resp = requests.post(url, json=payload, timeout=TIMEOUT)
        resp.raise_for_status()
        result = resp.json()
        print(f"[PIPELINE] ✓ {label} done")
        return result
    except requests.exceptions.ConnectionError:
        print(f"[PIPELINE] ✗ {label} — server not running at {url}, skipping")
        return {}
    except Exception as e:
        print(f"[PIPELINE] ✗ {label} failed: {e}")
        return {}


def _save(data: dict, path: str):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[PIPELINE] saved → {path}")


# ── Pipeline steps ────────────────────────────────────────────────────────────

def run_pipeline(
    transcript_text: str = None,
    competitor_name: str = None,
    competitor_website: str = None,
    youtube_url=None,       # str or list
    reddit_url=None,        # str or list
    app_store_urls=None,    # list of Play/App Store URLs
    competitors=None,       # list of additional competitor names
    questions: list = None,
    save_outputs: bool = True,
    **kwargs,               # absorb extra fields like company_info, twitter_url etc.
) -> dict:
    outputs = {}

    # auto-start any agents that aren't running
    ensure_agents_running()

    # normalize to lists
    youtube_urls = ([youtube_url] if isinstance(youtube_url, str) else youtube_url) or []
    reddit_urls  = ([reddit_url]  if isinstance(reddit_url,  str) else reddit_url)  or []
    app_urls     = app_store_urls or []

    # ── Step 1: Agent 1 — Transcript Analysis ─────────────────────────────────
    agent1_out = {}
    if transcript_text:
        agent1_out = _post(f"{AGENT1_URL}/pipeline/run", {"text": transcript_text}, "Agent 1 — Transcript")
        if save_outputs and agent1_out: _save(agent1_out, "pipeline_agent1.json")
    else:
        print("[PIPELINE] ⚠ No transcript, skipping Agent 1")
    outputs["agent1"] = agent1_out

    # ── Step 2: Agent 2 — Competitor Research ─────────────────────────────────
    agent2_out = {}
    all_competitors = []
    if competitor_name and competitor_website:
        all_competitors.append({"company_name": competitor_name, "website": competitor_website})
    # research additional competitors from the list (best-effort website guess)
    for comp in (competitors or []):
        slug = comp.lower().replace(" ", "")
        all_competitors.append({"company_name": comp, "website": f"https://{slug}.com"})

    if all_competitors:
        if len(all_competitors) == 1:
            agent2_out = _post(f"{AGENT2_URL}/competitor/research", all_competitors[0], f"Agent 2 — {all_competitors[0]['company_name']}")
        else:
            agent2_out = _post(f"{AGENT2_URL}/competitor/bulk", {"competitors": all_competitors}, "Agent 2 — Bulk Competitors")
        if save_outputs and agent2_out: _save(agent2_out, "pipeline_agent2.json")
    else:
        print("[PIPELINE] ⚠ No competitors, skipping Agent 2")
    outputs["agent2"] = agent2_out

    # ── Step 3: Agent 3 — YouTube / Reddit / App Store ────────────────────────
    agent3_outputs = []

    for yt_url in youtube_urls:
        endpoint = "/analyze/channel" if ("/@" in yt_url or "/c/" in yt_url or "/channel/" in yt_url) else "/analyze/video"
        out = _post(f"{AGENT3_URL}{endpoint}", {"url": yt_url}, f"Agent 3 — YouTube {endpoint} ({yt_url[-40:]})")
        if out: agent3_outputs.append(out)

    for rd_url in reddit_urls:
        endpoint = "/analyze/subreddit" if "/comments/" not in rd_url else "/analyze/reddit"
        out = _post(f"{AGENT3_URL}{endpoint}", {"url": rd_url}, f"Agent 3 — Reddit {endpoint} ({rd_url[-40:]})")
        if out: agent3_outputs.append(out)

    for app_url in app_urls:
        out = _post(f"{AGENT3_URL}/analyze/app", {"input": app_url, "store": "auto"}, f"Agent 3 — App ({app_url[-40:]})")
        if out: agent3_outputs.append(out)

    agent3_out = agent3_outputs[0] if len(agent3_outputs) == 1 else {"sources": agent3_outputs} if agent3_outputs else {}
    if save_outputs and agent3_out: _save(agent3_out, "pipeline_agent3.json")
    if not agent3_outputs: print("[PIPELINE] ⚠ No social URLs, skipping Agent 3")
    outputs["agent3"] = agent3_out

    # ── Step 4: Agent 4 — Insight Extraction ──────────────────────────────────
    signals = [s for s in [agent1_out, agent2_out, agent3_out] if s]
    agent4_out = {}
    if signals:
        agent4_out = _post(
            f"{AGENT4_URL}/insights/extract",
            {"signals": signals},
            "Agent 4 — Insight Extraction"
        )
        if save_outputs and agent4_out:
            _save(agent4_out, "pipeline_agent4.json")
    else:
        print("[PIPELINE] ⚠ No signals available, skipping Agent 4")
    outputs["agent4"] = agent4_out

    # ── Step 5: Agent 5 — Research Synthesis ──────────────────────────────────
    agent5_out = {}
    if agent4_out:
        agent5_out = _post(
            f"{AGENT5_URL}/synthesis/run",
            {
                "agent1_data": agent1_out or None,
                "agent4_data": agent4_out,
                "competitor_data": agent2_out or None,
            },
            "Agent 5 — Research Synthesis"
        )
        if save_outputs and agent5_out:
            _save(agent5_out, "pipeline_agent5.json")
    else:
        print("[PIPELINE] ⚠ No problems from Agent 4, skipping Agent 5")
    outputs["agent5"] = agent5_out

    # ── Step 6: Agent 6 — Product Brief ───────────────────────────────────────
    agent6_out = {}
    if agent5_out:
        agent6_out = _post(
            f"{AGENT6_URL}/briefs/generate",
            {
                "agent5_data": agent5_out,
                "agent4_data": agent4_out or None,
                "agent1_data": agent1_out or None,
            },
            "Agent 6 — Product Brief Generation"
        )
        if save_outputs and agent6_out:
            _save(agent6_out, "pipeline_agent6.json")
    else:
        print("[PIPELINE] ⚠ No insights from Agent 5, skipping Agent 6")
    outputs["agent6"] = agent6_out

    # ── Step 7: Agent 7 — Load Copilot Context ────────────────────────────────
    copilot_loaded = False
    if any([agent1_out, agent4_out, agent5_out, agent6_out]):
        load_result = _post(
            f"{AGENT7_URL}/copilot/load-context",
            {
                "agent1_file": None,
                "agent4_file": None,
                "agent5_file": None,
                "agent6_file": None,
            },
            "Agent 7 — Loading Copilot Context"
        )
        # load inline since we have data in memory
        load_result = requests.post(
            f"{AGENT7_URL}/copilot/ask-inline",
            json={
                "question": "Summarize the key findings from this pipeline run in 3 bullet points.",
                "agent1_data": agent1_out or None,
                "agent4_data": agent4_out or None,
                "agent5_data": agent5_out or None,
                "agent6_data": agent6_out or None,
            },
            timeout=TIMEOUT,
        ).json()
        outputs["pipeline_summary"] = load_result
        copilot_loaded = True
        print(f"[PIPELINE] ✓ Copilot ready")

    # ── Answer founder questions + their follow-ups ───────────────────────────
    copilot_answers = []
    inline_payload = {
        "agent1_data": agent1_out or None,
        "agent4_data": agent4_out or None,
        "agent5_data": agent5_out or None,
        "agent6_data": agent6_out or None,
    }

    if questions and copilot_loaded:
        # collect all questions including follow-ups from previous answers
        answered_questions = set()
        queue = list(questions)

        print(f"\n[PIPELINE] ▶ Answering founder questions (with follow-ups)...")
        while queue:
            q = queue.pop(0)
            if q in answered_questions:
                continue
            answered_questions.add(q)

            ans = _post(
                f"{AGENT7_URL}/copilot/ask-inline",
                {"question": q, **inline_payload},
                f"Copilot: {q[:60]}"
            )
            copilot_answers.append({"question": q, **ans})

            # auto-answer follow-up questions suggested by the copilot
            follow_ups = ans.get("follow_up_questions", [])
            for fq in follow_ups:
                if fq and fq not in answered_questions:
                    queue.append(fq)
                    print(f"[PIPELINE] ↳ Follow-up queued: {fq[:70]}")

    outputs["copilot_answers"] = copilot_answers

    if save_outputs:
        _save(outputs, "pipeline_output.json")
        print("\n[PIPELINE] ✅ Full pipeline complete → pipeline_output.json")

    return outputs


# ── FastAPI wrapper ───────────────────────────────────────────────────────────

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(
    title="Pipeline Orchestrator",
    description="Runs the full end-to-end agent pipeline: Ingestion → Insight → Synthesis → Brief → Copilot",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class PipelineRequest(BaseModel):
    transcript_text: Optional[str] = None
    competitor_name: Optional[str] = None
    competitor_website: Optional[str] = None
    youtube_url: Optional[List[str]] = None       # single string or list
    reddit_url: Optional[List[str]] = None         # single string or list
    app_store_urls: Optional[List[str]] = None     # Play Store / App Store URLs
    twitter_url: Optional[str] = None              # reserved for future
    linkedin_url: Optional[str] = None             # reserved for future
    company_info: Optional[dict] = None            # extra context, passed to agents
    competitors: Optional[List[str]] = None        # additional competitors to research
    data_sources: Optional[List[str]] = None       # informational
    analysis_goals: Optional[List[str]] = None     # informational
    questions: Optional[List[str]] = [
        "What are the top 3 user problems?",
        "What should we build next?",
        "What are competitors doing differently?",
    ]
    save_outputs: bool = True

    class Config:
        json_schema_extra = {
            "example": {
                "transcript_text": "Meeting transcript text here...",
                "competitor_name": "Groww",
                "competitor_website": "https://groww.in",
                "youtube_url": "https://www.youtube.com/@GrowwApp",
                "reddit_url": "https://www.reddit.com/r/IndiaInvestments/",
                "questions": [
                    "What are the top 3 user problems?",
                    "What should we build next?",
                    "What are competitors doing differently?",
                ],
                "save_outputs": True,
            }
        }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/pipeline/run")
def run(req: PipelineRequest):
    """
    Run the full end-to-end pipeline.
    Provide any combination of inputs — steps with missing inputs are skipped gracefully.
    """
    try:
        result = run_pipeline(
            transcript_text=req.transcript_text,
            competitor_name=req.competitor_name,
            competitor_website=req.competitor_website,
            youtube_url=req.youtube_url,
            reddit_url=req.reddit_url,
            app_store_urls=req.app_store_urls,
            competitors=req.competitors,
            questions=req.questions,
            save_outputs=req.save_outputs,
        )
        return {
            "status": "complete",
            "steps_run": [k for k, v in result.items() if v and k not in ("copilot_answers", "pipeline_summary")],
            "pipeline_summary": result.get("pipeline_summary"),
            "copilot_answers": result.get("copilot_answers", []),
            "feature_count": result.get("agent6", {}).get("total_features", 0),
            "insight_count": result.get("agent5", {}).get("total_insights", 0),
            "problem_count": result.get("agent4", {}).get("total_problems", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("pipeline:app", host="0.0.0.0", port=8000, reload=True)
