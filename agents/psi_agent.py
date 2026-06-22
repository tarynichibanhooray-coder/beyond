from __future__ import annotations

import asyncio
import json

from agents._client import create_message, get_anthropic_client, parse_json_response
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
    return PsiOutput(
        witness_read="They are asking to be seen without naming what they need seen.",
        carried_story="Older voices may still be measuring whether they are allowed to be lost.",
        color_intensity=70,
    )


def _mock_speak(
    ctx: TurnContext,
    conversation: list[ConversationLine],
) -> str:
    if len(conversation) == 1:
        prior = conversation[0].speaker
        if prior == "arabi":
            return (
                "Arabi, you would widen them into the threshold—but they stand on what "
                "their people carried. You do not transcend that; you integrate it, or you leave them orphaned."
            )
        return (
            "Blake, you would burn the past to see—but they stand on what their people "
            "carried. You do not transcend that; you integrate it, or you leave them orphaned."
        )
    return "What they said has ancestors. Name them before you ask them to leap."


class PsiAgent:
    member_id = "morrison"

    async def reflect(self, ctx: TurnContext) -> PsiOutput:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_reflect, ctx)

        def _call() -> PsiOutput:
            msg = create_message(
                client,
                label="morrison.reflect",
                model=settings.anthropic_model,
                max_tokens=350,
                system=PSI_REFLECT,
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
            return parse_json_response(msg.content[0].text, PsiOutput)

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
            return call_speak(MORRISON_SPEAK, user, label="morrison.speak", max_tokens=350)

        return await asyncio.to_thread(_call)
