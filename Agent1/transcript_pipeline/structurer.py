"""
Step 2: Structure the raw transcript into a clean, formatted schema.
Produces a StructuredTranscript dict ready for analysis and storage.
"""

from typing import List, Dict, Any
from .extractor import RawTranscript


def structure_transcript(raw: RawTranscript) -> Dict[str, Any]:
    """
    Converts RawTranscript into a structured dict with:
    - metadata
    - timeline of sections
    - per-speaker contribution summary
    - full formatted dialogue
    """
    sections: Dict[str, List[dict]] = {}
    speaker_stats: Dict[str, int] = {}

    for turn in raw.turns:
        sec = turn.section or "General"
        if sec not in sections:
            sections[sec] = []
        sections[sec].append({
            "speaker": turn.speaker,
            "role": turn.role,
            "text": turn.text,
            "timestamp_block": turn.timestamp_block,
        })
        speaker_stats[turn.speaker] = speaker_stats.get(turn.speaker, 0) + 1

    timeline = []
    seen_ts = {}
    for turn in raw.turns:
        ts = turn.timestamp_block
        if ts and ts not in seen_ts:
            seen_ts[ts] = turn.section
            timeline.append({"timestamp": ts, "section": turn.section})

    formatted_dialogue = []
    for turn in raw.turns:
        formatted_dialogue.append(
            f"[{turn.timestamp_block}] [{turn.section}]\n"
            f"{turn.speaker} ({turn.role}): {turn.text}"
        )

    return {
        "metadata": {
            "title": raw.title,
            "topic": raw.topic,
            "duration": raw.duration,
            "participants": raw.participants,
            "total_turns": len(raw.turns),
        },
        "timeline": timeline,
        "sections": sections,
        "speaker_contribution": speaker_stats,
        "formatted_dialogue": "\n\n".join(formatted_dialogue),
    }
