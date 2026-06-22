from __future__ import annotations

import asyncio
import json

from agents._client import create_message, get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import BLAKE_SPEAK, LAMBDA_REFLECT
from config import settings
from utils.locale import apply_locale_system, normalize_locale
from models import (
    ConversationLine,
    PsiOutput,
    TurnContext,
)


def _mock_reflect(ctx: TurnContext) -> LambdaOutput:
    snippet = ctx.transcript[:100] if len(ctx.transcript) > 100 else ctx.transcript
    if normalize_locale(ctx.locale) == "es":
        return LambdaOutput(
            vision_read=f"Una visión se tensa bajo sus palabras: {snippet}",
            symbols=["umbral", "fuego", "ojo"],
            blocked_imagination="No mirarán hasta que el camino sea cierto.",
            color_intensity=62,
        )
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
    if normalize_locale(ctx.locale) == "es":
        return (
            "Veo una imagen intentando nacer en lo que dijeron—"
            "el ojo interior abriéndose, no a pesar del pasado sino a través del fuego."
        )
    return "I see an image trying to be born in what they said—the inner eye opening, not despite the past but through fire."


class LambdaAgent:
    member_id = "blake"

    async def reflect(self, ctx: TurnContext) -> LambdaOutput:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> LambdaOutput:
            msg = create_message(
                client,
                label="blake.reflect",
                model=settings.anthropic_model,
                max_tokens=280,
                system=apply_locale_system(LAMBDA_REFLECT, ctx.locale),
                messages=[
                    {
                        "role": "user",
                        "content": json.dumps(
                            {
                                "question": ctx.question,
                                "transcript": ctx.transcript,
                                "locale": normalize_locale(ctx.locale),
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
        reflections: dict,
        conversation: list[ConversationLine],
    ) -> str:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_speak, ctx, conversation)

        user = speak_user_block(ctx, self.member_id, reflections, conversation)

        def _call() -> str:
            return call_speak(BLAKE_SPEAK, user, label="blake.speak", locale=ctx.locale)

        return await asyncio.to_thread(_call)
