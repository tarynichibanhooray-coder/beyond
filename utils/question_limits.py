from __future__ import annotations

import re


_SENTENCE_RE = re.compile(r".+?(?:[.!?]+|[。！？]+)(?=\s|$)", re.DOTALL)


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
