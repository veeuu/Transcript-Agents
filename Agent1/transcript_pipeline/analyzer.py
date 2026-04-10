"""
Steps 3-5: Extract relevant info, identify problems/decisions/improvements,
and produce a final conclusion with next steps.
Uses Google Gemini 2.5 Flash for LLM-based analysis.
"""

import json
import os
from dotenv import load_dotenv
load_dotenv()
from typing import Dict, Any

import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

ANALYSIS_PROMPT_PREFIX = """You are an expert business analyst reviewing a founders meeting transcript.

Produce a JSON object with EXACTLY these keys (respond with valid JSON only, no markdown, no code fences):

{
  "title": "short title of the meeting",
  "summary": "2-line summary of the entire discussion",
  "major_decisions": ["list of key decisions made"],
  "problems_identified": ["list of problems or blockers raised"],
  "solutions_pitched": ["list of proposed solutions or ideas"],
  "tone": {
    "positive": ["positive moments or sentiments"],
    "negative": ["concerns, friction, or negative signals"]
  },
  "timeline_of_discussion": [
    {"timestamp": "00:00-02:00", "section": "...", "key_point": "..."}
  ],
  "improvements_for_next_call": ["list of suggested improvements"],
  "next_steps": ["actionable next steps with owner if mentioned"],
  "decision_making_insights": ["anything useful for strategic decision making"]
}

Transcript:
"""


def analyze(structured: Dict[str, Any]) -> Dict[str, Any]:
    transcript_text = structured["formatted_dialogue"]
    metadata = structured["metadata"]

    prompt = ANALYSIS_PROMPT_PREFIX + transcript_text
    response = _model.generate_content(prompt)

    raw = response.text.strip()
    # Strip markdown code fences if model adds them anyway
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    analysis = json.loads(raw)
    analysis["metadata"] = metadata
    analysis["speaker_contribution"] = structured["speaker_contribution"]
    analysis["timeline"] = structured["timeline"]

    return analysis

