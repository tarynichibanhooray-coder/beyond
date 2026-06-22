from __future__ import annotations

import asyncio
import json

from agents._client import create_message, get_anthropic_client, parse_json_response
from agents._speak import call_speak, speak_user_block
from prompt_training.prompts import ARABI_REFLECT, ARABI_SPEAK
from config import settings
from utils.locale import apply_locale_system, normalize_locale
from models import ArabiOutput, ConversationLine, TurnContext


def _mock_reflect(ctx: TurnContext) -> ArabiOutput:
    snippet = ctx.transcript.strip()[:100]
    if normalize_locale(ctx.locale) == "es":
        return ArabiOutput(
            disclosure_read=(
                f"Su búsqueda no es un fracaso: \"{snippet}\" "
                "muestra algo más grande moviéndose a través de ellos."
            ),
            barzakh_note="Están en el intermedio mismo—no antes de la vida real, sino dentro de ella.",
            mirror_read="Algo más grande que su historia personal se mueve en este momento.",
            color_intensity=64,
        )
    return ArabiOutput(
        disclosure_read=(
            f"Their searching is not failure: \"{snippet}\" "
            "shows something larger moving through them."
        ),
        barzakh_note="They stand in the in-between itself—not before real life, but inside it.",
        mirror_read="Something larger than their personal story moves through this moment.",
        color_intensity=64,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    if normalize_locale(ctx.locale) == "es":
        return (
            "Ya estás en el intermedio—no en un pasillo hacia otro lugar. "
            "¿Y si este no-saber te está diciendo algo?"
        )
    return (
        "You are already in the in-between—not a hallway on the way somewhere else. "
        "What if this not-knowing is itself telling you something?"
    )


class ArabiAgent:
    member_id = "arabi"

    async def reflect(self, ctx: TurnContext) -> ArabiOutput:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> ArabiOutput:
            msg = create_message(
                client,
                label="arabi.reflect",
                model=settings.anthropic_model,
                max_tokens=280,
                system=apply_locale_system(ARABI_REFLECT, ctx.locale),
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
            return parse_json_response(msg.content[0].text, ArabiOutput)

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
            return call_speak(ARABI_SPEAK, user, label="arabi.speak", locale=ctx.locale)

        return await asyncio.to_thread(_call)
