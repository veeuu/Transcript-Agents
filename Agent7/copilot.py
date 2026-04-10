"""
Agent 7 — Founder Copilot
A conversational query interface over all agent outputs.
Answers founder questions with direct answers, evidence, and confidence levels.

Inputs: Agent 1 (transcript), Agent 4 (problems), Agent 5 (insights), Agent 6 (features)
"""

import os
import json
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

load_dotenv()

HF_TOKEN = os.environ.get("HF_TOKEN", "")
HF_MODEL = "Qwen/Qwen2.5-72B-Instruct"
_client = InferenceClient(api_key=HF_TOKEN)

# In-memory context store — loaded once, reused across queries
_context_cache: dict = {}


# ── LLM helper ────────────────────────────────────────────────────────────────

def _ask(prompt: str, max_tokens: int = 1000) -> str:
    try:
        resp = _client.chat_completion(
            model=HF_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=0.2,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[HF ERROR] {e}")
        return ""


def _ask_json(prompt: str, max_tokens: int = 1000) -> dict:
    raw = _ask(prompt, max_tokens)
    if "```" in raw:
        for part in raw.split("```"):
            part = part.strip().lstrip("json").strip()
            if part.startswith("{"):
                raw = part
                break
    try:
        return json.loads(raw.strip())
    except Exception:
        return {"answer": raw, "evidence": [], "confidence": "Medium"}


# ── Context builder ───────────────────────────────────────────────────────────

def _summarize_agent1(data) -> str:
    if isinstance(data, list):
        return "\n".join(_summarize_agent1(d) for d in data if isinstance(d, dict))
    a = data.get("analysis", data)
    lines = [f"[INTERNAL] {a.get('summary', '')}"]
    for p in a.get("problems_identified", []):
        lines.append(f"  Internal problem: {p}")
    for d in a.get("major_decisions", []):
        lines.append(f"  Decision: {d}")
    for n in a.get("next_steps", []):
        lines.append(f"  Next step: {n}")
    return "\n".join(lines)


def _summarize_agent4(data) -> str:
    if isinstance(data, list):
        return "\n".join(_summarize_agent4(d) for d in data if isinstance(d, dict))
    lines = ["[USER PROBLEMS]"]
    for p in data.get("problems", []):
        lines.append(f"  [{p.get('frequency','?')} freq | {p.get('user_type','?')}] {p.get('problem','')}")
        lines.append(f"    Sources: {', '.join(p.get('source_mix', []))}")
        for e in p.get("evidence", [])[:2]:
            lines.append(f"    Evidence: {e[:150]}")
    return "\n".join(lines)


def _summarize_agent5(data) -> str:
    if isinstance(data, list):
        return "\n".join(_summarize_agent5(d) for d in data if isinstance(d, dict))
    lines = ["[INSIGHTS]"]
    for ins in data.get("insights", []):
        lines.append(f"  [{ins.get('priority','?')}] {ins.get('insight','')}")
        lines.append(f"    Implication: {ins.get('implication','')}")
        lines.append(f"    Action: {ins.get('recommended_action','')}")
        lines.append(f"    Hypothesis: {ins.get('hypothesis','')}")
    return "\n".join(lines)


def _summarize_agent6(data) -> str:
    if isinstance(data, list):
        return "\n".join(_summarize_agent6(d) for d in data if isinstance(d, dict))
    lines = ["[PRODUCT FEATURES]"]
    for f in data.get("features", []):
        lines.append(f"  [{f.get('priority','?')} | {f.get('effort','?')} effort] {f.get('feature_name','')}")
        lines.append(f"    Problem: {f.get('problem','')}")
        lines.append(f"    Impact: {f.get('expected_impact','')}")
        lines.append(f"    For: {f.get('target_user','')}")
    return "\n".join(lines)


def build_context(agent1=None, agent4=None, agent5=None, agent6=None) -> str:
    parts = []
    if agent1: parts.append(_summarize_agent1(agent1))
    if agent4: parts.append(_summarize_agent4(agent4))
    if agent5: parts.append(_summarize_agent5(agent5))
    if agent6: parts.append(_summarize_agent6(agent6))
    return "\n\n".join(parts)


# ── Query engine ──────────────────────────────────────────────────────────────

def query(question: str, context: str) -> dict:
    """
    Answer a founder question using the full context from all agents.
    Returns: answer, evidence, confidence, follow_up_questions
    """
    prompt = f"""You are a Founder Copilot — an AI assistant helping a startup founder make fast, high-quality product decisions.

You have access to research data from multiple sources:
- Internal meeting transcripts
- Validated user problems (with frequency and user type)
- Product insights (with root causes and implications)
- Product feature briefs (with priority and effort)

Answer the founder's question directly and concisely.

Return a JSON object with:
- "answer": direct, specific answer to the question (2-4 sentences max)
- "evidence": list of 2-4 specific data points from the context that support the answer
- "confidence": "High", "Medium", or "Low" based on how well the data supports the answer
- "follow_up_questions": list of 2-3 related questions the founder should also consider

Return ONLY valid JSON, no explanation.

Context:
{context[:5000]}

Founder's Question: {question}"""

    return _ask_json(prompt, max_tokens=800)


# ── Context loader ────────────────────────────────────────────────────────────

def load_context_from_files(
    agent1_file: str = None,
    agent4_file: str = None,
    agent5_file: str = None,
    agent6_file: str = None,
    workspace_root: str = ".",
) -> str:
    def load(path):
        if not path:
            return None
        if not os.path.isabs(path):
            path = os.path.join(workspace_root, path)
        path = os.path.normpath(path)
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            objects, idx = [], 0
            while idx < len(content):
                chunk = content[idx:].lstrip()
                if not chunk: break
                idx += len(content[idx:]) - len(chunk)
                try:
                    obj, end = decoder.raw_decode(chunk)
                    objects.append(obj)
                    idx += end
                except json.JSONDecodeError:
                    idx += 1
            return objects if len(objects) > 1 else (objects[0] if objects else None)

    return build_context(
        agent1=load(agent1_file),
        agent4=load(agent4_file),
        agent5=load(agent5_file),
        agent6=load(agent6_file),
    )
