"""
Founder Copilot API — Agent 7
Query interface over all agent outputs for fast founder decision-making.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional, List

from copilot import query, load_context_from_files, build_context

app = FastAPI(
    title="Founder Copilot API",
    description=(
        "Agent 7: Ask any product or strategy question and get a direct answer "
        "with evidence and confidence level, powered by all agent outputs."
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

# cached context — loaded once per session
_cached_context: str = ""
WORKSPACE_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))


# ── Models ────────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    agent1_data: Optional[Any] = None
    agent4_data: Optional[Any] = None
    agent5_data: Optional[Any] = None
    agent6_data: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What are the top 3 user problems this week?",
                "agent4_data": {"problems": [{"problem": "App crashes", "frequency": "High"}]},
            }
        }


class FileQueryRequest(BaseModel):
    question: str
    agent1_file: Optional[str] = "input_Agent1.json"
    agent4_file: Optional[str] = "input_Agent2.json"
    agent5_file: Optional[str] = "input_Agent3.json"
    agent6_file: Optional[str] = "input_Agent4.json"

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What should we build next?",
                "agent1_file": "input_Agent1.json",
                "agent4_file": "input_Agent2.json",
                "agent5_file": "input_Agent3.json",
                "agent6_file": "input_Agent4.json",
            }
        }


class LoadContextRequest(BaseModel):
    agent1_file: Optional[str] = "input_Agent1.json"
    agent4_file: Optional[str] = "input_Agent2.json"
    agent5_file: Optional[str] = "input_Agent3.json"
    agent6_file: Optional[str] = "input_Agent4.json"


class CopilotResponse(BaseModel):
    question: str
    answer: Optional[str] = None
    evidence: Optional[List[str]] = None
    confidence: Optional[str] = None
    follow_up_questions: Optional[List[str]] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok", "context_loaded": bool(_cached_context)}


@app.post("/copilot/load-context", tags=["Setup"])
def load_context(req: LoadContextRequest):
    """
    Pre-load all agent output files into memory.
    Call this once before querying to avoid reloading files on every question.
    """
    global _cached_context
    try:
        _cached_context = load_context_from_files(
            agent1_file=req.agent1_file,
            agent4_file=req.agent4_file,
            agent5_file=req.agent5_file,
            agent6_file=req.agent6_file,
            workspace_root=WORKSPACE_ROOT,
        )
        return {"status": "context loaded", "context_length": len(_cached_context)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/copilot/ask", response_model=CopilotResponse, tags=["Copilot"])
def ask(req: FileQueryRequest):
    """
    Ask any founder question using pre-loaded or file-based context.

    Example questions:
    - "What are the top 3 user problems this week?"
    - "What insights are emerging?"
    - "What should we build next?"
    - "What are competitors doing differently?"
    - "What is the highest priority feature to ship?"
    - "What are users most frustrated about?"
    """
    global _cached_context
    try:
        # use cached context if available, else load fresh
        ctx = _cached_context
        if not ctx:
            ctx = load_context_from_files(
                agent1_file=req.agent1_file,
                agent4_file=req.agent4_file,
                agent5_file=req.agent5_file,
                agent6_file=req.agent6_file,
                workspace_root=WORKSPACE_ROOT,
            )

        result = query(req.question, ctx)
        return {
            "question": req.question,
            "answer": result.get("answer"),
            "evidence": result.get("evidence", []),
            "confidence": result.get("confidence"),
            "follow_up_questions": result.get("follow_up_questions", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/copilot/ask-inline", response_model=CopilotResponse, tags=["Copilot"])
def ask_inline(req: QueryRequest):
    """
    Ask a question passing agent data directly as JSON (no files needed).
    """
    try:
        ctx = build_context(
            agent1=req.agent1_data,
            agent4=req.agent4_data,
            agent5=req.agent5_data,
            agent6=req.agent6_data,
        )
        result = query(req.question, ctx)
        return {
            "question": req.question,
            "answer": result.get("answer"),
            "evidence": result.get("evidence", []),
            "confidence": result.get("confidence"),
            "follow_up_questions": result.get("follow_up_questions", []),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
