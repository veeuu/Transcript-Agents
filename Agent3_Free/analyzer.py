"""
YouTube Analysis Agent - Free Version (Agent 3 Free)
- Apify YouTube scraper for video/channel data (free tier)
- HuggingFace Qwen2.5-72B for analysis (free token)
- No Gemini, no YouTube API key needed
"""

import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

APIFY_TOKEN = os.environ.get("APIFY_TOKEN", "")
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"

APIFY_BASE = "https://api.apify.com/v2"


# ── HuggingFace LLM ───────────────────────────────────────────────────────────

def _ask_json(prompt: str) -> dict | list:
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(api_key=HF_TOKEN)
        resp = client.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("{") or part.startswith("["):
                    raw = part
                    break
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[HF ERROR] {e}")
        return {}


# ── Apify helpers ─────────────────────────────────────────────────────────────

def _apify_run(actor_id: str, input_data: dict, timeout: int = 120) -> list:
    """Run an Apify actor and return the dataset items."""
    # start run
    run_resp = requests.post(
        f"{APIFY_BASE}/acts/{actor_id}/runs",
        params={"token": APIFY_TOKEN},
        json=input_data,
        timeout=30,
    )
    run_resp.raise_for_status()
    run_id = run_resp.json()["data"]["id"]
    print(f"[APIFY] started run {run_id} for {actor_id}")

    # poll until finished
    deadline = time.time() + timeout
    while time.time() < deadline:
        status_resp = requests.get(
            f"{APIFY_BASE}/actor-runs/{run_id}",
            params={"token": APIFY_TOKEN},
            timeout=15,
        )
        status = status_resp.json()["data"]["status"]
        print(f"[APIFY] status: {status}")
        if status == "SUCCEEDED":
            break
        if status in ("FAILED", "ABORTED", "TIMED-OUT"):
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
        time.sleep(5)
    else:
        raise TimeoutError(f"Apify run {run_id} did not finish in {timeout}s")

    # fetch dataset
    dataset_id = status_resp.json()["data"]["defaultDatasetId"]
    items_resp = requests.get(
        f"{APIFY_BASE}/datasets/{dataset_id}/items",
        params={"token": APIFY_TOKEN, "format": "json"},
        timeout=30,
    )
    return items_resp.json()


def _format_duration(seconds) -> str:
    if not seconds:
        return "0m 0s"
    # handle string formats like "4:32" or "1:23:45"
    if isinstance(seconds, str):
        parts = seconds.split(":")
        try:
            if len(parts) == 3:
                seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                seconds = int(parts[0]) * 60 + int(parts[1])
            else:
                seconds = int(seconds)
        except ValueError:
            return seconds  # return as-is if unparseable
    mins, secs = divmod(int(seconds), 60)
    return f"{mins}m {secs}s"


def _fmt_date(raw: str) -> str:
    """Normalize date to YYYY-MM-DD."""
    if not raw:
        return None
    raw = raw[:10]  # handles ISO format
    return raw


# ── Single video analysis ─────────────────────────────────────────────────────

