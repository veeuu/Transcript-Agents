"""
Insight Extraction API — Agent 4
Converts raw signals from Agents 1/2/3 into structured user problems.
"""

import os
import sys
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Any, Optional, List

from extractor import extract_insights

app = FastAPI(
    title="Insight Extraction API",
    description=(
        "Agent 4: Takes combined output from Agents 1, 2, 3 and extracts "
        "structured, validated user problems with evidence, frequency, user type, and source mix."
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

class InsightRequest(BaseModel):
    """
    Pass the combined output from Agents 1/2/3 as a JSON array or object.
    You can mix multiple agent outputs in a single array.
    """
    signals: Any  # list or dict — accepts any agent output shape

    class Config:
        json_schema_extra = {
            "example": {
                "signals": [
                    {"company": "Groww", "user_complaints": ["app crashes", "slow withdrawals"]},
                    {"post_url": "https://reddit.com/...", "negative_points": ["hard to use for beginners"]},
                ]
            }
        }


class InsightItem(BaseModel):
    problem: Optional[str] = None
    evidence: Optional[List[str]] = None
    frequency: Optional[str] = None
    user_type: Optional[str] = None
    source_mix: Optional[List[str]] = None
    positive_points: Optional[List[str]] = None
    negative_points: Optional[List[str]] = None


class InsightResponse(BaseModel):
    total_problems: int
    problems: List[InsightItem]


class FileRequest(BaseModel):
    file_path: str

    class Config:
        json_schema_extra = {
            "example": {"file_path": "input.json"}
        }


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.post("/insights/extract", response_model=InsightResponse, tags=["Insights"])
def extract(req: InsightRequest):
    """
    Extract structured user problems from combined agent signals.

    Pass the output of Agents 1, 2, 3 as a JSON array in the `signals` field.
    Returns a list of validated problems with evidence, frequency, user type, and source mix.
    """
    try:
        problems = extract_insights(req.signals)
        return {"total_problems": len(problems), "problems": problems}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/insights/from-file", response_model=InsightResponse, tags=["Insights"])
def extract_from_file(req: FileRequest):
    """
    Load signals from a local JSON file and extract insights.
    Useful for processing the combined input.json directly.

    The file can contain a JSON array, a single object, or multiple
    concatenated JSON objects (as produced by saving agent outputs).
    """
    try:
        path = req.file_path
        if not os.path.isabs(path):
            # resolve relative to workspace root (two levels up from Agent4/api/)
            workspace_root = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
            path = os.path.join(workspace_root, path)
        path = os.path.normpath(path)

        with open(path, encoding="utf-8") as f:
            content = f.read().strip()

        # handle concatenated JSON objects (not a valid JSON array)
        # split on top-level object boundaries
        objects = []
        try:
            parsed = json.loads(content)
            objects = parsed if isinstance(parsed, list) else [parsed]
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
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
                    idx += 1  # skip bad char and keep trying

        if not objects:
            raise ValueError("No valid JSON objects found in file")

        problems = extract_insights(objects)
        return {"total_problems": len(problems), "problems": problems}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {req.file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
