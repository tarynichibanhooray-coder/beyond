from __future__ import annotations

import re


_SENTENCE_RE = re.compile(r".+?(?:[.!?]+|[。！？]+)(?=\s|$)", re.DOTALL)
_TITLE_ECHO_RE = re.compile(
    r"(?i)\b(?:"
    r"in this time before|"
    r"this time before|"
    r"in the time that remains before|"
    r"the time that remains before|"
    r"en este tiempo previo|"
    r"en el tiempo que queda antes|"
    r"el tiempo que queda antes"
    r")\b"
)


def limit_question_sentences(text: str, max_sentences: int = 2) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned or max_sentences <= 0:
        return cleaned

    matches = list(_SENTENCE_RE.finditer(cleaned))
    sentences = [match.group(0).strip() for match in matches]
    if len(sentences) < max_sentences:
        return cleaned
    if len(sentences) == max_sentences and matches[-1].end() == len(cleaned):
        return cleaned
    return " ".join(sentences[:max_sentences])


def scrub_title_echo(text: str) -> str:
    """Remove installation-title recitation from a participant-facing question."""
    cleaned = _TITLE_ECHO_RE.sub("", text or "")
    cleaned = re.sub(r"\s*,\s*,+", ",", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s+([?!.])", r"\1", cleaned)
    cleaned = re.sub(r"^[\s,;:—.–-]+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;:—")
    if cleaned:
        cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned
