"""
Competitor Research Engine
Gathers structured competitive intelligence for a given company
using Google Search (SerpAPI) + website scraping.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyDSGDny-k99pLQB3xonYbiG1A-M9-1NPao")
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "0ce8a0102165979f7a84be8259503f63c3bf95698e13089cdee04f25db707082")

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _google_search(query: str, num: int = 5) -> list[str]:
    """Return a list of snippet strings from Google via SerpAPI."""
    if not SERPAPI_KEY:
        return []
    try:
        resp = requests.get(
            "https://serpapi.com/search",
            params={"q": query, "api_key": SERPAPI_KEY, "num": num, "engine": "google"},
            timeout=10
        )
        data = resp.json()
        snippets = []
        for r in data.get("organic_results", []):
            if r.get("snippet"):
                snippets.append(r["snippet"])
            if r.get("title"):
                snippets.append(r["title"])
        return snippets
    except Exception:
        return []


def _scrape_text(url: str, max_chars: int = 6000) -> str:
    """Scrape visible text from a URL."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = " ".join(soup.get_text(separator=" ").split())
        return text[:max_chars]
    except Exception:
        return ""


def _ask_gemini(question: str, context: str) -> str:
    """Ask Gemini to extract a specific field from context."""
    prompt = f"""You are a competitive intelligence analyst.
Based ONLY on the context below, answer this question concisely (1-3 sentences max, or a short list):

Question: {question}

Context:
{context}

If the information is not available in the context, respond with: "Not found"
"""
    try:
        response = _model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def _ask_gemini_list(question: str, context: str) -> list[str]:
    """Ask Gemini to return a JSON list."""
    prompt = f"""You are a competitive intelligence analyst.
Based ONLY on the context below, answer this question as a JSON array of strings.
Return ONLY the JSON array, no markdown, no explanation.

Question: {question}

Context:
{context}

If nothing found, return: []
"""
    try:
        raw = _model.generate_content(prompt).text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return []


# â”€â”€ Main Research Function â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def research_competitor(company_name: str, website: str) -> dict:
    """
    Research a competitor and return structured intelligence.
    """
    result = {"company": company_name, "website": website}

    # --- Scrape website ---
    website_text = _scrape_text(website)

    # --- Google searches ---
    g_general = _google_search(f"{company_name} fintech stock market app India")
    g_founders = _google_search(f"{company_name} founders CEO founded by")
    g_funding   = _google_search(f"{company_name} funding raised series investment")
    g_revenue   = _google_search(f"{company_name} annual revenue ARR")
    g_users     = _google_search(f"{company_name} number of users downloads")
    g_reviews   = _google_search(f"{company_name} user reviews complaints problems reddit")
    g_strategy  = _google_search(f"{company_name} partnership expansion new market 2024 2025")
    g_features  = _google_search(f"{company_name} new features launched product update 2024 2025")

    # Play Store / App Store reviews
    g_play      = _google_search(f"{company_name} site:play.google.com OR site:apps.apple.com reviews")
    g_reddit    = _google_search(f"{company_name} site:reddit.com review experience")

    general_ctx  = " ".join(g_general)
    founders_ctx = " ".join(g_founders)
    funding_ctx  = " ".join(g_funding)
    revenue_ctx  = " ".join(g_revenue)
    users_ctx    = " ".join(g_users)
    reviews_ctx  = " ".join(g_reviews + g_play + g_reddit)
    strategy_ctx = " ".join(g_strategy)
    features_ctx = " ".join(g_features)

    # --- Extract each field ---
    result["year_founded"] = _ask_gemini(
        f"What year was {company_name} founded?",
        founders_ctx + " " + general_ctx
    )

    result["founders"] = _ask_gemini_list(
        f"Who are the founders of {company_name}? List their names.",
        founders_ctx + " " + general_ctx
    )

    result["headquarters"] = _ask_gemini(
        f"Where is {company_name} headquartered? City and country.",
        general_ctx
    )

    result["platforms"] = _ask_gemini(
        f"Is {company_name} available on Web, Mobile (iOS/Android), or both?",
        website_text + " " + general_ctx
    )

    result["funding_raised"] = _ask_gemini(
        f"How much total funding has {company_name} raised? Include rounds if available.",
        funding_ctx
    )

    result["number_of_users"] = _ask_gemini(
        f"How many users or downloads does {company_name} have?",
        users_ctx + " " + general_ctx
    )

    result["annual_revenue"] = _ask_gemini(
        f"What is the annual revenue or ARR of {company_name}?",
        revenue_ctx
    )

    result["key_positioning"] = _ask_gemini(
        f"What is the key positioning or main marketing message of {company_name}?",
        website_text
    )

    result["revenue_model"] = _ask_gemini(
        f"What is the revenue model and pricing structure of {company_name}?",
        website_text + " " + general_ctx
    )

    result["differentiators"] = _ask_gemini_list(
        f"What are the key differentiators of {company_name}? What do users like about it?",
        website_text + " " + reviews_ctx
    )

    result["user_complaints"] = _ask_gemini_list(
        f"What are the main user complaints or negative reviews about {company_name}?",
        reviews_ctx
    )

    result["strategic_moves"] = _ask_gemini_list(
        f"What are the recent strategic moves of {company_name}? Partnerships, expansions, acquisitions.",
        strategy_ctx + " " + website_text
    )

    result["new_features"] = _ask_gemini_list(
        f"What new features has {company_name} recently launched?",
        features_ctx + " " + website_text
    )

    return result
