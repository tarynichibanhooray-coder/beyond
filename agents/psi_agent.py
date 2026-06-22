from __future__ import annotations

import asyncio
import json

from agents._client import get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import MORRISON_SPEAK, PSI_REFLECT
from config import settings
from models import (
    ConversationLine,
    KierkegaardReflection,
    LambdaOutput,
    PsiOutput,
    TurnContext,
)


def _mock_reflect(ctx: TurnContext) -> PsiOutput:
    if not ctx.bpm_window:
        body_note = "No body signal in this window."
    else:
        avg = sum(b for _, b in ctx.bpm_window) / len(ctx.bpm_window)
        body_note = f"Pulse lifts and holds near {avg:.0f} BPM as they speak."
    return PsiOutput(
        witness_read="They are asking to be seen without naming what they need seen.",
        carried_story="Older voices may still be measuring whether they are allowed to be lost.",
        body_signal_note=body_note,
        color_intensity=70,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    n = len(conversation)
    if n == 1:
        return "Blake, your fire is real—but hear the body. This is not abstraction; it is memory in flesh."
    if n == 4:
        return "I will not let us rush past what they carry. Witness first; then let vision and choice meet."
    return "What they said has ancestors. Name them before you ask them to leap."


class PsiAgent:
    async def reflect(self, ctx: TurnContext) -> PsiOutput:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> PsiOutput:
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=280,
                system=PSI_REFLECT,
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": ctx.question,
                                "transcript": ctx.transcript,
                                "bpm_window": ctx.bpm_window,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            return parse_json_response(msg.content[0].text, PsiOutput)

        return await asyncio.to_thread(_call)

    async def speak(
        self,
        ctx: TurnContext,
        blake: LambdaOutput,
        morrison: PsiOutput,
        kierkegaard: KierkegaardReflection,
        conversation: list[ConversationLine],
    ) -> str:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_speak, ctx, conversation)

        user = speak_user_block(ctx, "morrison", blake, morrison, kierkegaard, conversation)

        def _call() -> str:
            return call_speak(MORRISON_SPEAK, user)

        return await asyncio.to_thread(_call)
