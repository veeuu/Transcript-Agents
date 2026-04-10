"""
Agent 5 — Research Synthesis Agent
Converts structured problems + competitor signals + internal notes
into higher-level product insights and hypotheses.

Output schema per insight:
  insight            : core underlying issue (the "why behind the what")
  supporting_problems: list of related problems that point to this insight
  evidence           : why this insight is valid
  implication        : what this means for the product
  priority           : Critical / High / Medium / Low
  hypothesis         : testable hypothesis for product team
  recommended_action : concrete next step
"""

import os
import json
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
# mistral-small is fast, cheap, excellent at synthesis and reasoning
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
_client = InferenceClient(api_key=HF_TOKEN)


# ── LLM helper ────────────────────────────────────────────────────────────────

def _ask_json(prompt: str, max_tokens: int = 2500) -> list | dict:
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

def _flatten_agent1(data: dict | list) -> str:
    """Extract key signals from Agent 1 transcript output."""
    # handle if file was parsed as list of objects
    if isinstance(data, list):
        return "\n\n".join(_flatten_agent1(item) for item in data if isinstance(item, dict))
    lines = ["=== INTERNAL NOTES (Transcript Analysis) ==="]
    a = data.get("analysis", data)
    lines.append(f"Meeting: {a.get('title', data.get('metadata', {}).get('title', ''))}")
    lines.append(f"Summary: {a.get('summary', '')}")
    for p in a.get("problems_identified", []):
        lines.append(f"Internal Problem: {p}")
    for d in a.get("major_decisions", []):
        lines.append(f"Decision: {d}")
    for n in a.get("tone", {}).get("negative", []):
        lines.append(f"Concern: {n}")
    for s in a.get("next_steps", []):
        lines.append(f"Next Step: {s}")
    for i in a.get("decision_making_insights", []):
        lines.append(f"Strategic Insight: {i}")
    return "\n".join(lines)


def _flatten_agent4(data: dict | list) -> str:
    """Extract structured problems from Agent 4 output."""
    lines = ["=== STRUCTURED USER PROBLEMS (Agent 4) ==="]
    problems = data if isinstance(data, list) else data.get("problems", [])
    for p in problems:
        lines.append(f"\nProblem: {p.get('problem', '')}")
        lines.append(f"  Frequency: {p.get('frequency', '')} | User Type: {p.get('user_type', '')} | Sources: {', '.join(p.get('source_mix', []))}")
        for e in p.get("evidence", [])[:3]:
            lines.append(f"  Evidence: {e}")
        for n in p.get("negative_points", [])[:3]:
            lines.append(f"  Negative: {n}")
        for pos in p.get("positive_points", [])[:2]:
            lines.append(f"  Positive: {pos}")
    return "\n".join(lines)


def _flatten_competitor(data: dict) -> str:
    """Extract competitor signals."""
    lines = [f"=== COMPETITOR: {data.get('company', '')} ==="]
    lines.append(f"Positioning: {data.get('key_positioning', '')}")
    lines.append(f"Revenue Model: {data.get('revenue_model', '')}")
    for d in data.get("differentiators", []):
        lines.append(f"Differentiator: {d}")
    for c in data.get("user_complaints", []):
        lines.append(f"User Complaint: {c}")
    for m in data.get("strategic_moves", []):
        lines.append(f"Strategic Move: {m}")
    for f in data.get("new_features", []):
        lines.append(f"New Feature: {f}")
    return "\n".join(lines)


def _build_context(agent1_data, agent4_data, competitor_data=None) -> str:
    parts = []
    if agent1_data:
        parts.append(_flatten_agent1(agent1_data))
    if agent4_data:
        # agent4 output could be a list of objects or a single dict
        if isinstance(agent4_data, list):
            for item in agent4_data:
                parts.append(_flatten_agent4(item))
        else:
            parts.append(_flatten_agent4(agent4_data))
    if competitor_data:
        if isinstance(competitor_data, list):
            for c in competitor_data:
                parts.append(_flatten_competitor(c))
        elif isinstance(competitor_data, dict):
            parts.append(_flatten_competitor(competitor_data))
    return "\n\n".join(parts)


# ── Main synthesis ────────────────────────────────────────────────────────────

def synthesize(agent1_data: dict, agent4_data: dict | list, competitor_data=None) -> list:
    """
    Synthesize problems + internal notes + competitor signals
    into high-level product insights.
    """
    context = _build_context(agent1_data, agent4_data, competitor_data)
    print(f"[AGENT5] context length: {len(context)} chars")

    prompt = f"""You are a senior product strategist. Analyze the signals below from internal meetings,
user research, and competitor analysis.

Your job is to synthesize these into HIGH-LEVEL PRODUCT INSIGHTS — not summaries of problems,
but the deeper patterns, root causes, and strategic implications behind them.

Each insight should connect multiple problems to a single underlying issue.

Return a JSON array where each item has:
- "insight": the core underlying issue in 1-2 sentences (the "why behind the what")
- "supporting_problems": list of 2-4 specific problems that point to this insight
- "evidence": list of 2-3 concrete data points or quotes that validate this insight
- "implication": what this means for the product — what must change or be built (1-2 sentences)
- "priority": "Critical", "High", "Medium", or "Low" based on frequency and impact
- "hypothesis": a testable hypothesis the product team can validate (1 sentence, starts with "If we...")
- "recommended_action": the single most important next step (1 sentence)

Rules:
- Group related problems — don't create one insight per problem
- Focus on root causes, not symptoms
- Be specific and actionable, not generic
- Return ONLY valid JSON array, no explanation

Signals:
{context[:6000]}"""

    result = _ask_json(prompt, max_tokens=2500)
    if not isinstance(result, list):
        result = []

    print(f"[AGENT5] synthesized {len(result)} insights")
    return result
