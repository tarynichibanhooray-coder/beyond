from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from agents._client import create_message, get_anthropic_client, parse_json_response
from agents.arabi_agent import ArabiAgent
from agents.delta_agent import DeltaAgent
from agents.lambda_agent import LambdaAgent
from agents.psi_agent import PsiAgent
from agents.roster import CouncilMemberId, display_label, display_name, parse_roster
from prompt_training.prompts import COUNCIL_DECIDE
from config import settings
from models import (
    ConversationLine,
    CouncilDecision,
    CouncilTurnResult,
    TurnContext,
)

AGENT_CLASSES = {
    "arabi": ArabiAgent,
    "blake": LambdaAgent,
    "morrison": PsiAgent,
    "kierkegaard": DeltaAgent,
}


def _mock_decide(ctx: TurnContext, conversation: list[ConversationLine], roster: list[CouncilMemberId]) -> CouncilDecision:
    askers = [m for m in roster if m != "kierkegaard"] + ["kierkegaard"]
    chosen = askers[abs(hash(ctx.transcript)) % len(askers)]
    questions = {
        "arabi": "What if this threshold you stand in is not before your life—but the place where your searching becomes visible?",
        "blake": "What image are you refusing to see that keeps returning to you?",
        "morrison": "Whose story are you still performing—and what would your body say if you stopped?",
        "kierkegaard": "What would you begin if you trusted that becoming yourself is allowed?",
    }
    return CouncilDecision(
        chosen_asker=chosen,
        next_question=questions[chosen],
    )


class AgentCouncil:
    def __init__(self, roster: list[CouncilMemberId] | None = None) -> None:
        self.roster = roster or parse_roster()
        self._agents = {
            member_id: AGENT_CLASSES[member_id]() for member_id in self.roster
        }
        self.display_names = {member_id: display_name(member_id) for member_id in self.roster}
        self.display_labels = {member_id: display_label(member_id) for member_id in self.roster}

    async def run_turn(
        self,
        ctx: TurnContext,
        history_snippet: str,
    ) -> CouncilTurnResult:
        result: CouncilTurnResult | None = None
        async for event in self.run_turn_events(ctx, history_snippet):
            if event["type"] == "complete":
                result = event["result"]
        if result is None:
            raise RuntimeError("Turn ended without a result")
        return result

    async def run_turn_events(
        self,
        ctx: TurnContext,
        history_snippet: str,
    ) -> AsyncIterator[dict[str, Any]]:
        yield {"type": "phase", "phase": "reflect"}

        reflect_tasks = {
            member_id: self._agents[member_id].reflect(ctx) for member_id in self.roster
        }
        reflect_results = await asyncio.gather(*reflect_tasks.values())
        reflections = {
            member_id: result.model_dump()
            for member_id, result in zip(reflect_tasks.keys(), reflect_results, strict=True)
        }
        payload = {"type": "reflections", **{f"{k}_reflection": v for k, v in reflections.items()}}
        # Also expose generic map for future UI
        payload["reflections"] = reflections
        yield payload

        yield {"type": "phase", "phase": "deliberate", "label": "The council speaks…"}

        conversation: list[ConversationLine] = []
        reflection_models = dict(zip(reflect_tasks.keys(), reflect_results, strict=True))

        for speaker in self.roster:
            yield {
                "type": "phase",
                "phase": "speak",
                "speaker": speaker,
                "label": f"{self.display_names[speaker]} speaks…",
            }
            reflections_for_speak = {
                member_id: reflection_models[member_id].model_dump()
                for member_id in self.roster
            }
            line = await self._agents[speaker].speak(
                ctx,
                reflections_for_speak,
                conversation,
            )
            conversation.append(ConversationLine(speaker=speaker, text=line))
            yield {
                "type": "speak",
                "speaker": speaker,
                "text": line,
                "conversation": [c.model_dump() for c in conversation],
            }

        yield {"type": "phase", "phase": "decide", "label": "Formulating your next question…"}

        decision = await self._decide(
            ctx, reflections, conversation, history_snippet
        )

        result = CouncilTurnResult(
            reflections=reflections,
            conversation=conversation,
            decision=decision,
        )
        yield {"type": "complete", "result": result.model_dump()}

    async def _decide(
        self,
        ctx: TurnContext,
        reflections: dict[str, dict],
        conversation: list[ConversationLine],
        history_snippet: str,
    ) -> CouncilDecision:
        client = get_anthropic_client()
        if client is None:
            return await asyncio.to_thread(_mock_decide, ctx, conversation, self.roster)

        payload = json.dumps(
            {
                "question": ctx.question,
                "participant_answer": ctx.transcript,
                "active_roster": self.roster,
                "private_reflections": reflections,
                "conversation": [c.model_dump() for c in conversation],
                "session_history_excerpt": history_snippet,
            },
            ensure_ascii=False,
        )

        def _call() -> CouncilDecision:
            msg = create_message(
                client,
                label="council.decide",
                model=settings.anthropic_model,
                max_tokens=280,
                system=COUNCIL_DECIDE,
                messages=[{"role": "user", "content": payload}],
            )
            decision = parse_json_response(msg.content[0].text, CouncilDecision)
            if decision.chosen_asker not in self.roster:
                decision = decision.model_copy(update={"chosen_asker": self.roster[0]})
            return decision

        return await asyncio.to_thread(_call)


# Backward-compatible exports for app layer
DISPLAY_NAMES = {member_id: display_name(member_id) for member_id in AGENT_CLASSES}
