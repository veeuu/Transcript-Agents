"""
YouTube Analysis API (Agent 3)
Analyze a single video or an entire channel — no YouTube API key needed.
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from analyzer import analyze_video, analyze_channel

app = FastAPI(
    title="YouTube Analysis API",
    description="Agent 3: Deep analysis of YouTube videos and channels using yt-dlp + HuggingFace AI.",
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

class VideoRequest(BaseModel):
    url: str

    class Config:
        json_schema_extra = {"example": {"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}}


class ChannelRequest(BaseModel):
    url: str
    max_videos: int = 10

    class Config:
        json_schema_extra = {
            "example": {
                "url": "https://www.youtube.com/@mkbhd",
                "max_videos": 10,
            }
        }


class VideoAnalysis(BaseModel):
    video_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    channel: Optional[str] = None
    upload_date: Optional[str] = None
    duration: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    thumbnail: Optional[str] = None
    tags: Optional[List[str]] = None
    summary: Optional[str] = None
    main_topics: Optional[List[str]] = None
    sentiment: Optional[str] = None
    target_audience: Optional[str] = None
    key_insights: Optional[List[str]] = None
    content_type: Optional[str] = None
    call_to_action: Optional[str] = None
    transcript_available: Optional[bool] = None


class PerVideoSummary(BaseModel):
    video_id: Optional[str] = None
    url: Optional[str] = None
    title: Optional[str] = None
    upload_date: Optional[str] = None
    duration: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    summary: Optional[str] = None
    main_topics: Optional[List[str]] = None
    sentiment: Optional[str] = None
    content_type: Optional[str] = None


class ChannelAnalysis(BaseModel):
    channel: Optional[str] = None
    channel_url: Optional[str] = None
    videos_analyzed: Optional[int] = None
    date_range: Optional[dict] = None
    channel_summary: Optional[str] = None
    content_themes: Optional[List[str]] = None
    posting_pattern: Optional[str] = None
    audience_type: Optional[str] = None
    content_style: Optional[str] = None
    top_performing_topics: Optional[List[str]] = None
    videos: Optional[List[PerVideoSummary]] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"])
def health():
    return {"status": "ok"}


@app.post("/analyze/video", response_model=VideoAnalysis, tags=["Analysis"])
def video_analysis(req: VideoRequest):
    """
    Analyze a single YouTube video.

    Returns: title, channel, date, duration, views, likes, comments,
    AI-generated summary, main topics, sentiment, key insights, content type.
    """
    try:
        return analyze_video(req.url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/channel", response_model=ChannelAnalysis, tags=["Analysis"])
def channel_analysis(req: ChannelRequest):
    """
    Analyze a YouTube channel.

    Returns: channel overview, content themes, posting pattern, audience type,
    and per-video breakdown for the most recent N videos (default 10, max 20).
    """
    try:
        return analyze_channel(req.url, max_videos=min(req.max_videos, 20))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
