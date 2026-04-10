"""
Agent 6 — Product Brief Agent
Converts insights (Agent 5) + problems (Agent 4) + internal notes (Agent 1)
into clear, buildable product feature briefs.

Output schema per feature:
  feature_name    : short name for the feature
  problem         : user issue this solves
  why_it_matters  : impact on user
  solution        : high-level description
  user_flow       : step-by-step usage
  expected_impact : measurable outcome
  priority        : Critical / High / Medium / Low
  effort          : Low / Medium / High (estimated build complexity)
  target_user     : Beginner / Intermediate / Advanced
"""

import os
import json
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
_client = InferenceClient(api_key=HF_TOKEN)


# ── LLM helper ────────────────────────────────────────────────────────────────

def _ask_json(prompt: str, max_tokens: int = 3000) -> list | dict:
    try:
        resp = _client.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.15,
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


# ── Input flatteners ──────────────────────────────────────────────────────────

def _flatten_agent5(data: dict | list) -> str:
    """Extract insights from Agent 5 output."""
    lines = ["=== PRODUCT INSIGHTS (Agent 5) ==="]
    insights = data if isinstance(data, list) else data.get("insights", [])
    for ins in insights:
        lines.append(f"\nInsight: {ins.get('insight', '')}")
        lines.append(f"  Priority: {ins.get('priority', '')} | Hypothesis: {ins.get('hypothesis', '')}")
        lines.append(f"  Implication: {ins.get('implication', '')}")
        lines.append(f"  Action: {ins.get('recommended_action', '')}")
        for sp in ins.get("supporting_problems", []):
            lines.append(f"  Problem: {sp}")
    return "\n".join(lines)


def _flatten_agent4(data: dict | list) -> str:
    """Extract structured problems from Agent 4 output."""
    lines = ["=== USER PROBLEMS (Agent 4) ==="]
    problems = data if isinstance(data, list) else data.get("problems", [])
    for p in problems:
        lines.append(f"\nProblem: {p.get('problem', '')}")
        lines.append(f"  Frequency: {p.get('frequency', '')} | User: {p.get('user_type', '')} | Sources: {', '.join(p.get('source_mix', []))}")
        for e in p.get("evidence", [])[:2]:
            lines.append(f"  Evidence: {e}")
    return "\n".join(lines)


def _flatten_agent1(data: dict | list) -> str:
    """Extract internal notes from Agent 1 output."""
    if isinstance(data, list):
        return "\n\n".join(_flatten_agent1(item) for item in data if isinstance(item, dict))
    lines = ["=== INTERNAL NOTES (Agent 1) ==="]
    a = data.get("analysis", data)
    lines.append(f"Summary: {a.get('summary', '')}")
    for d in a.get("major_decisions", []):
        lines.append(f"Decision: {d}")
    for n in a.get("next_steps", []):
        lines.append(f"Next Step: {n}")
    for i in a.get("decision_making_insights", []):
        lines.append(f"Strategic Insight: {i}")
    return "\n".join(lines)


# ── Main generation ───────────────────────────────────────────────────────────

def generate_briefs(agent5_data, agent4_data=None, agent1_data=None) -> list:
    """
    Generate product feature briefs from insights + problems + internal notes.
    """
    parts = [_flatten_agent5(agent5_data)]
    if agent4_data:
        if isinstance(agent4_data, list):
            for item in agent4_data:
                parts.append(_flatten_agent4(item))
        else:
            parts.append(_flatten_agent4(agent4_data))
    if agent1_data:
        parts.append(_flatten_agent1(agent1_data))

    context = "\n\n".join(parts)
    print(f"[AGENT6] context length: {len(context)} chars")

    prompt = f"""You are a senior product manager. Based on the insights, user problems, and internal notes below,
generate a list of clear, buildable product feature briefs.

Each feature must directly address a validated user problem or insight.
Be specific — not generic. Think in terms of actual UI/UX features, not vague improvements.

Return a JSON array where each item has:
- "feature_name": short, memorable name for the feature (e.g. "Smart Withdrawal Tracker")
- "problem": the specific user issue this feature solves (1 sentence)
- "why_it_matters": the real impact on the user if this is NOT solved (1-2 sentences)
- "solution": high-level description of what to build (2-3 sentences)
- "user_flow": list of 3-5 steps describing how a user would use this feature
- "expected_impact": measurable outcome (e.g. "reduces withdrawal confusion by giving real-time status updates")
- "priority": "Critical", "High", "Medium", or "Low"
- "effort": estimated build complexity — "Low", "Medium", or "High"
- "target_user": "Beginner", "Intermediate", or "Advanced"

Rules:
- Generate one feature per distinct problem/insight — don't combine unrelated issues
- User flows must be concrete steps, not abstract descriptions
- Expected impact must be specific and measurable
- Return ONLY valid JSON array, no explanation

Context:
{context[:6000]}"""

    result = _ask_json(prompt, max_tokens=3000)
    if not isinstance(result, list):
        result = []

    print(f"[AGENT6] generated {len(result)} feature briefs")
    return result
