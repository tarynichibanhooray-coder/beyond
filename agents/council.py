from __future__ import annotations

import asyncio
import json

from agents._client import get_anthropic_client, parse_json_response
from agents.delta_agent import DeltaAgent
from agents.lambda_agent import LambdaAgent
from prompt_training.prompts import COUNCIL_DECIDE
from agents.psi_agent import PsiAgent
from config import settings
from models import (
    AskerName,
    ConversationLine,
    CouncilDecision,
    CouncilTurnResult,
    TurnContext,
)

# Two full rounds: Blake → Morrison → Kierkegaard → Blake → Morrison → Kierkegaard
SPEAK_ORDER: list[AskerName] = [
    "blake",
    "morrison",
    "kierkegaard",
    "blake",
    "morrison",
    "kierkegaard",
]

DISPLAY_NAMES = {
    "blake": "William Blake",
    "morrison": "Toni Morrison",
    "kierkegaard": "Søren Kierkegaard",
}


def _mock_decide(ctx: TurnContext, conversation: list[ConversationLine]) -> CouncilDecision:
    symbol = "threshold"
    askers: list[AskerName] = ["morrison", "blake", "kierkegaard"]
    chosen = askers[abs(hash(ctx.transcript)) % 3]
    questions = {
        "blake": (
            f"What image are you refusing to see in the word '{symbol}' that keeps returning to you?"
        ),
        "morrison": (
            "Whose story are you still performing—and what would your body say if you stopped?"
        ),
        "kierkegaard": (
            "What choice are you postponing until you feel no dread at all?"
        ),
    }
    return CouncilDecision(
        chosen_asker=chosen,
        next_question=questions[chosen],
        rationale=(
            f"{DISPLAY_NAMES[chosen]} should ask because the council converged on "
            "their line of pressure in the final exchange."
        ),
    )


class AgentCouncil:
    def __init__(self) -> None:
        self._blake = LambdaAgent()
        self._morrison = PsiAgent()
        self._kierkegaard = DeltaAgent()

    async def run_turn(
        self,
        ctx: TurnContext,
        history_snippet: str,
    ) -> CouncilTurnResult:
        blake_r, morrison_r, kierkegaard_r = await asyncio.gather(
            self._blake.reflect(ctx),
            self._morrison.reflect(ctx),
            self._kierkegaard.reflect(ctx),
        )

        conversation: list[ConversationLine] = []
        agents = {
            "blake": self._blake,
            "morrison": self._morrison,
            "kierkegaard": self._kierkegaard,
        }

        for speaker in SPEAK_ORDER:
            line = await agents[speaker].speak(
                ctx,
                blake_r,
                morrison_r,
                kierkegaard_r,
                conversation,
            )
            conversation.append(ConversationLine(speaker=speaker, text=line))

        decision = await self._decide(ctx, blake_r, morrison_r, kierkegaard_r, conversation, history_snippet)

        return CouncilTurnResult(
            blake_reflection=blake_r,
            morrison_reflection=morrison_r,
            kierkegaard_reflection=kierkegaard_r,
            conversation=conversation,
            decision=decision,
        )

    async def _decide(
        self,
        ctx: TurnContext,
        blake_r,
        morrison_r,
        kierkegaard_r,
        conversation: list[ConversationLine],
        history_snippet: str,
    ) -> CouncilDecision:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_decide, ctx, conversation)

        payload = json.dumps(
            {
                "question": ctx.question,
                "participant_answer": ctx.transcript,
                "private_reflections": {
                    "blake": blake_r.model_dump(),
                    "morrison": morrison_r.model_dump(),
                    "kierkegaard": kierkegaard_r.model_dump(),
                },
                "conversation": [c.model_dump() for c in conversation],
                "session_history_excerpt": history_snippet,
            },
            ensure_ascii=False,
        )

        def _call() -> CouncilDecision:
            msg = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=320,
                system=COUNCIL_DECIDE,
                messages=[{"role": "user", "content": payload}],
            )
            return parse_json_response(msg.content[0].text, CouncilDecision)

        return await asyncio.to_thread(_call)