def analyze_video(video_url: str) -> dict:
    print(f"[APIFY] scraping video: {video_url}")
    items = _apify_run(
        "streamers~youtube-scraper",
        {
            "startUrls": [{"url": video_url}],
            "maxResults": 1,
            "maxResultsShorts": 0,
            "downloadSubtitles": True,
        },
    )

    if not items:
        raise ValueError("No data returned from Apify for this video URL.")

    v = items[0]
    title = v.get("title", "")
    channel = v.get("channelName", "")
    description = (v.get("description") or "")[:1000]
    tags = v.get("hashtags", [])[:15] or v.get("keywords", [])[:15]
    transcript_parts = v.get("subtitles", []) or []
    transcript = " ".join(s.get("text", "") for s in transcript_parts)[:4000]

    context = f"Title: {title}\nChannel: {channel}\nDescription: {description}"
    if transcript:
        context += f"\nTranscript: {transcript}"
    else:
        context += f"\nTags: {', '.join(tags)}"

    print("[HF] analyzing video...")
    analysis = _ask_json(f"""Analyze this YouTube video and return a JSON object with these exact keys:
- "summary": 2-3 sentence summary
- "main_topics": list of main topics (max 6)
- "sentiment": "Positive", "Negative", or "Neutral"
- "target_audience": who this is aimed at (1 sentence)
- "key_insights": list of 3-5 key takeaways
- "content_type": e.g. Tutorial, Review, News, Opinion, Vlog, Stand-up Comedy, etc.
- "call_to_action": what the creator asks viewers to do, or null

Return ONLY valid JSON, no explanation.

Context:
{context[:4000]}""")

    return {
        "video_id": v.get("id", ""),
        "url": v.get("url", video_url),
        "title": title,
        "channel": channel,
        "upload_date": _fmt_date(v.get("date", "")),
        "duration": _format_duration(v.get("duration")),
        "view_count": v.get("viewCount"),
        "like_count": v.get("likes"),
        "comment_count": v.get("commentsCount"),
        "thumbnail": v.get("thumbnailUrl", ""),
        "tags": tags,
        "summary": analysis.get("summary"),
        "main_topics": analysis.get("main_topics", []),
        "sentiment": analysis.get("sentiment"),
        "target_audience": analysis.get("target_audience"),
        "key_insights": analysis.get("key_insights", []),
        "content_type": analysis.get("content_type"),
        "call_to_action": analysis.get("call_to_action"),
        "transcript_available": bool(transcript),
    }


# ── Channel analysis ──────────────────────────────────────────────────────────

def analyze_channel(channel_url: str, max_videos: int = 10) -> dict:
    print(f"[APIFY] scraping channel: {channel_url}")
    items = _apify_run(
        "streamers~youtube-scraper",
        {
            "startUrls": [{"url": channel_url}],
            "maxResults": max_videos,
            "maxResultsShorts": 0,
            "downloadSubtitles": False,
        },
        timeout=180,
    )

    if not items:
        raise ValueError("No videos found for this channel.")

    channel_name = items[0].get("channelName", channel_url)
    videos_data = []

    for v in items:
        title = v.get("title", "")
        description = (v.get("description") or "")[:400]
        context = f"Title: {title}\nDescription: {description}"

        print(f"[HF] analyzing: {title[:60]}")
        per = _ask_json(f"""Analyze this YouTube video briefly. Return JSON with:
- "summary": 1-2 sentence summary
- "main_topics": list of up to 4 topics
- "sentiment": "Positive", "Negative", or "Neutral"
- "content_type": e.g. Tutorial, Review, News, Opinion, Vlog, etc.

Return ONLY valid JSON.

{context}""")

        videos_data.append({
            "video_id": v.get("id", ""),
            "url": v.get("url", ""),
            "title": title,
            "upload_date": _fmt_date(v.get("date", "")),
            "duration": _format_duration(v.get("duration")),
            "view_count": v.get("viewCount"),
            "like_count": v.get("likes"),
            "summary": per.get("summary"),
            "main_topics": per.get("main_topics", []),
            "sentiment": per.get("sentiment"),
            "content_type": per.get("content_type"),
        })

    all_titles = "\n".join(f"- {v['title']} ({v['upload_date']})" for v in videos_data)
    print("[HF] channel-level analysis...")
    ch = _ask_json(f"""Analyze this YouTube channel based on its recent videos. Return JSON with:
- "channel_summary": 2-3 sentence overview
- "content_themes": list of recurring themes
- "posting_pattern": how frequently they post
- "audience_type": who the channel targets
- "content_style": overall style (educational, entertainment, news, etc.)
- "top_performing_topics": topics that appear most often

Return ONLY valid JSON.

Channel: {channel_name}
Recent videos:
{all_titles}""")

    dates = sorted([v["upload_date"] for v in videos_data if v["upload_date"]], reverse=True)

    return {
        "channel": channel_name,
        "channel_url": channel_url,
        "videos_analyzed": len(videos_data),
        "date_range": {
            "latest": dates[0] if dates else None,
            "oldest": dates[-1] if dates else None,
        },
        "channel_summary": ch.get("channel_summary"),
        "content_themes": ch.get("content_themes", []),
        "posting_pattern": ch.get("posting_pattern"),
        "audience_type": ch.get("audience_type"),
        "content_style": ch.get("content_style"),
        "top_performing_topics": ch.get("top_performing_topics", []),
        "videos": videos_data,
    }
