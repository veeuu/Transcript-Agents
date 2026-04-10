"""
Chat interface for querying stored transcripts via RAG.
Uses Google Gemini 2.5 Flash for response generation.
Usage:
    python chat/chatbot.py
"""

import os
from dotenv import load_dotenv
load_dotenv()
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import google.generativeai as genai
from transcript_pipeline.rag_store import query_rag

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)
_model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")

SYSTEM_PROMPT = """You are an intelligent assistant with access to internal founder meeting transcripts.
You help the team recall decisions, problems, next steps, and insights from past meetings.
Answer based ONLY on the context provided. If the answer isn't in the context, say so clearly.
Be concise and direct."""


def chat(question: str, history: list = None) -> str:
    hits = query_rag(question, n_results=4)

    if not hits:
        return "No relevant transcript data found for your question."

    context = "\n\n---\n\n".join(
        f"[Source: {h['metadata'].get('title', 'Unknown')} | {h['metadata'].get('chunk_type', '')}]\n{h['content']}"
        for h in hits
    )

    prompt = f"{SYSTEM_PROMPT}\n\nContext from transcripts:\n{context}\n\nQuestion: {question}"

    # Gemini doesn't have explicit history format like OpenAI, but we can prepend it
    if history:
        conv = "\n".join([f"{m['role']}: {m['content']}" for m in history])
        prompt = f"Previous conversation:\n{conv}\n\n{prompt}"

    response = _model.generate_content(prompt)
    return response.text.strip()


def run_chat_loop():
    print("Transcript Chat â€” type 'exit' to quit\n")
    history = []

    while True:
        question = input("You: ").strip()
        if question.lower() in ("exit", "quit"):
            break
        if not question:
            continue

        answer = chat(question, history)
        print(f"\nAssistant: {answer}\n")

        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    run_chat_loop()

