"""
Agent 4 — Insight Extraction Agent
Converts raw signals from Agents 1, 2, 3 into structured, validated user problems.

Output schema per problem:
  problem        : clear description
  evidence       : list of examples from input
  frequency      : Low / Medium / High
  user_type      : Beginner / Intermediate / Advanced
  source_mix     : list of sources (Competitor / Reddit / YouTube / Internal)
  positive_points: what's working well related to this area
  negative_points: what's broken or painful
"""

import os
import json
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
# HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
_client = InferenceClient(api_key=HF_TOKEN)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ask_json(prompt: str):
    try:
        resp = _client.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.1,
        )
        raw = resp.choices[0].message.content.strip()
        if "```" in raw:
            for part in raw.split("```"):
                part = part.strip().lstrip("json").strip()
                if part.startswith("[") or part.startswith("{"):
                    raw = part
                    break
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[HF ERROR] {e}")
        return []


def _flatten_input(data: list | dict) -> str:
    """Convert mixed agent outputs into a single readable text block."""
    lines = []

    def process(obj, source_hint=""):
        if isinstance(obj, list):
            for item in obj:
                process(item, source_hint)
        elif isinstance(obj, dict):
            # Agent 1 — transcript analysis
            if "analysis" in obj and "problems_identified" in obj.get("analysis", {}):
                a = obj["analysis"]
                lines.append(f"[INTERNAL TRANSCRIPT]")
                lines.append(f"Summary: {a.get('summary','')}")
                for p in a.get("problems_identified", []):
                    lines.append(f"Problem: {p}")
                for t in a.get("tone", {}).get("negative", []):
                    lines.append(f"Negative tone: {t}")
                for t in a.get("tone", {}).get("positive", []):
                    lines.append(f"Positive tone: {t}")
                for d in a.get("major_decisions", []):
                    lines.append(f"Decision: {d}")

            # Agent 2 — competitor research
            elif "user_complaints" in obj and "company" in obj:
                lines.append(f"[COMPETITOR: {obj.get('company','')}]")
                for c in obj.get("user_complaints", []):
                    lines.append(f"Complaint: {c}")
                for d in obj.get("differentiators", []):
                    lines.append(f"Differentiator: {d}")
                for m in obj.get("strategic_moves", []):
                    lines.append(f"Strategic move: {m}")
                for f in obj.get("new_features", []):
                    lines.append(f"New feature: {f}")

            # Agent 3 — YouTube video
            elif "video_id" in obj:
                lines.append(f"[YOUTUBE VIDEO: {obj.get('title','')}]")
                lines.append(f"Sentiment: {obj.get('sentiment','')}")
                for i in obj.get("key_insights", []):
                    lines.append(f"Insight: {i}")
                for n in obj.get("negative_points", []):
                    lines.append(f"Negative: {n}")

            # Agent 3 — YouTube channel
            elif "channel" in obj and "videos" in obj:
                lines.append(f"[YOUTUBE CHANNEL: {obj.get('channel','')}]")
                lines.append(f"Summary: {obj.get('channel_summary','')}")
                for t in obj.get("content_themes", []):
                    lines.append(f"Theme: {t}")
                for n in obj.get("negative_points", []):
                    lines.append(f"Negative: {n}")

            # Agent 3 — Reddit post
            elif "post_url" in obj:
                lines.append(f"[REDDIT POST: {obj.get('title','')} in {obj.get('subreddit','')}]")
                lines.append(f"Sentiment: {obj.get('overall_sentiment','')} | Community: {obj.get('community_sentiment','')}")
                for o in obj.get("key_opinions", []):
                    lines.append(f"Opinion: {o}")
                for n in obj.get("negative_points", []):
                    lines.append(f"Negative: {n}")
                lines.append(f"Takeaway: {obj.get('key_takeaway','')}")

            # Agent 3 — Subreddit
            elif "subreddit" in obj and "posts" in obj:
                lines.append(f"[SUBREDDIT: {obj.get('subreddit','')}]")
                lines.append(f"Summary: {obj.get('subreddit_summary','')}")
                for t in obj.get("hot_topics", []):
                    lines.append(f"Hot topic: {t}")
                for n in obj.get("negative_points", []):
                    lines.append(f"Negative: {n}")
                for p in obj.get("posts", []):
                    lines.append(f"Post: {p.get('title','')} | {p.get('overall_sentiment','')} | {p.get('post_type','')}")
                    for np in p.get("negative_points", []):
                        lines.append(f"  Post negative: {np}")

            # Agent 3 — App Store
            elif "store" in obj and "app_name" in obj:
                lines.append(f"[APP: {obj.get('app_name','')} on {obj.get('store','')}]")
                lines.append(f"Rating: {obj.get('rating','')} | Installs: {obj.get('installs','')}")
                for c in obj.get("top_complaints", []):
                    lines.append(f"Complaint: {c}")
                for p in obj.get("top_praises", []):
                    lines.append(f"Praise: {p}")
                for i in obj.get("recent_issues", []):
                    lines.append(f"Recent issue: {i}")
                for r in obj.get("negative_reviews", [])[:10]:
                    lines.append(f"Review [{r.get('rating')}★]: {(r.get('review') or '')[:200]}")

    process(data)
    return "\n".join(lines)


# ── Main extraction ───────────────────────────────────────────────────────────

def extract_insights(raw_input: list | dict) -> list:
    """
    Takes combined output from Agents 1/2/3 and returns
    a list of structured user problems.
    """
    signal_text = _flatten_input(raw_input)
    print(f"[AGENT4] signal text length: {len(signal_text)} chars")

    prompt = f"""You are a product insight analyst. Analyze the signals below from multiple sources
(internal transcripts, competitor research, YouTube, Reddit, App Store reviews).

Extract a list of VALIDATED USER PROBLEMS — not summaries.
Each problem must be specific, actionable, and grounded in evidence from the signals.

Group similar signals together. Count frequency across sources.

Return a JSON array where each item has:
- "problem": clear 1-2 sentence description of the user issue
- "evidence": list of 2-4 direct quotes or examples from the signals
- "frequency": "Low" (1 source), "Medium" (2-3 sources), or "High" (4+ sources or repeated)
- "user_type": "Beginner", "Intermediate", or "Advanced" based on context
- "source_mix": list of sources where this appeared — use: "Competitor", "Reddit", "YouTube", "App Store", "Internal"
- "positive_points": list of what IS working well in this area (from the signals)
- "negative_points": list of what is broken, painful, or frustrating in this area

Return ONLY a valid JSON array, no explanation.

Signals:
{signal_text[:6000]}"""

    result = _ask_json(prompt)
    if not isinstance(result, list):
        result = []

    print(f"[AGENT4] extracted {len(result)} problems")
    return result
