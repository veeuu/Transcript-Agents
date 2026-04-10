"""
YouTube Analysis Agent (Agent 3)
- Single video: transcript, summary, topics, sentiment, key insights
- Channel: all videos with per-video analysis, posting patterns, content themes
No YouTube API key needed — uses yt-dlp + youtube-transcript-api + Gemini
"""

import os
import re
import json
from dotenv import load_dotenv
from yt_dlp import YoutubeDL
from youtube_transcript_api import YouTubeTranscriptApi
import google.generativeai as genai

load_dotenv()

GEMINI_API_KEY = os.environ.get("AGENT2_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")


# ── LLM helper ────────────────────────────────────────────────────────────────

def _ask(prompt: str) -> str:
    try:
        return _model.generate_content(prompt).text.strip()
    except Exception as e:
        print(f"[GEMINI ERROR] {e}")
        return ""


def _ask_json(prompt: str) -> dict | list:
    raw = _ask(prompt)
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip().lstrip("json").strip()
            if part.startswith("{") or part.startswith("["):
                raw = part
                break
    raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ── yt-dlp helpers ────────────────────────────────────────────────────────────

def _ydl_opts(quiet=True):
    return {
        "quiet": quiet,
        "no_warnings": True,
        "extract_flat": False,
        "skip_download": True,
    }


def _get_video_meta(video_url: str) -> dict:
    with YoutubeDL(_ydl_opts()) as ydl:
        info = ydl.extract_info(video_url, download=False)
    return info


def _get_channel_videos(channel_url: str, max_videos: int = 20) -> list[dict]:
    opts = {
        **_ydl_opts(),
        "extract_flat": True,
        "playlistend": max_videos,
    }
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
    entries = info.get("entries", [])
    return entries[:max_videos]


def _get_transcript(video_id: str, max_chars: int = 4000) -> str:
    try:
        segments = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join(s["text"] for s in segments)
        return text[:max_chars]
    except Exception:
        return ""


def _extract_video_id(url: str) -> str:
    patterns = [
        r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})",
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return ""


# ── Single video analysis ─────────────────────────────────────────────────────

def analyze_video(video_url: str) -> dict:
    print(f"[VIDEO] fetching metadata: {video_url}")
    info = _get_video_meta(video_url)

    video_id = info.get("id", _extract_video_id(video_url))
    title = info.get("title", "")
    channel = info.get("channel", info.get("uploader", ""))
    upload_date = info.get("upload_date", "")  # YYYYMMDD
    duration_secs = info.get("duration", 0)
    view_count = info.get("view_count")
    like_count = info.get("like_count")
    comment_count = info.get("comment_count")
    description = (info.get("description") or "")[:1000]
    tags = info.get("tags", [])[:15]
    thumbnail = info.get("thumbnail", "")

    # format date
    if upload_date and len(upload_date) == 8:
        upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"

    # duration
    mins, secs = divmod(duration_secs or 0, 60)
    duration_str = f"{mins}m {secs}s"

    print(f"[VIDEO] fetching transcript for {video_id}")
    transcript = _get_transcript(video_id)

    # build context — use transcript if available, else fall back to description + tags
    if transcript:
        context = f"Title: {title}\nDescription: {description}\nTranscript: {transcript}"
        context_note = ""
    else:
        tags_str = ", ".join(tags)
        context = f"Title: {title}\nDescription: {description}\nTags: {tags_str}"
        context_note = "Note: No transcript available. Base analysis on title, description and tags only."

    print("[GEMINI] analyzing video...")
    analysis = _ask_json(f"""Analyze this YouTube video and return a JSON object with these keys:
- "summary": 2-3 sentence summary of what the video is about
- "main_topics": list of main topics covered (max 6)
- "sentiment": overall sentiment — "Positive", "Negative", or "Neutral"
- "target_audience": who this video is aimed at (1 sentence)
- "key_insights": list of 3-5 most important points or takeaways
- "negative_points": list of criticisms, controversies, downsides, or negative aspects mentioned (max 5), or []
- "content_type": e.g. "Tutorial", "Review", "News", "Opinion", "Interview", "Vlog", "Stand-up Comedy", etc.
- "call_to_action": what the creator asks viewers to do, or null

{context_note}
Return ONLY valid JSON, no explanation.

Video cxt:
{context[:4000]}""")

    return {
        "video_id": video_id,
        "url": video_url,
        "title": title,
        "channel": channel,
        "upload_date": upload_date,
        "duration": duration_str,
        "view_count": view_count,
        "like_count": like_count,
        "comment_count": comment_count,
        "thumbnail": thumbnail,
        "tags": tags,
        "summary": analysis.get("summary"),
        "main_topics": analysis.get("main_topics", []),
        "sentiment": analysis.get("sentiment"),
        "target_audience": analysis.get("target_audience"),
        "key_insights": analysis.get("key_insights", []),
        "negative_points": analysis.get("negative_points", []),
        "content_type": analysis.get("content_type"),
        "call_to_action": analysis.get("call_to_action"),
        "transcript_available": bool(transcript),
    }


