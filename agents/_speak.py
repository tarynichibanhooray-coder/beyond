from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel

from agents._client import get_anthropic_client, parse_json_response
from config import settings
from models import (
    AskerName,
    ConversationLine,
    KierkegaardReflection,
    LambdaOutput,
    PsiOutput,
    TurnContext,
)


class SpeakLine(BaseModel):
    line: str


def _reflections_payload(
    speaker: AskerName,
    blake: LambdaOutput,
    morrison: PsiOutput,
    kierkegaard: KierkegaardReflection,
) -> dict[str, Any]:
    all_r = {
        "blake": blake.model_dump(),
        "morrison": morrison.model_dump(),
        "kierkegaard": kierkegaard.model_dump(),
    }
    others = {k: v for k, v in all_r.items() if k != speaker}
    return {"your_reflection": all_r[speaker], "others_reflections": others}


def speak_user_block(
    ctx: TurnContext,
    speaker: AskerName,
    blake: LambdaOutput,
    morrison: PsiOutput,
    kierkegaard: KierkegaardReflection,
    conversation: list[ConversationLine],
) -> str:
    return json.dumps(
        {
            "question": ctx.question,
            "participant_answer": ctx.transcript,
            "bpm_window": ctx.bpm_window,
            **_reflections_payload(speaker, blake, morrison, kierkegaard),
            "conversation_so_far": [c.model_dump() for c in conversation],
        },
        ensure_ascii=False,
    )


def call_speak(system: str, user_content: str) -> str:
    client = get_anthropic_client()
    if client is None:
        raise RuntimeError("mock should not call call_speak")
    msg = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=180,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    text = msg.content[0].text
    return parse_json_response(text, SpeakLine).line.strip()
