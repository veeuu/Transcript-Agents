"""
Step 1: Extract raw content from transcript text or audio file.
Supports .txt input directly; audio support via whisper (optional).
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Turn:
    speaker: str
    role: str
    timestamp_block: str
    section: str
    text: str


@dataclass
class RawTranscript:
    title: str
    participants: List[dict]
    duration: str
    topic: str
    turns: List[Turn]


# Maps speaker first name -> role from participant header
def _parse_participants(header_text: str) -> dict:
    mapping = {}
    for line in header_text.splitlines():
        m = re.match(r"\*?\s*(\w+)\s*\(([^)]+)\)", line)
        if m:
            mapping[m.group(1).strip()] = m.group(2).strip()
    return mapping


def extract_from_text(raw_text: str) -> RawTranscript:
    lines = raw_text.strip().splitlines()

    title = lines[0].replace("Transcript:", "").strip()
    duration, topic = "", ""
    participant_block = []
    in_participants = False

    for line in lines:
        if line.strip().lower().startswith("duration:"):
            duration = line.split(":", 1)[1].strip()
        elif line.strip().lower().startswith("topic:"):
            topic = line.split(":", 1)[1].strip()
        elif line.strip().lower().startswith("participants:"):
            in_participants = True
        elif in_participants and line.strip().startswith("*"):
            participant_block.append(line)
        elif in_participants and line.strip() == "":
            in_participants = False

    role_map = _parse_participants("\n".join(participant_block))
    participants = [{"name": k, "role": v} for k, v in role_map.items()]

    # Parse turns
    section_pattern = re.compile(r"^\[(\d+:\d+\s*-\s*\d+:\d+)\]\s+(.+)$")
    speaker_pattern = re.compile(r"^([A-Z][a-z]+):\s+(.+)$")

    turns: List[Turn] = []
    current_section = ""
    current_timestamp = ""

    for line in lines:
        line = line.strip()
        sec_match = section_pattern.match(line)
        if sec_match:
            current_timestamp = sec_match.group(1)
            current_section = sec_match.group(2)
            continue

        spk_match = speaker_pattern.match(line)
        if spk_match:
            name = spk_match.group(1)
            text = spk_match.group(2)
            role = role_map.get(name, "Unknown")
            turns.append(Turn(
                speaker=name,
                role=role,
                timestamp_block=current_timestamp,
                section=current_section,
                text=text
            ))

    return RawTranscript(
        title=title,
        participants=participants,
        duration=duration,
        topic=topic,
        turns=turns
    )


def extract_from_audio(audio_path: str) -> str:
    """
    Transcribe audio to text using OpenAI Whisper.
    Requires: pip install openai-whisper
    """
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return result["text"]
    except ImportError:
        raise RuntimeError("whisper not installed. Run: pip install openai-whisper")
