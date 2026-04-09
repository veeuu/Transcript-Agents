"""
FastAPI app with Swagger UI.
Endpoints:
  POST /pipeline/run     - Run full pipeline on a text transcript
  POST /pipeline/audio   - Run pipeline on an uploaded audio file
  POST /chat             - Chat with stored transcripts via RAG
  GET  /health           - Health check
  GET  /transcripts      - List stored transcript IDs from ChromaDB
"""

import os
import sys
from dotenv import load_dotenv
load_dotenv()
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from transcript_pipeline.extractor import extract_from_text, extract_from_audio
from transcript_pipeline.structurer import structure_transcript
from transcript_pipeline.analyzer import analyze
from transcript_pipeline.rag_store import store_transcript, query_rag
from chat.chatbot import chat

app = FastAPI(
    title="Transcript Intelligence API",
    description=(
        "Pipeline to ingest founder meeting transcripts (text or audio), "
        "analyze them with Gemini 2.5 Flash, store in RAG (ChromaDB), "
        "and expose a chat interface for decision-making queries."
    ),
    version="1.0.0",
    docs_url="/docs",       # Swagger UI
    redoc_url="/redoc",     # ReDoc UI
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# â”€â”€ Request / Response Models â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TranscriptTextRequest(BaseModel):
    text: str

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Transcript: Vertex Founders Strategy Session\nParticipants:\n* Alex (CEO): Strategy and Vision\n..."
            }
        }


class ChatRequest(BaseModel):
    question: str
    history: Optional[List[dict]] = []

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What decisions were made in the last meeting?",
                "history": []
            }
        }


class ChatResponse(BaseModel):
    answer: str
    sources: List[dict]


class PipelineResponse(BaseModel):
    transcript_id: str
    metadata: dict
    analysis: dict


class HealthResponse(BaseModel):
    status: str
    gemini_key_set: bool
    chroma_path: str


# â”€â”€ Routes â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Check API health and configuration status."""
    from transcript_pipeline.rag_store import CHROMA_PATH
    return {
        "status": "ok",
        "gemini_key_set": bool(os.environ.get("GEMINI_API_KEY", "")),
        "chroma_path": CHROMA_PATH,
    }


@app.post("/pipeline/run", response_model=PipelineResponse, tags=["Pipeline"])
def run_pipeline_text(req: TranscriptTextRequest):
    """
    Run the full 4-step pipeline on a raw text transcript.

    Steps:
    1. Extract speakers, sections, turns
    2. Structure into formatted schema
    3. Analyze with Gemini 2.5 Flash (decisions, problems, next steps, tone)
    4. Store chunks in ChromaDB RAG
    """
    try:
        raw = extract_from_text(req.text)
        structured = structure_transcript(raw)
        analysis = analyze(structured)
        transcript_id = store_transcript(structured, analysis)
        return {
            "transcript_id": transcript_id,
            "metadata": structured["metadata"],
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/pipeline/audio", response_model=PipelineResponse, tags=["Pipeline"])
async def run_pipeline_audio(file: UploadFile = File(..., description="Audio file (mp3, wav, m4a)")):
    """
    Upload an audio file, transcribe with Whisper, then run the full pipeline.
    Requires: pip install openai-whisper
    """
    try:
        suffix = os.path.splitext(file.filename)[1] or ".mp3"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        text = extract_from_audio(tmp_path)
        os.unlink(tmp_path)

        raw = extract_from_text(text)
        structured = structure_transcript(raw)
        analysis = analyze(structured)
        transcript_id = store_transcript(structured, analysis)

        return {
            "transcript_id": transcript_id,
            "metadata": structured["metadata"],
            "analysis": analysis,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat_endpoint(req: ChatRequest):
    """
    Ask a question about stored transcripts.
    Returns an answer from Gemini 2.5 Flash grounded in RAG context,
    plus the source chunks used.
    """
    try:
        hits = query_rag(req.question, n_results=4)
        if not hits:
            return {"answer": "No relevant transcript data found.", "sources": []}

        answer = chat(req.question, req.history)
        sources = [
            {
                "title": h["metadata"].get("title"),
                "chunk_type": h["metadata"].get("chunk_type"),
                "section": h["metadata"].get("section", ""),
                "score": h["score"],
            }
            for h in hits
        ]
        return {"answer": answer, "sources": sources}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/transcripts", tags=["System"])
def list_transcripts():
    """
    List all transcript IDs and titles stored in ChromaDB.
    """
    try:
        import chromadb
        from transcript_pipeline.rag_store import CHROMA_PATH
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_or_create_collection("transcripts")
        results = collection.get(include=["metadatas"])
        seen = {}
        for meta in results["metadatas"]:
            tid = meta.get("transcript_id")
            if tid and tid not in seen:
                seen[tid] = {"transcript_id": tid, "title": meta.get("title"), "topic": meta.get("topic")}
        return {"transcripts": list(seen.values()), "total": len(seen)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

