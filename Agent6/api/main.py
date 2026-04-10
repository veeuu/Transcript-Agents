"""
Product Brief API — Agent 6
Converts insights + problems + internal notes into buildable product feature briefs.
"""

import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional, List

from brief_generator import generate_briefs

app = FastAPI(
    title="Product Brief API",
    description=(
        "Agent 6: Converts insights (Agent 5) + problems (Agent 4) + internal notes (Agent 1) "
        "into clear, buildable product feature briefs with user flows and expected impact."
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

class BriefRequest(BaseModel):
    agent5_data: Any
    agent4_data: Optional[Any] = None
    agent1_data: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "example": {
                "agent5_data": {"insights": [{"insight": "...", "priority": "High"}]},
                "agent4_data": {"problems": [{"problem": "App crashes during peak hours"}]},
                "agent1_data": None
            }
        }


class FileBriefRequest(BaseModel):
    agent5_file: str = "input_Agent3.json"
    agent4_file: Optional[str] = "input_Agent2.json"
    agent1_file: Optional[str] = "input_Agent1.json"

    class Config:
        json_schema_extra = {
            "example": {
                "agent5_file": "input_Agent3.json",
                "agent4_file": "input_Agent2.json",
                "agent1_file": "input_Agent1.json"
            }
        }


class FeatureBrief(BaseModel):
    feature_name: Optional[str] = None
    problem: Optional[str] = None
    why_it_matters: Optional[str] = None
    solution: Optional[str] = None
    user_flow: Optional[List[str]] = None
    expected_impact: Optional[str] = None
    priority: Optional[str] = None
    effort: Optional[str] = None
    target_user: Optional[str] = None


class BriefResponse(BaseModel):
    total_features: int
    features: List[FeatureBrief]


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
        decoder = json.JSONDecoder()
        objects, idx = [], 0
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


@app.post("/briefs/generate", response_model=BriefResponse, tags=["Briefs"])
def generate(req: BriefRequest):
    """
    Generate product feature briefs from Agent 5 insights + Agent 4 problems + Agent 1 notes.
    Pass data directly as JSON.
    """
    try:
        features = generate_briefs(req.agent5_data, req.agent4_data, req.agent1_data)
        return {"total_features": len(features), "features": features}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/briefs/from-files", response_model=BriefResponse, tags=["Briefs"])
def generate_from_files(req: FileBriefRequest):
    """
    Load Agent 5, 4, and 1 outputs from local files and generate product briefs.

    Defaults:
    - agent5_file: input_Agent3.json  (Agent 5 output)
    - agent4_file: input_Agent2.json  (Agent 4 output)
    - agent1_file: input_Agent1.json  (Agent 1 output)
    """
    try:
        agent5_data = _load_file(req.agent5_file)
        agent4_data = _load_file(req.agent4_file) if req.agent4_file else None
        agent1_data = _load_file(req.agent1_file) if req.agent1_file else None
        features = generate_briefs(agent5_data, agent4_data, agent1_data)
        return {"total_features": len(features), "features": features}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
