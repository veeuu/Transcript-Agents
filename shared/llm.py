"""
Shared LLM utility — Groq with JSON mode + retry fallback.
Used by Agents 4, 5, 6, 7.

Groq is free, 10x faster than HuggingFace inference, 131k context window,
and supports response_format=json_object for guaranteed valid JSON output.
"""

import os
import json
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
# llama-3.3-70b: best quality on Groq free tier, 131k context
# fallback: llama3-8b-8192 (faster, smaller context)
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")

_client = Groq(api_key=GROQ_API_KEY)

MAX_RETRIES = 3
RETRY_DELAY = 2  # seconds


def ask_json(prompt: str, max_tokens: int = 2000, retries: int = MAX_RETRIES) -> dict | list:
    """
    Send a prompt to Groq and return parsed JSON.
    Uses response_format=json_object for guaranteed valid JSON.
    Retries up to MAX_RETRIES times on failure.
    """
    for attempt in range(1, retries + 1):
        try:
            resp = _client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a precise data extraction assistant. Always respond with valid JSON only.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content.strip()
            parsed = json.loads(raw)
            return parsed
        except json.JSONDecodeError as e:
            print(f"[GROQ] JSON parse error (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(RETRY_DELAY)
        except Exception as e:
            err = str(e)
            print(f"[GROQ] Error (attempt {attempt}/{retries}): {err}")
            # rate limit — wait longer
            if "rate_limit" in err.lower() or "429" in err:
                time.sleep(10 * attempt)
            elif attempt < retries:
                time.sleep(RETRY_DELAY)
    return {}


def ask_json_array(prompt: str, max_tokens: int = 2000) -> list:
    """
    Ask for a JSON array. Wraps in object since Groq json_object mode
    requires a top-level object, then extracts the array.
    """
    wrapped_prompt = prompt + '\n\nIMPORTANT: Return a JSON object with a single key "items" containing the array. Example: {"items": [...]}'
    result = ask_json(wrapped_prompt, max_tokens)
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        # try common array keys
        for key in ("items", "results", "problems", "insights", "features", "posts", "videos"):
            if isinstance(result.get(key), list):
                return result[key]
        # if only one key and it's a list
        vals = list(result.values())
        if len(vals) == 1 and isinstance(vals[0], list):
            return vals[0]
    return []


def ask_text(prompt: str, max_tokens: int = 1000) -> str:
    """Plain text response without JSON mode."""
    try:
        resp = _client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GROQ] Text error: {e}")
        return ""
