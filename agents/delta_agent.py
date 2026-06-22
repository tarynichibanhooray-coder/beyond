from __future__ import annotations

import asyncio
import json

from agents._client import get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import DELTA_FINAL_SYSTEM, KIERKEGAARD_REFLECT, KIERKEGAARD_SPEAK
from config import settings
from models import (
    ConversationLine,
    DeltaFinal,
    KierkegaardReflection,
    LambdaOutput,
    PsiOutput,
    TurnContext,
)


def _mock_reflect(ctx: TurnContext) -> KierkegaardReflection:
    return KierkegaardReflection(
        dread_read="They stand at the edge of freedom and call it confusion.",
        avoided_choice="They wait for certainty before they will choose themselves.",
        leap_pressure="The leap is not information; it is commitment in the dark.",
        color_intensity=58,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    n = len(conversation)
    if n == 2:
        return "You both speak truly. But the participant is frozen between vision and wound—between what they see and what they carry."
    if n == 5:
        return "Enough circling. One of us must ask, and the question must cost them something true."
    return "The anxiety they feel is not a flaw—it is the sign that they are finally free to choose."


def _mock_delta_final(history_summary: str) -> DeltaFinal:
    return DeltaFinal(
        final_question="In the time that remains before, what will you choose to be?",
        reasoning=(
            "The session traced vision, what you carry, and the choice you postpone—"
            "at this threshold, only a question of becoming suffices."
        ),
    )


class DeltaAgent:
    async def reflect(self, ctx: TurnContext) -> KierkegaardReflection:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> KierkegaardReflection:
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=280,
                system=KIERKEGAARD_REFLECT,
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": ctx.question,
                                "transcript": ctx.transcript,
                            },
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            return parse_json_response(msg.content[0].text, KierkegaardReflection)

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

        user = speak_user_block(ctx, "kierkegaard", blake, morrison, kierkegaard, conversation)

        def _call() -> str:
            return call_speak(KIERKEGAARD_SPEAK, user)

        return await asyncio.to_thread(_call)

    async def final_question(self, history_snippet: str) -> DeltaFinal:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_delta_final, history_snippet)

        def _call() -> DeltaFinal:
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=400,
                system=DELTA_FINAL_SYSTEM,
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"full_session": history_snippet},
                            ensure_ascii=False,
                        ),
                    },
                ],
            )
            return parse_json_response(msg.content[0].text, DeltaFinal)

        return await asyncio.to_thread(_call)
