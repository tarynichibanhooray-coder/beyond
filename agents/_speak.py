from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from agents._client import create_message, get_anthropic_client, parse_json_response
from config import settings
from models import ConversationLine, TurnContext


class SpeakLine(BaseModel):
    line: str


def _reflections_payload(
    speaker: str,
    reflections: dict[str, Any],
) -> dict[str, Any]:
    others = {k: v for k, v in reflections.items() if k != speaker}
    return {
        "your_reflection": reflections[speaker],
        "others_reflections": others,
    }


def speak_user_block(
    ctx: TurnContext,
    speaker: str,
    reflections: dict[str, Any],
    conversation: list[ConversationLine],
) -> str:
    return json.dumps(
        {
            "question": ctx.question,
            "participant_answer": ctx.transcript,
            **_reflections_payload(speaker, reflections),
            "conversation_so_far": [c.model_dump() for c in conversation],
        },
        ensure_ascii=False,
    )


def call_speak(
    system: str,
    user_content: str,
    *,
    label: str = "council.speak",
    max_tokens: int = 180,
) -> str:
    client = get_anthropic_client()
    if client is None:
        raise RuntimeError("mock should not call call_speak")
    msg = create_message(
        client,
        label=label,
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    text = msg.content[0].text
    return parse_json_response(text, SpeakLine).line.strip()
