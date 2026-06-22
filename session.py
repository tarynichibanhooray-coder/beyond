from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agents.council import AgentCouncil, DISPLAY_NAMES
from agents.roster import parse_roster
from agents.delta_agent import DeltaAgent
from config import settings
from models import CouncilTurnResult, DeltaFinal, TurnContext
from utils.logger import get_logger
from utils.speech_to_text import mock_transcript_for_turn
from utils.usage import UsageLedger, bind_usage_ledger

log = get_logger(__name__)


@dataclass
class SessionManager:
    timer_seconds: int = field(default_factory=lambda: settings.session_duration_seconds)
    conversation_history: list[dict] = field(default_factory=list)
    heart_rate_data: list[tuple[float, float]] = field(default_factory=list)
    last_transcript_path: Path | None = None
    initial_question: str = ""
    current_question: str = ""
    usage: UsageLedger = field(default_factory=UsageLedger)

    def __post_init__(self) -> None:
        self.council_roster = parse_roster()
        self._council = AgentCouncil(self.council_roster)
        self._delta = DeltaAgent()
        self._start_monotonic: float | None = None

    def elapsed(self) -> float:
        if self._start_monotonic is None:
            return 0.0
        return time.monotonic() - self._start_monotonic

    def remaining(self) -> int:
        return max(0, int(self.timer_seconds - self.elapsed()))

    def start_session(self, *, initial_question: str = "What brought you here?") -> None:
        self._start_monotonic = time.monotonic()
        self.conversation_history.clear()
        self.heart_rate_data.clear()
        self.usage = UsageLedger()
        self.initial_question = initial_question
        self.current_question = initial_question
        settings.transcript_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        self.last_transcript_path = settings.transcript_dir / f"session-{stamp}.json"
        self._save_transcript()
        log.info("Session started (%ss); transcript %s", self.timer_seconds, self.last_transcript_path)

    def note_current_question(self, question: str) -> None:
        text = question.strip()
        if not text:
            return
        self.current_question = text
        if not self.initial_question:
            self.initial_question = text
        self._save_transcript()

    async def run_turn(
        self,
        question: str,
        transcript: str,
        bpm_window: list[tuple[float, float]],
        locale: str = "en",
    ) -> CouncilTurnResult:
        result: CouncilTurnResult | None = None
        async for event in self.run_turn_events(question, transcript, bpm_window, locale):
            if event["type"] == "complete":
                result = CouncilTurnResult.model_validate(event["result"])
        if result is None:
            raise RuntimeError("Turn ended without a result")
        return result

    async def run_turn_events(
        self,
        question: str,
        transcript: str,
        bpm_window: list[tuple[float, float]],
        locale: str = "en",
    ):
        ctx = TurnContext(
            question=question,
            transcript=transcript,
            bpm_window=bpm_window,
            locale=locale,
        )
        history_snippet = json.dumps(self.conversation_history[-4:], default=str)
        with bind_usage_ledger(self.usage):
            async for event in self._council.run_turn_events(ctx, history_snippet):
                if event["type"] == "complete":
                    result = CouncilTurnResult.model_validate(event["result"])
                    self.conversation_history.append(
                        {
                            "question": question,
                            "transcript": transcript,
                            "council_roster": self.council_roster,
                            "reflections": result.reflections,
                            "conversation": [c.model_dump() for c in result.conversation],
                            "chosen_asker": result.decision.chosen_asker,
                            "next_question": result.decision.next_question,
                        }
                    )
                    self.current_question = result.decision.next_question.strip() or question
                    self._save_transcript()
                    log.info("Transcript saved (turn %s): %s", len(self.conversation_history), self.last_transcript_path)
                    log.info(
                        "Turn complete | %s asks: %s",
                        DISPLAY_NAMES.get(
                            result.decision.chosen_asker, result.decision.chosen_asker
                        ),
                        result.decision.next_question[:80],
                    )
                yield event

    async def end_session(self, locale: str = "en") -> DeltaFinal:
        summary = json.dumps(self.conversation_history, default=str)
        with bind_usage_ledger(self.usage):
            final = await self._delta.final_question(summary, locale=locale)
        self.conversation_history.append(
            {"final_question": final.model_dump()},
        )
        self._save_transcript()
        log.info("Session ended; transcript %s", self.last_transcript_path)
        return final

    def _transcript_payload(self) -> list[dict[str, Any]]:
        meta = {
            "session": {
                "initial_question": self.initial_question,
                "current_question": self.current_question,
            }
        }
        return [meta, *self.conversation_history]

    def _save_transcript(self) -> Path:
        if self.last_transcript_path is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            self.last_transcript_path = settings.transcript_dir / f"session-{stamp}.json"
        path = self.last_transcript_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._transcript_payload(), indent=2, default=str))
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
        bpm_window = []
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
