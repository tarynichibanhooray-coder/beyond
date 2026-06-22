from __future__ import annotations

import time
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pathlib import Path

from agents.council import DISPLAY_NAMES
from session import SessionManager

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Before — demo")

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

INITIAL_QUESTION = "What brought you here?"


@dataclass
class _SessionState:
    sm: SessionManager
    question: str
    turn: int


_SESSIONS: dict[str, _SessionState] = {}


class StartResponse(BaseModel):
    session_id: str
    question: str
    remaining_sec: int


class AnswerRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)


class TurnResponse(BaseModel):
    session_id: str
    turn: int
    question: str
    transcript: str
    blake_reflection: dict
    morrison_reflection: dict
    kierkegaard_reflection: dict
    conversation: list[dict]
    chosen_asker: str
    chosen_asker_display: str
    next_question: str
    decision_rationale: str
    remaining_sec: int
    done: bool
    final_question: str | None = None
    reasoning: str | None = None
    transcript_path: str | None = None


def _fallback_question(transcript: str) -> str:
    seed = transcript.strip()
    if not seed:
        return "What are you refusing to choose, even now?"
    return f"You said, \"{seed[:120]}\". What truth inside that are you ready to live by today?"


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.post("/api/session/start")
async def start_session() -> StartResponse:
    sm = SessionManager()
    sm.start_session()
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = _SessionState(sm=sm, question=INITIAL_QUESTION, turn=0)
    return StartResponse(
        session_id=session_id,
        question=INITIAL_QUESTION,
        remaining_sec=sm.remaining(),
    )


@app.post("/api/session/{session_id}/answer")
async def answer(session_id: str, req: AnswerRequest) -> TurnResponse:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if state.sm.remaining() <= 0:
        raise HTTPException(status_code=409, detail="Session has ended")

    t0 = state.sm.elapsed()
    bpm_window = [(t0 + i * 0.5, 72.0 + i) for i in range(5)]

    q = state.question
    result = await state.sm.run_turn(q, req.transcript, bpm_window)

    next_q = result.decision.next_question.strip()
    if not next_q:
        next_q = _fallback_question(req.transcript)
    chosen = result.decision.chosen_asker

    state.turn += 1
    state.question = next_q

    remaining = state.sm.remaining()
    done = remaining <= 0 or state.turn >= 3

    final_question = None
    reasoning = None
    transcript_path = None
    if done:
        final = await state.sm.end_session()
        final_question = final.final_question
        reasoning = final.reasoning
        transcript_path = (
            str(state.sm.last_transcript_path) if state.sm.last_transcript_path else None
        )
        _SESSIONS.pop(session_id, None)

    return TurnResponse(
        session_id=session_id,
        turn=state.turn,
        question=q,
        transcript=req.transcript,
        blake_reflection=result.blake_reflection.model_dump(),
        morrison_reflection=result.morrison_reflection.model_dump(),
        kierkegaard_reflection=result.kierkegaard_reflection.model_dump(),
        conversation=[c.model_dump() for c in result.conversation],
        chosen_asker=chosen,
        chosen_asker_display=DISPLAY_NAMES[chosen],
        next_question=next_q,
        decision_rationale=result.decision.rationale,
        remaining_sec=remaining,
        done=done,
        final_question=final_question,
        reasoning=reasoning,
        transcript_path=transcript_path,
    )


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "time": time.strftime("%Y-%m-%d %H:%M:%S")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