# ── Channel analysis ──────────────────────────────────────────────────────────

def analyze_channel(channel_url: str, max_videos: int = 20) -> dict:
    print(f"[CHANNEL] fetching video list: {channel_url}")
    entries = _get_channel_videos(channel_url, max_videos)

    if not entries:
        return {"error": "No videos found for this channel."}

    # fetch full meta for each video
    videos_data = []
    for entry in entries:
        vid_url = entry.get("url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}"
        vid_id = entry.get("id", "")
        title = entry.get("title", "")
        upload_date = entry.get("upload_date", "") or ""
        if upload_date and len(upload_date) == 8:
            upload_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:]}"
        duration_secs = entry.get("duration") or 0
        mins, secs = divmod(duration_secs, 60)

        print(f"[CHANNEL] analyzing: {title[:60]}")
        transcript = _get_transcript(vid_id)
        context = f"Title: {title}\nTranscript excerpt: {transcript[:1500]}" if transcript else f"Title: {title}\nDescription: {(entry.get('description') or '')[:500]}"

        per_video = _ask_json(f"""Analyze this YouTube video briefly. Return JSON with:
- "summary": 1-2 sentence summary
- "main_topics": list of up to 4 topics
- "sentiment": "Positive", "Negative", or "Neutral"
- "content_type": e.g. Tutorial, Review, News, Opinion, Vlog, etc.

Return ONLY valid JSON.

{context}""")

        videos_data.append({
            "video_id": vid_id,
            "url": vid_url,
            "title": title,
            "upload_date": upload_date,
            "duration": f"{mins}m {secs}s",
            "view_count": entry.get("view_count"),
            "like_count": entry.get("like_count"),
            "summary": per_video.get("summary"),
            "main_topics": per_video.get("main_topics", []),
            "sentiment": per_video.get("sentiment"),
            "content_type": per_video.get("content_type"),
        })

    # channel-level analysis
    channel_name = entries[0].get("channel") or entries[0].get("uploader") or channel_url
    all_titles = "\n".join(f"- {v['title']} ({v['upload_date']})" for v in videos_data)

    print("[GEMINI] generating channel-level analysis...")
    channel_analysis = _ask_json(f"""Analyze this YouTube channel based on its recent videos. Return JSON with:
- "channel_summary": 2-3 sentence overview of what this channel is about
- "content_themes": list of recurring themes or topics across videos
- "posting_pattern": description of how frequently they post
- "audience_type": who the channel targets
- "content_style": overall style (educational, entertainment, news, etc.)
- "top_performing_topics": topics that appear most often

Return ONLY valid JSON.

Channel: {channel_name}
Recent videos:
{all_titles}""")

    # posting frequency
    dates = [v["upload_date"] for v in videos_data if v["upload_date"]]
    dates_sorted = sorted(dates, reverse=True)

    return {
        "channel": channel_name,
        "channel_url": channel_url,
        "videos_analyzed": len(videos_data),
        "date_range": {
            "latest": dates_sorted[0] if dates_sorted else None,
            "oldest": dates_sorted[-1] if dates_sorted else None,
        },
        "channel_summary": channel_analysis.get("channel_summary"),
        "content_themes": channel_analysis.get("content_themes", []),
        "posting_pattern": channel_analysis.get("posting_pattern"),
        "audience_type": channel_analysis.get("audience_type"),
        "content_style": channel_analysis.get("content_style"),
        "top_performing_topics": channel_analysis.get("top_performing_topics", []),
        "videos": videos_data,
    }
