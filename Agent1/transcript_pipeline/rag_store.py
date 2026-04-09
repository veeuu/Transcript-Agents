"""
RAG Store: Embeds and stores analyzed transcripts in ChromaDB.
Uses Google Gemini embedding model for vectorization.
Each transcript is chunked by section for fine-grained retrieval.
"""

import json
import os
from dotenv import load_dotenv
load_dotenv()
import hashlib
from typing import Dict, Any, List

import chromadb
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
genai.configure(api_key=GEMINI_API_KEY)

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "chroma_db")
EMBED_MODEL = "models/gemini-embedding-001"


def _embed(texts: List[str]) -> List[List[float]]:
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=texts,
        task_type="retrieval_document"
    )
    return result["embedding"] if isinstance(texts, str) else result["embedding"]


def _embed_query(text: str) -> List[float]:
    result = genai.embed_content(
        model=EMBED_MODEL,
        content=text,
        task_type="retrieval_query"
    )
    return result["embedding"]


def _get_collection():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    # Use raw collection without built-in embedding fn â€” we supply our own
    return client.get_or_create_collection(name="transcripts")


def _make_id(text: str) -> str:
    return hashlib.md5(text.encode()).hexdigest()


def store_transcript(structured: Dict[str, Any], analysis: Dict[str, Any]) -> str:
    collection = _get_collection()
    meta = structured["metadata"]
    transcript_id = _make_id(meta["title"] + meta["topic"])

    documents: List[str] = []
    ids: List[str] = []
    metadatas: List[dict] = []

    # Chunk 1: full analysis summary
    summary_doc = json.dumps({
        "type": "analysis_summary",
        "title": analysis.get("title"),
        "summary": analysis.get("summary"),
        "major_decisions": analysis.get("major_decisions"),
        "problems_identified": analysis.get("problems_identified"),
        "solutions_pitched": analysis.get("solutions_pitched"),
        "next_steps": analysis.get("next_steps"),
        "improvements_for_next_call": analysis.get("improvements_for_next_call"),
        "decision_making_insights": analysis.get("decision_making_insights"),
        "tone": analysis.get("tone"),
    }, indent=2)

    documents.append(summary_doc)
    ids.append(f"{transcript_id}_summary")
    metadatas.append({
        "transcript_id": transcript_id,
        "chunk_type": "summary",
        "title": meta["title"],
        "topic": meta["topic"],
        "duration": meta["duration"],
    })

    # Chunk per section
    for section_name, turns in structured["sections"].items():
        section_text = f"Section: {section_name}\n"
        for t in turns:
            section_text += f"{t['speaker']} ({t['role']}): {t['text']}\n"
        documents.append(section_text)
        ids.append(f"{transcript_id}_{_make_id(section_name)}")
        metadatas.append({
            "transcript_id": transcript_id,
            "chunk_type": "section",
            "section": section_name,
            "title": meta["title"],
            "topic": meta["topic"],
        })

    embeddings = _embed(documents)
    collection.upsert(documents=documents, ids=ids, metadatas=metadatas, embeddings=embeddings)
    print(f"[RAG] Stored {len(documents)} chunks for: {meta['title']}")
    return transcript_id


def query_rag(question: str, n_results: int = 4) -> List[Dict[str, Any]]:
    collection = _get_collection()
    q_embedding = _embed_query(question)

    results = collection.query(
        query_embeddings=[q_embedding],
        n_results=n_results,
        include=["documents", "metadatas", "distances"]
    )

    hits = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        hits.append({"content": doc, "metadata": meta, "score": round(1 - dist, 4)})

    return hits

