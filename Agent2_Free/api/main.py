"""
Competitor Research API (Free Version)
FastAPI + Swagger UI — no API keys required
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from researcher import research_competitor, HF_MODEL

app = FastAPI(
    title="Competitor Research API (Free)",
    description=(
        "Agent 2 Free: Researches competitors using DuckDuckGo (no key) + "
        "local Ollama LLM (no key). Same output as the paid version."
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

class CompetitorRequest(BaseModel):
    company_name: str
    website: str

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "Stockgro",
                "website": "https://stockgro.com"
            }
        }


class CompetitorResponse(BaseModel):
    company: str
    website: str
    year_founded: Optional[str] = None
    founders: Optional[List[str]] = None
    headquarters: Optional[str] = None
    platforms: Optional[str] = None
    funding_raised: Optional[str] = None
    number_of_users: Optional[str] = None
    annual_revenue: Optional[str] = None
    key_positioning: Optional[str] = None
    revenue_model: Optional[str] = None
    differentiators: Optional[List[str]] = None
    user_complaints: Optional[List[str]] = None
    strategic_moves: Optional[List[str]] = None
    new_features: Optional[List[str]] = None


class BulkRequest(BaseModel):
    competitors: List[CompetitorRequest]

    class Config:
        json_schema_extra = {
            "example": {
                "competitors": [
                    {"company_name": "Liquide", "website": "https://liquide.life"},
                    {"company_name": "StockEdge", "website": "https://stockedge.com"},
                    {"company_name": "Univest", "website": "https://univest.in"},
                ]
            }
        }


class HealthResponse(BaseModel):
    status: str
    hf_model: str
    hf_token_set: bool


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Check API health and Ollama config."""
    return {
        "status": "ok",
        "hf_model": HF_MODEL,
        "hf_token_set": bool(os.environ.get("HF_TOKEN", "")),
    }


@app.post("/competitor/research", response_model=CompetitorResponse, tags=["Research"])
def research_single(req: CompetitorRequest):
    """
    Research a single competitor — no API keys needed.

    Uses DuckDuckGo for real-time search and a local Ollama model for analysis.
    Returns the same structured intelligence as the paid version.
    """
    try:
        return research_competitor(req.company_name, req.website)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/competitor/bulk", tags=["Research"])
def research_bulk(req: BulkRequest):
    """Research multiple competitors in one call."""
    results, errors = [], []
    for comp in req.competitors:
        try:
            results.append(research_competitor(comp.company_name, comp.website))
        except Exception as e:
            errors.append({"company": comp.company_name, "error": str(e)})
    return {"results": results, "errors": errors, "total": len(results)}


@app.get("/competitor/presets", tags=["Research"])
def get_presets():
    """Returns the pre-configured list of 6 key competitors."""
    return {
        "competitors": [
            {"company_name": "Liquide", "website": "https://liquide.life"},
            {"company_name": "Stockgro", "website": "https://stockgro.com"},
            {"company_name": "StockEdge", "website": "https://stockedge.com"},
            {"company_name": "Univest", "website": "https://univest.in"},
            {"company_name": "Trackk", "website": "https://trackk.in"},
            {"company_name": "Value Research", "website": "https://valueresearchstocks.com"},
        ]
    }
