"""
YouTube & Reddit Analysis Agent - Free Version (Agent 3 Free)
- Apify scrapers for YouTube and Reddit data (free tier)
- HuggingFace Qwen2.5-72B for analysis (free token)
- No Gemini, no YouTube/Reddit API key needed
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


# ── Reddit post analysis ──────────────────────────────────────────────────────

def analyze_reddit_post(post_url: str) -> dict:
    print(f"[APIFY] scraping Reddit post: {post_url}")
    items = _apify_run(
        "trudax~reddit-scraper-lite",
        {
            "startUrls": [{"url": post_url}],
            "maxComments": 50,
            "maxCommunitiesCount": 0,
            "maxUserCount": 0,
        },
        timeout=120,
    )

    if not items:
        raise ValueError("No data returned from Apify for this Reddit post.")

    # find the post item (type == "post")
    post = next((i for i in items if i.get("dataType") == "post"), items[0])
    comments_raw = [i for i in items if i.get("dataType") == "comment"]

    title = post.get("title", "")
    body = (post.get("body") or post.get("text") or "")[:2000]
    subreddit = post.get("communityName", post.get("subreddit", ""))
    author = post.get("username", post.get("author", ""))
    score = post.get("score", post.get("upVotes"))
    upvote_ratio = post.get("upVoteRatio")
    num_comments = post.get("numberOfComments", post.get("commentsCount", len(comments_raw)))
    created_at = post.get("createdAt", post.get("created", ""))
    url = post.get("url", post_url)
    flair = post.get("flair", post.get("linkFlairText", ""))

    # top comments text
    top_comments = []
    for c in comments_raw[:20]:
        text = (c.get("body") or c.get("text") or "").strip()
        if text:
            top_comments.append(text)

    comments_ctx = "\n".join(f"- {c[:200]}" for c in top_comments[:15])
    context = f"Subreddit: r/{subreddit}\nTitle: {title}\nBody: {body}\nTop comments:\n{comments_ctx}"

    print("[HF] analyzing Reddit post...")
    analysis = _ask_json(f"""Analyze this Reddit post and its comments. Return a JSON object with these keys:
- "summary": 2-3 sentence summary of what the post is about
- "main_topics": list of main topics discussed (max 6)
- "overall_sentiment": sentiment of the post — "Positive", "Negative", or "Neutral"
- "community_sentiment": sentiment of the comments — "Positive", "Negative", "Neutral", or "Mixed"
- "key_opinions": list of 3-5 distinct opinions or viewpoints expressed in comments
- "post_type": e.g. "Question", "Discussion", "News", "Rant", "Meme", "Review", "AMA", "Advice", etc.
- "controversy_level": "Low", "Medium", or "High" based on comment tone
- "key_takeaway": single most important insight from this post and its discussion

Return ONLY valid JSON, no explanation.

Context:
{context[:4000]}""")

    return {
        "post_url": url,
        "title": title,
        "subreddit": subreddit,
        "author": author,
        "created_at": created_at,
        "score": score,
        "upvote_ratio": upvote_ratio,
        "num_comments": num_comments,
        "flair": flair or None,
        "body_preview": body[:500] if body else None,
        "top_comments_scraped": len(top_comments),
        "summary": analysis.get("summary"),
        "main_topics": analysis.get("main_topics", []),
        "overall_sentiment": analysis.get("overall_sentiment"),
        "community_sentiment": analysis.get("community_sentiment"),
        "key_opinions": analysis.get("key_opinions", []),
        "post_type": analysis.get("post_type"),
        "controversy_level": analysis.get("controversy_level"),
        "key_takeaway": analysis.get("key_takeaway"),
    }


# ── Subreddit analysis ────────────────────────────────────────────────────────

# In-memory store for monitor state: {subreddit_name: {"last_post_ids": set, "new_posts": []}}
_monitor_state: dict = {}


def _scrape_subreddit_posts(subreddit_url: str, max_posts: int = 20) -> list:
    """Fetch recent posts from a subreddit via Apify."""
    return _apify_run(
        "trudax~reddit-scraper-lite",
        {
            "startUrls": [{"url": subreddit_url}],
            "maxPostCount": max_posts,
            "maxComments": 10,
            "maxCommunitiesCount": 0,
            "maxUserCount": 0,
        },
        timeout=180,
    )


def _analyze_post_brief(post: dict) -> dict:
    """Quick per-post analysis for subreddit overview."""
    title = post.get("title", "")
    body = (post.get("body") or post.get("text") or "")[:500]
    subreddit = post.get("communityName", post.get("subreddit", ""))
    comments_raw = post.get("comments", []) or []
    top_comments = "\n".join(f"- {(c.get('body') or '')[:150]}" for c in comments_raw[:5])

    context = f"Title: {title}\nBody: {body}\nTop comments:\n{top_comments}"

    result = _ask_json(f"""Analyze this Reddit post briefly. Return JSON with:
