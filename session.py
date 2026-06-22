from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.council import AgentCouncil, DISPLAY_NAMES
from agents.delta_agent import DeltaAgent
from config import settings
from models import CouncilTurnResult, DeltaFinal, TurnContext
from utils.logger import get_logger
from utils.speech_to_text import mock_transcript_for_turn

log = get_logger(__name__)


@dataclass
class SessionManager:
    timer_seconds: int = field(default_factory=lambda: settings.session_duration_seconds)
    conversation_history: list[dict] = field(default_factory=list)
    heart_rate_data: list[tuple[float, float]] = field(default_factory=list)
    last_transcript_path: Path | None = None

    def __post_init__(self) -> None:
        self._council = AgentCouncil()
        self._delta = DeltaAgent()
        self._start_monotonic: float | None = None

    def elapsed(self) -> float:
        if self._start_monotonic is None:
            return 0.0
        return time.monotonic() - self._start_monotonic

    def remaining(self) -> int:
        return max(0, int(self.timer_seconds - self.elapsed()))

    def start_session(self) -> None:
        self._start_monotonic = time.monotonic()
        self.conversation_history.clear()
        self.heart_rate_data.clear()
        settings.transcript_dir.mkdir(parents=True, exist_ok=True)
        log.info("Session started (%ss)", self.timer_seconds)

    async def run_turn(
        self,
        question: str,
        transcript: str,
        bpm_window: list[tuple[float, float]],
    ) -> CouncilTurnResult:
        ctx = TurnContext(
            question=question,
            transcript=transcript,
            bpm_window=bpm_window,
        )
        history_snippet = json.dumps(self.conversation_history[-4:], default=str)
        result = await self._council.run_turn(ctx, history_snippet)

        self.conversation_history.append(
            {
                "question": question,
                "transcript": transcript,
                "blake_reflection": result.blake_reflection.model_dump(),
                "morrison_reflection": result.morrison_reflection.model_dump(),
                "kierkegaard_reflection": result.kierkegaard_reflection.model_dump(),
                "conversation": [c.model_dump() for c in result.conversation],
                "chosen_asker": result.decision.chosen_asker,
                "next_question": result.decision.next_question,
                "decision_rationale": result.decision.rationale,
            }
        )
        log.info(
            "Turn complete | %s asks: %s",
            DISPLAY_NAMES[result.decision.chosen_asker],
            result.decision.next_question[:80],
        )
        return result

    async def end_session(self) -> DeltaFinal:
        summary = json.dumps(self.conversation_history, default=str)
        final = await self._delta.final_question(summary)
        self.conversation_history.append(
            {"final_question": final.model_dump()},
        )
        self.last_transcript_path = self._save_transcript()
        log.info("Session ended; transcript %s", self.last_transcript_path)
        return final

    def _save_transcript(self) -> Path:
        stamp = time.strftime("%Y%m%d-%H%M%S")
        path = settings.transcript_dir / f"session-{stamp}.json"
        path.write_text(json.dumps(self.conversation_history, indent=2, default=str))
        return path


async def iter_demo_events() -> AsyncIterator[dict[str, Any]]:
    sm = SessionManager()
    sm.start_session()
    yield {
        "type": "session_start",
        "duration_sec": sm.timer_seconds,
        "remaining_sec": sm.remaining(),
    }
    question = "What brought you here?"
    turn_idx = 0
    while sm.remaining() > 0 and turn_idx < 3:
        transcript = mock_transcript_for_turn(turn_idx)
        t0 = sm.elapsed()
        bpm_window = [(t0 + i * 0.5, 72.0 + i) for i in range(5)]
        result = await sm.run_turn(question, transcript, bpm_window)
        yield {
            "type": "turn",
            "turn": turn_idx + 1,
            "question": question,
            "transcript": transcript,
            "council": result.model_dump(),
            "remaining_sec": sm.remaining(),
        }
        question = result.decision.next_question
        turn_idx += 1

    final = await sm.end_session()
    yield {
        "type": "final",
        "final_question": final.final_question,
        "reasoning": final.reasoning,
        "transcript_path": str(sm.last_transcript_path) if sm.last_transcript_path else "",
    }


async def demo_loop() -> None:
    async for _ in iter_demo_events():
        pass
