from __future__ import annotations

import asyncio
import json

from agents._client import create_message, get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import DELTA_FINAL_SYSTEM, KIERKEGAARD_REFLECT, KIERKEGAARD_SPEAK
from config import settings
from models import (
    ConversationLine,
    DeltaFinal,
    KierkegaardReflection,
    TurnContext,
)


def _mock_reflect(ctx: TurnContext) -> KierkegaardReflection:
    return KierkegaardReflection(
        dread_read=(
            "Something in them is opening toward a life they have not yet claimed—"
            "the dizziness before infinite possibility, not failure."
        ),
        avoided_choice="They hesitate before a good they already recognize.",
        leap_pressure=(
            "Becoming themselves is nearer than they think—and worth trusting, "
            "even when it terrifies."
        ),
        color_intensity=58,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    if len(conversation) == 2:
        return (
            "You both speak truly—and both honor what they carry. "
            "Still, there is a life here only they can choose to inhabit—and that choice "
            "will not feel safe. It will feel like standing at the edge of everything open."
        )
    return (
        "What they love is already showing itself; the question is whether they will trust it "
        "when freedom feels like vertigo, not reassurance."
    )


def _mock_delta_final(history_summary: str) -> DeltaFinal:
    return DeltaFinal(
        final_question="In the time that remains before, what will you choose to be?",
        reasoning=(
            "The session traced vision, what you carry, and the choice you postpone—"
            "at this threshold, only a question of becoming suffices."
        ),
    )


class DeltaAgent:
    member_id = "kierkegaard"

    async def reflect(self, ctx: TurnContext) -> KierkegaardReflection:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> KierkegaardReflection:
            msg = create_message(
                client,
                label="kierkegaard.reflect",
                model=settings.anthropic_model,
                max_tokens=350,
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
        reflections: dict,
        conversation: list[ConversationLine],
    ) -> str:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_speak, ctx, conversation)

        user = speak_user_block(ctx, self.member_id, reflections, conversation)

        def _call() -> str:
            return call_speak(KIERKEGAARD_SPEAK, user, label="kierkegaard.speak", max_tokens=350)

        return await asyncio.to_thread(_call)

    async def final_question(self, history_snippet: str) -> DeltaFinal:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_delta_final, history_snippet)

        def _call() -> DeltaFinal:
            msg = create_message(
                client,
                label="kierkegaard.final",
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
