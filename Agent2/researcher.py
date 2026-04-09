"""
Competitor Research Engine
Gathers structured competitive intelligence for a given company
using Google Search (SerpAPI) + website scraping + Gemini analysis.
"""

import os
import re
import json
import requests
from bs4 import BeautifulSoup
from typing import Optional
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.environ.get("AGENT2_GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")

genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _google_search(query: str, num: int = 5) -> list:
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
    prompt = f"""You are a competitive intelligence analyst.
Based ONLY on the context below, answer this question concisely (1-3 sentences max):

Question: {question}

Context:
{context}

If the information is not available, respond with: Not found"""
    try:
        return _model.generate_content(prompt).text.strip()
    except Exception as e:
        return f"Error: {str(e)}"


def _ask_gemini_list(question: str, context: str) -> list:
    prompt = f"""You are a competitive intelligence analyst.
Based ONLY on the context below, answer as a JSON array of strings.
Return ONLY the JSON array, no markdown, no explanation.

Question: {question}

Context:
{context}

If nothing found, return: []"""
    try:
        raw = _model.generate_content(prompt).text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return []


def research_competitor(company_name: str, website: str) -> dict:
    result = {"company": company_name, "website": website}

    website_text = _scrape_text(website)

    g_general  = _google_search(f"{company_name} fintech stock market app India")
    g_founders = _google_search(f"{company_name} founders CEO founded by")
    g_funding  = _google_search(f"{company_name} funding raised series investment")
    g_revenue  = _google_search(f"{company_name} annual revenue ARR")
    g_users    = _google_search(f"{company_name} number of users downloads")
    g_reviews  = _google_search(f"{company_name} user reviews complaints problems reddit")
    g_strategy = _google_search(f"{company_name} partnership expansion new market 2024 2025")
    g_features = _google_search(f"{company_name} new features launched product update 2024 2025")
    g_play     = _google_search(f"{company_name} site:play.google.com OR site:apps.apple.com reviews")
    g_reddit   = _google_search(f"{company_name} site:reddit.com review experience")

    general_ctx  = " ".join(g_general)
    founders_ctx = " ".join(g_founders)
    funding_ctx  = " ".join(g_funding)
    revenue_ctx  = " ".join(g_revenue)
    users_ctx    = " ".join(g_users)
    reviews_ctx  = " ".join(g_reviews + g_play + g_reddit)
    strategy_ctx = " ".join(g_strategy)
    features_ctx = " ".join(g_features)

    result["year_founded"]      = _ask_gemini(f"What year was {company_name} founded?", founders_ctx + " " + general_ctx)
    result["founders"]          = _ask_gemini_list(f"Who are the founders of {company_name}?", founders_ctx + " " + general_ctx)
    result["headquarters"]      = _ask_gemini(f"Where is {company_name} headquartered?", general_ctx)
    result["platforms"]         = _ask_gemini(f"Is {company_name} available on Web, Mobile, or both?", website_text + " " + general_ctx)
    result["funding_raised"]    = _ask_gemini(f"How much total funding has {company_name} raised?", funding_ctx)
    result["number_of_users"]   = _ask_gemini(f"How many users or downloads does {company_name} have?", users_ctx + " " + general_ctx)
    result["annual_revenue"]    = _ask_gemini(f"What is the annual revenue of {company_name}?", revenue_ctx)
    result["key_positioning"]   = _ask_gemini(f"What is the key positioning or main message of {company_name}?", website_text)
    result["revenue_model"]     = _ask_gemini(f"What is the revenue model and pricing of {company_name}?", website_text + " " + general_ctx)
    result["differentiators"]   = _ask_gemini_list(f"What are the key differentiators of {company_name}? What do users like?", website_text + " " + reviews_ctx)
    result["user_complaints"]   = _ask_gemini_list(f"What are the main user complaints about {company_name}?", reviews_ctx)
    result["strategic_moves"]   = _ask_gemini_list(f"What are recent strategic moves of {company_name}? Partnerships, expansions.", strategy_ctx + " " + website_text)
    result["new_features"]      = _ask_gemini_list(f"What new features has {company_name} recently launched?", features_ctx + " " + website_text)

    return result