- "summary": 1-2 sentence summary
- "main_topics": list of up to 4 topics
- "overall_sentiment": "Positive", "Negative", or "Neutral"
- "community_sentiment": "Positive", "Negative", "Neutral", or "Mixed"
- "post_type": e.g. Question, Discussion, News, Rant, Review, Advice, etc.
- "controversy_level": "Low", "Medium", or "High"

Return ONLY valid JSON.

{context}""")

    return {
        "post_id": post.get("id", ""),
        "post_url": post.get("url", ""),
        "title": title,
        "author": post.get("username", post.get("author", "")),
        "created_at": post.get("createdAt", post.get("created", "")),
        "score": post.get("score", post.get("upVotes")),
        "upvote_ratio": post.get("upVoteRatio"),
        "num_comments": post.get("numberOfComments", post.get("commentsCount")),
        "flair": post.get("flair") or post.get("linkFlairText") or None,
        "summary": result.get("summary"),
        "main_topics": result.get("main_topics", []),
        "overall_sentiment": result.get("overall_sentiment"),
        "community_sentiment": result.get("community_sentiment"),
        "post_type": result.get("post_type"),
        "controversy_level": result.get("controversy_level"),
    }


def analyze_subreddit(subreddit_url: str, max_posts: int = 20) -> dict:
    """Fetch and analyze the last N posts from a subreddit."""
    print(f"[APIFY] scraping subreddit: {subreddit_url}")
    items = _scrape_subreddit_posts(subreddit_url, max_posts)

    posts_raw = [i for i in items if i.get("dataType") == "post" or i.get("title")]
    if not posts_raw:
        raise ValueError("No posts found for this subreddit.")

    subreddit_name = posts_raw[0].get("communityName", posts_raw[0].get("subreddit", subreddit_url))

    # store seen post IDs for monitor
    seen_ids = {p.get("id", "") for p in posts_raw}
    _monitor_state[subreddit_name] = {"last_post_ids": seen_ids, "new_posts": []}

    print(f"[HF] analyzing {len(posts_raw)} posts...")
    analyzed_posts = [_analyze_post_brief(p) for p in posts_raw]

    # subreddit-level summary
    titles_ctx = "\n".join(f"- {p['title']} [{p.get('overall_sentiment','')}]" for p in analyzed_posts)
    summary = _ask_json(f"""Analyze this investing subreddit based on recent posts. Return JSON with:
- "subreddit_summary": 2-3 sentence overview of current community mood and topics
- "hot_topics": list of topics being discussed most right now
- "dominant_sentiment": overall community sentiment right now
- "common_post_types": most common types of posts
- "notable_trends": any emerging trends or recurring themes

Return ONLY valid JSON.

Subreddit: r/{subreddit_name}
Recent posts:
{titles_ctx}""")

    dates = sorted([p["created_at"] for p in analyzed_posts if p.get("created_at")], reverse=True)

    return {
        "subreddit": subreddit_name,
        "subreddit_url": subreddit_url,
        "posts_analyzed": len(analyzed_posts),
        "date_range": {
            "latest": dates[0] if dates else None,
            "oldest": dates[-1] if dates else None,
        },
        "subreddit_summary": summary.get("subreddit_summary"),
        "hot_topics": summary.get("hot_topics", []),
        "dominant_sentiment": summary.get("dominant_sentiment"),
        "common_post_types": summary.get("common_post_types", []),
        "notable_trends": summary.get("notable_trends", []),
        "posts": analyzed_posts,
    }


# ── Subreddit live monitor ────────────────────────────────────────────────────

def check_new_posts(subreddit_url: str) -> dict:
    """
    Poll a subreddit for new posts since the last check.
    Call this repeatedly (e.g. every 5-10 min) to get live updates.
    New posts are auto-analyzed and returned.
    """
    print(f"[MONITOR] checking for new posts: {subreddit_url}")
    items = _scrape_subreddit_posts(subreddit_url, max_posts=10)
    posts_raw = [i for i in items if i.get("dataType") == "post" or i.get("title")]

    subreddit_name = posts_raw[0].get("communityName", subreddit_url) if posts_raw else subreddit_url
    state = _monitor_state.get(subreddit_name, {"last_post_ids": set(), "new_posts": []})
    known_ids = state["last_post_ids"]

    new_raw = [p for p in posts_raw if p.get("id", "") not in known_ids]
    print(f"[MONITOR] found {len(new_raw)} new posts")

    new_analyzed = []
    for p in new_raw:
        analyzed = _analyze_post_brief(p)
        new_analyzed.append(analyzed)
        known_ids.add(p.get("id", ""))

    _monitor_state[subreddit_name] = {"last_post_ids": known_ids, "new_posts": new_analyzed}

    return {
        "subreddit": subreddit_name,
        "new_posts_found": len(new_analyzed),
        "new_posts": new_analyzed,
        "tip": "Call this endpoint again in 5-10 minutes to check for more new posts.",
    }
