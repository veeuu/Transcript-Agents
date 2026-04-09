"""
Competitor Research Engine (Free Version)
- DuckDuckGo for search (no API key needed)
- HuggingFace Inference API for LLM (free token, runs on HF servers)
- BeautifulSoup for website scraping
"""

import os
import json
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from dotenv import load_dotenv

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
CTX_LIMIT = 4000

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ddg_search(query: str, num: int = 5) -> list[str]:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num))
        print(f"[DDG] '{query}' → {len(results)} results")
        return [r.get("body", "") + " " + r.get("title", "") for r in results]
    except Exception as e:
        print(f"[DDG ERROR] '{query}' → {e}")
        return []


def _scrape_text(url: str, max_chars: int = 4000) -> str:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        print(f"[SCRAPE] {url} → {len(text)} chars")
        return text[:max_chars]
    except Exception as e:
        print(f"[SCRAPE ERROR] {url} → {e}")
        return ""


def _hf_infer(prompt: str) -> str:
    """Call HuggingFace via InferenceClient."""
    try:
        from huggingface_hub import InferenceClient
        client = InferenceClient(api_key=HF_TOKEN)
        response = client.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.1,
        )
        text = response.choices[0].message.content.strip()
        print(f"[HF] response length: {len(text)} chars")
        return text
    except Exception as e:
        print(f"[HF ERROR] {e}")
        return ""


def _parse_json(raw: str) -> dict:
    if "```" in raw:
        parts = raw.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:]
            part = part.strip()
            if part.startswith("{"):
                raw = part
                break
    start = raw.find("{")
    end = raw.rfind("}") + 1
    if start != -1 and end > start:
        raw = raw[start:end]
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _mini_prompt(company: str, keys: list[str], ctx: str) -> dict:
    keys_str = ", ".join(f'"{k}"' for k in keys)
    prompt = f"""You are a competitive intelligence analyst. Extract information about "{company}" from the context below.

Return ONLY a valid JSON object with these keys: {keys_str}
Rules:
- "platforms": must be one of "Web", "Mobile", or "Both" — not a product list
- String fields: actual value found, or null if not in context
- Array fields: list of real extracted strings, or []
- Do NOT invent data not present in the context
- Return ONLY the JSON, no explanation

Context:
{ctx[:CTX_LIMIT]}"""
    raw = _hf_infer(prompt)
    return _parse_json(raw)


# ── Main research function ────────────────────────────────────────────────────

def research_competitor(company_name: str, website: str) -> dict:
    website_text = _scrape_text(website)

    facts_ctx = " ".join(
        _ddg_search(f"{company_name} founded year headquarters founders CEO", num=4) +
        _ddg_search(f"{company_name} total registered users active investors downloads", num=4) +
        _ddg_search(f"{company_name} annual revenue ARR net revenue FY2024 FY2025", num=4) +
        _ddg_search(f"{company_name} total funding raised valuation series", num=3)
    )
    positioning_ctx = " ".join(
        _ddg_search(f"{company_name} revenue model how does it make money brokerage fees", num=4) +
        _ddg_search(f"{company_name} product features pricing plans", num=3)
    )
    sentiment_ctx = " ".join(
        _ddg_search(f"{company_name} user reviews complaints reddit problems 2024", num=4) +
        _ddg_search(f"{company_name} new features launched product update 2024 2025", num=4) +
        _ddg_search(f"{company_name} partnership acquisition expansion strategic 2024 2025", num=3)
    )

    print("[HF] call 1/3 — facts")
    facts = _mini_prompt(company_name,
        ["year_founded", "founders", "headquarters", "platforms", "funding_raised", "number_of_users", "annual_revenue"],
        facts_ctx)

    print("[HF] call 2/3 — positioning")
    positioning = _mini_prompt(company_name,
        ["key_positioning", "revenue_model", "differentiators"],
        website_text + " " + positioning_ctx)

    print("[HF] call 3/3 — sentiment")
    sentiment = _mini_prompt(company_name,
        ["user_complaints", "strategic_moves", "new_features"],
        sentiment_ctx)

    def clean(val):
        if val is None:
            return None
        if isinstance(val, list):
            return ", ".join(str(v) for v in val) if val else None
        val = str(val).strip()
        return None if val.lower() in ("null", "none", "") else val

    def clean_list(val):
        if not isinstance(val, list):
            return []
        bad = {"null", "none", "n/a", "item1", "item2", "complaint1", "complaint2",
               "move1", "move2", "feature1", "feature2", "name1", "name2"}
        return [str(v).strip() for v in val if str(v).strip().lower() not in bad]

    return {
        "company":         company_name,
        "website":         website,
        "year_founded":    clean(facts.get("year_founded")),
        "founders":        clean_list(facts.get("founders", [])),
        "headquarters":    clean(facts.get("headquarters")),
        "platforms":       clean(facts.get("platforms")),
        "funding_raised":  clean(facts.get("funding_raised")),
        "number_of_users": clean(facts.get("number_of_users")),
        "annual_revenue":  clean(facts.get("annual_revenue")),
        "key_positioning": clean(positioning.get("key_positioning")),
        "revenue_model":   clean(positioning.get("revenue_model")),
        "differentiators": clean_list(positioning.get("differentiators", [])),
        "user_complaints": clean_list(sentiment.get("user_complaints", [])),
        "strategic_moves": clean_list(sentiment.get("strategic_moves", [])),
        "new_features":    clean_list(sentiment.get("new_features", [])),
    }
