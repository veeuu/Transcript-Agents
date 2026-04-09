"""
Competitor Research API
FastAPI + Swagger UI
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import Optional, List

from researcher import research_competitor

app = FastAPI(
    title="Competitor Research API",
    description=(
        "Agent 2: Given a company name and website, automatically researches "
        "and returns structured competitive intelligence including founders, funding, "
        "users, revenue, positioning, complaints, and strategic moves."
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


# â”€â”€ Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    serpapi_key_set: bool
    gemini_key_set: bool


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health():
    """Check API health and whether API keys are configured."""
    return {
        "status": "ok",
        "serpapi_key_set": bool(os.environ.get("SERPAPI_KEY", "0ce8a0102165979f7a84be8259503f63c3bf95698e13089cdee04f25db707082")),
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY", "AIzaSyDSGDny-k99pLQB3xonYbiG1A-M9-1NPao")),
    }


@app.post("/competitor/research", response_model=CompetitorResponse, tags=["Research"])
def research_single(req: CompetitorRequest):
    """
    Research a single competitor.

    Gathers the following from Google Search + website scraping + Gemini analysis:
    - Year founded, Founders, HQ
    - Platform availability (Web / Mobile / Both)
    - Funding raised, Number of users, Annual revenue
    - Key positioning & messaging (from website)
    - Revenue model / pricing (from website)
    - Differentiators & what users like
    - User complaints (from Google, Reddit, Play Store, App Store)
    - Strategic moves (partnerships, expansions)
    - New features launched

    **Note:** Set SERPAPI_KEY env var for Google Search results.
    Without it, only website scraping + Gemini analysis runs.
    """
    try:
        return research_competitor(req.company_name, req.website)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/competitor/bulk", tags=["Research"])
def research_bulk(req: BulkRequest):
    """
    Research multiple competitors in one call.
    Returns a list of competitive intelligence profiles.

    Pre-loaded example includes the 6 key competitors:
    Liquide, Stockgro, StockEdge, Univest, Trackk, ValueResearch
    """
    results = []
    errors = []
    for comp in req.competitors:
        try:
            data = research_competitor(comp.company_name, comp.website)
            results.append(data)
        except Exception as e:
            errors.append({"company": comp.company_name, "error": str(e)})

    return {"results": results, "errors": errors, "total": len(results)}


@app.get("/competitor/presets", tags=["Research"])
def get_presets():
    """
    Returns the pre-configured list of 6 key competitors to track.
    Use these directly with /competitor/bulk.
    """
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
