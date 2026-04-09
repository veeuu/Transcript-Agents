"""
Main pipeline orchestrator.
Usage:
    python -m transcript_pipeline.pipeline --input data/sample_transcript.txt
    python -m transcript_pipeline.pipeline --audio path/to/audio.mp3
"""

import argparse
import json
import os

from .extractor import extract_from_text, extract_from_audio
from .structurer import structure_transcript
from .analyzer import analyze
from .rag_store import store_transcript


def run_pipeline(text: str, save_output: bool = True) -> dict:
    print("[1/4] Extracting transcript...")
    raw = extract_from_text(text)

    print("[2/4] Structuring transcript...")
    structured = structure_transcript(raw)

    print("[3/4] Analyzing with LLM...")
    analysis = analyze(structured)

    print("[4/4] Storing in RAG...")
    transcript_id = store_transcript(structured, analysis)

    result = {
        "transcript_id": transcript_id,
        "structured": structured,
        "analysis": analysis,
    }

    if save_output:
        out_path = os.path.join("data", f"{transcript_id}_output.json")
        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[Done] Output saved to {out_path}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Transcript Analysis Pipeline")
    parser.add_argument("--input", type=str, help="Path to .txt transcript file")
    parser.add_argument("--audio", type=str, help="Path to audio file (mp3/wav)")
    args = parser.parse_args()

    if args.audio:
        print(f"[Audio] Transcribing {args.audio}...")
        text = extract_from_audio(args.audio)
    elif args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        parser.print_help()
        return

    run_pipeline(text)


if __name__ == "__main__":
    main()
