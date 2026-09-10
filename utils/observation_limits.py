"""Keep displayed council observations short and particular."""

from __future__ import annotations

import re

_SENTENCE_RE = re.compile(r".+?(?:[.!?]+|[。！？]+)(?=\s|$)", re.DOTALL)
_CLAUSE_RE = re.compile(r"\s*[—;–]\s*")

MAX_OBSERVATION_SENTENCES = 2
MAX_OBSERVATION_WORDS = 40


def clamp_observation(
    text: str,
    max_sentences: int = MAX_OBSERVATION_SENTENCES,
    max_words: int = MAX_OBSERVATION_WORDS,
) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned or max_sentences <= 0:
        return cleaned

    sentences = [match.group(0).strip() for match in _SENTENCE_RE.finditer(cleaned)]
    if not sentences:
        sentences = [part.strip() for part in _CLAUSE_RE.split(cleaned, maxsplit=1) if part.strip()]
        if len(sentences) > 1:
            sentences[0] = sentences[0].rstrip("—,;–") + "."
    clipped = " ".join(sentences[:max_sentences]).strip() or cleaned

    words = clipped.split()
    if len(words) > max_words:
        clipped = " ".join(words[:max_words]).rstrip(",;:—–-") + "."
    return clipped


DISPLAY_FIELDS = {
    "arabi": "disclosure_read",
    "blake": "vision_read",
    "morrison": "witness_read",
    "kierkegaard": "dread_read",
}


def clamp_reflection_display(member_id: str, reflection: dict) -> dict:
    field = DISPLAY_FIELDS.get(member_id)
    if not field or not isinstance(reflection, dict):
        return reflection
    value = reflection.get(field)
    if not isinstance(value, str):
        return reflection
    clamped = {**reflection, field: clamp_observation(value)}
    return clamped
