"""Detect when a participant needs a clearer question and rephrase in plain language."""

from __future__ import annotations

import asyncio
import json
import re

from agents._client import create_message, get_anthropic_client
from config import settings
from utils.locale import REPHRASE_SYSTEM, normalize_locale

_CONFUSION_PHRASES = (
    "don't understand",
    "dont understand",
    "do not understand",
    "don't get",
    "dont get",
    "do not get",
    "what do you mean",
    "what does that mean",
    "what does this mean",
    "doesn't make sense",
    "doesnt make sense",
    "confused",
    "not sure what you",
    "not sure what that",
    "can you rephrase",
    "could you rephrase",
    "say that again",
    "say it again",
    "simpler",
    "more simply",
    "plain english",
    "too abstract",
    "what are you asking",
    "i don't know what you're asking",
    "i dont know what youre asking",
    "no entiendo",
    "no comprendo",
    "qué quieres decir",
    "que quieres decir",
    "qué significa",
    "que significa",
    "no tiene sentido",
    "estoy confundido",
    "estoy confundida",
    "más simple",
    "mas simple",
    "más sencillo",
    "mas sencillo",
    "puedes reformular",
    "puede reformular",
    "repítelo",
    "repitelo",
    "no sé qué preguntas",
    "no se que preguntas",
)


def is_confusion_transcript(transcript: str) -> bool:
    text = transcript.strip().lower()
    if not text:
        return False
    if any(phrase in text for phrase in _CONFUSION_PHRASES):
        return True
    if len(text) <= 48 and re.search(r"^(huh|what|sorry|\?+)$", text):
        return True
    return False


def _mock_rephrase(question: str, locale: str = "en") -> str:
    q = question.strip()
    simplified = re.sub(r"\s*—\s*", ", ", q)
    simplified = re.sub(r"\s+", " ", simplified)
    if len(simplified) > 100:
        parts = simplified.split("?")
        simplified = parts[0].strip() + "?"
    if normalize_locale(locale) == "es":
        templates = {
            "¿Qué te trajo aquí?": "¿Qué te hizo querer estar aquí hoy?",
        }
        if simplified in templates:
            return templates[simplified]
        return f"Déjame preguntarlo de forma más simple: {simplified}"
    templates = {
        "What brought you here?": "What made you want to be here today?",
    }
    if simplified in templates:
        return templates[simplified]
    return f"Let me ask that more simply: {simplified}"


async def rephrase_question(question: str, transcript: str, locale: str = "en") -> str:
    client = get_anthropic_client()
    if client is None:
        return _mock_rephrase(question, locale)

    loc = normalize_locale(locale)

    def _call() -> str:
        msg = create_message(
            client,
            label="question.rephrase",
            model=settings.anthropic_model,
            max_tokens=120,
            system=REPHRASE_SYSTEM[loc],
            messages=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "original_question": question,
                            "participant_said": transcript,
                            "locale": loc,
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
        )
        text = msg.content[0].text.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1].strip()
        return text or _mock_rephrase(question, locale)

    return await asyncio.to_thread(_call)
