"""
Research Synthesis API — Agent 5
Converts problems + competitor signals + internal notes into product insights.
"""

import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional, List

from synthesizer import synthesize

app = FastAPI(
    title="Research Synthesis API",
    description=(
        "Agent 5: Synthesizes structured problems (Agent 4) + internal notes (Agent 1) "
        "+ competitor signals into high-level product insights with root causes, "
        "implications, hypotheses, and recommended actions."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Models ────────────────────────────────────────────────────────────────────

class SynthesisRequest(BaseModel):
    agent1_data: Any  # transcript analysis output from Agent 1
    agent4_data: Any  # structured problems output from Agent 4
    competitor_data: Optional[Any] = None  # optional competitor research from Agent 2

    class Config:
        json_schema_extra = {
            "example": {
                "agent1_data": {"analysis": {"summary": "...", "problems_identified": ["..."]}},
                "agent4_data": {"problems": [{"problem": "App crashes during peak hours", "frequency": "High"}]},
                "competitor_data": {"company": "Zerodha", "user_complaints": ["slow charts"]}
            }
        }


class FileSynthesisRequest(BaseModel):
    agent1_file: str = "input_Agent1.json"
    agent4_file: str = "input_Agent2.json"
    competitor_file: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "agent1_file": "input_Agent1.json",
                "agent4_file": "input_Agent2.json",
                "competitor_file": None
            }
        }


class InsightItem(BaseModel):
    insight: Optional[str] = None
    supporting_problems: Optional[List[str]] = None
    evidence: Optional[List[str]] = None
    implication: Optional[str] = None
    priority: Optional[str] = None
    hypothesis: Optional[str] = None
    recommended_action: Optional[str] = None


class SynthesisResponse(BaseModel):
    total_insights: int
    insights: List[InsightItem]


# ── File loader ───────────────────────────────────────────────────────────────

def _load_file(path: str) -> Any:
    workspace_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if not os.path.isabs(path):
        path = os.path.join(workspace_root, path)
    path = os.path.normpath(path)
    with open(path, encoding="utf-8") as f:
        content = f.read().strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        # handle concatenated JSON objects
        decoder = json.JSONDecoder()
        objects = []
        idx = 0
        while idx < len(content):
            chunk = content[idx:].lstrip()
            if not chunk:
                break
            idx += len(content[idx:]) - len(chunk)
            try:
                obj, end = decoder.raw_decode(chunk)
                objects.append(obj)
                idx += end
            except json.JSONDecodeError:
                idx += 1
        return objects if len(objects) > 1 else (objects[0] if objects else {})


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.post("/synthesis/run", response_model=SynthesisResponse, tags=["Synthesis"])
def run_synthesis(req: SynthesisRequest):
    """
    Synthesize insights from Agent 1 + Agent 4 + optional competitor data.

    Pass data directly as JSON objects.
    Returns high-level product insights with root causes, implications,
    testable hypotheses, and recommended actions.
    """
    try:
        insights = synthesize(req.agent1_data, req.agent4_data, req.competitor_data)
        return {"total_insights": len(insights), "insights": insights}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/synthesis/from-files", response_model=SynthesisResponse, tags=["Synthesis"])
def run_synthesis_from_files(req: FileSynthesisRequest):
    """
    Load Agent 1 and Agent 4 outputs from local files and synthesize insights.

    Defaults:
    - agent1_file: input_Agent1.json
    - agent4_file: input_Agent2.json (Agent 4 output)
    - competitor_file: optional
    """
    try:
        agent1_data = _load_file(req.agent1_file)
        agent4_data = _load_file(req.agent4_file)
        competitor_data = _load_file(req.competitor_file) if req.competitor_file else None
        insights = synthesize(agent1_data, agent4_data, competitor_data)
        return {"total_insights": len(insights), "insights": insights}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
