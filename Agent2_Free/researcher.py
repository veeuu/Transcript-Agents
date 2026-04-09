"""
Competitor Research Engine (Free Version)
- DuckDuckGo for search (no API key needed)
- Ollama for local LLM inference (no API key needed)
- BeautifulSoup for website scraping
"""

import json
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

# ── Config ────────────────────────────────────────────────────────────────────
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3.2:latest"
# Max chars to send per prompt — keep small so llama3.2 responds fast
CTX_LIMIT = 1500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ddg_search(query: str, num: int = 5) -> list[str]:
    """Search DuckDuckGo and return a list of snippets."""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=num))
        print(f"[DDG] '{query}' → {len(results)} results")
        return [r.get("body", "") + " " + r.get("title", "") for r in results]
    except Exception as e:
        print(f"[DDG ERROR] '{query}' → {e}")
        return []


def _scrape_text(url: str, max_chars: int = 6000) -> str:
    """Scrape visible text from a URL."""
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


def _ollama(prompt: str) -> str:
    """Send a prompt to the local Ollama model and return the response."""
    try:
        resp = requests.post(
            OLLAMA_URL,
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=180,
        )
        text = resp.json().get("response", "").strip()
        print(f"[OLLAMA] response length: {len(text)} chars")
        return text
    except Exception as e:
        print(f"[OLLAMA ERROR] {e}")
        return ""


def _parse_json(raw: str) -> dict:
    """Extract JSON object from model response, stripping markdown fences."""
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


# ── Main research function ────────────────────────────────────────────────────

def _mini_prompt(company: str, keys: list[str], ctx: str) -> dict:
    """Send a small focused prompt and return parsed JSON."""
    keys_str = ", ".join(f'"{k}"' for k in keys)
    prompt = f"""You are a data extractor. Read the context and fill in what you find about "{company}".

Return a JSON object with these keys: {keys_str}
- String fields: fill with actual value found, or null if not found
- Array fields (differentiators, user_complaints, strategic_moves, new_features, founders): fill with real extracted items, or []
- Do NOT copy example text, fill with REAL data from context only

Context:
{ctx[:CTX_LIMIT]}

JSON:"""
    raw = _ollama(prompt)
    return _parse_json(raw)


def research_competitor(company_name: str, website: str) -> dict:
    website_text = _scrape_text(website, max_chars=2000)

    # Search contexts grouped by topic
    facts_ctx = " ".join(
        _ddg_search(f"{company_name} founded year headquarters founders CEO", num=3) +
        _ddg_search(f"{company_name} funding raised users revenue", num=3)
    )
    positioning_ctx = " ".join(
        _ddg_search(f"{company_name} product features pricing revenue model", num=3)
    )
    sentiment_ctx = " ".join(
        _ddg_search(f"{company_name} user reviews complaints reddit problems", num=3) +
        _ddg_search(f"{company_name} new features partnership expansion 2024 2025", num=3)
    )

    # Call 1: hard facts
    print("[OLLAMA] call 1/3 — facts")
    facts = _mini_prompt(company_name,
        ["year_founded", "founders", "headquarters", "platforms", "funding_raised", "number_of_users", "annual_revenue"],
        facts_ctx)

    # Call 2: positioning from website
    print("[OLLAMA] call 2/3 — positioning")
    positioning = _mini_prompt(company_name,
        ["key_positioning", "revenue_model", "differentiators"],
        website_text + " " + positioning_ctx)

    # Call 3: sentiment & strategy
    print("[OLLAMA] call 3/3 — sentiment")
    sentiment = _mini_prompt(company_name,
        ["user_complaints", "strategic_moves", "new_features"],
        sentiment_ctx)

    def clean(val):
        """Return a string or None. Coerces ints, rejects lists."""
        if val is None:
            return None
        if isinstance(val, list):
            # model put a list where a string was expected — join it
            val = ", ".join(str(v) for v in val) if val else None
            return val
        val = str(val).strip()
        return None if val.lower() == "null" else val

    def clean_list(val):
        if not isinstance(val, list):
            return []
        bad = {"null", "item1", "item2", "complaint1", "complaint2", "move1", "move2", "feature1", "feature2", "name1", "name2"}
        return [str(v) for v in val if str(v).strip().lower() not in bad]

    return {
        "company": company_name,
        "website": website,
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
