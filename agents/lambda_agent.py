from __future__ import annotations

import asyncio
import json

from agents._client import get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import BLAKE_SPEAK, LAMBDA_REFLECT
from config import settings
from models import (
    ConversationLine,
    KierkegaardReflection,
    LambdaOutput,
    PsiOutput,
    TurnContext,
)


def _mock_reflect(ctx: TurnContext) -> LambdaOutput:
    return LambdaOutput(
        vision_read=(
            f"A vision strains beneath their words: {ctx.transcript[:100]}"
            if len(ctx.transcript) > 100
            else f"A vision strains beneath their words: {ctx.transcript}"
        ),
        symbols=["threshold", "fire", "eye"],
        blocked_imagination="They will not look until the path is certain.",
        color_intensity=62,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    n = len(conversation)
    if n == 0:
        return "I see an image trying to be born in what they said, but fear keeps closing the inner eye."
    if n == 3:
        return "Morrison names the wound; I name the fire. Both are true. Imagination is not escape—it is arrival."
    return "Do not ask the world to be safe before you see."


class LambdaAgent:
    async def reflect(self, ctx: TurnContext) -> LambdaOutput:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> LambdaOutput:
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=280,
                system=LAMBDA_REFLECT,
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
            return parse_json_response(msg.content[0].text, LambdaOutput)

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

        user = speak_user_block(ctx, "blake", blake, morrison, kierkegaard, conversation)

        def _call() -> str:
            return call_speak(BLAKE_SPEAK, user)

        return await asyncio.to_thread(_call)
