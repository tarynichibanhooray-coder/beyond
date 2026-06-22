from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pathlib import Path

from agents.council import DISPLAY_NAMES
from agents.roster import member_profiles_for_roster, parse_roster
from config import settings
from models import CouncilTurnResult
from session import SessionManager
from utils.usage import log_turn_usage, server_usage, server_usage_snapshot

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Before — demo")

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

INITIAL_QUESTION = "What brought you here?"


@dataclass
class _SessionState:
    sm: SessionManager
    question: str
    turn: int
    turn_busy: bool = False


_SESSIONS: dict[str, _SessionState] = {}


class UsageInfo(BaseModel):
    turn: dict
    session: dict
    server: dict
    token_budget: int


class StartResponse(BaseModel):
    session_id: str
    question: str
    remaining_sec: int
    mock_mode: bool
    usage: UsageInfo
    council_roster: list[str]
    council: list[dict]
    transcript_path: str | None = None


class TurnResponse(BaseModel):
    session_id: str
    turn: int
    question: str
    transcript: str
    reflections: dict[str, dict]
    council_roster: list[str]
    conversation: list[dict]
    chosen_asker: str
    chosen_asker_display: str
    next_question: str
    decision_rationale: str
    remaining_sec: int
    done: bool
    mock_mode: bool
    usage: UsageInfo
    final_question: str | None = None
    reasoning: str | None = None
    transcript_path: str | None = None


class AnswerRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)


def _empty_usage_dict(model: str) -> dict:
    from utils.usage import UsageSnapshot

    return UsageSnapshot().to_dict(model, settings.token_budget)


def _usage_payload(ledger, before) -> UsageInfo:
    after = ledger.snapshot()
    model = settings.anthropic_model
    budget = settings.token_budget
    return UsageInfo(
        turn=after.delta(before).to_dict(model, budget),
        session=after.to_dict(model, budget),
        server=server_usage_snapshot(model, budget),
        token_budget=budget,
    )


def _usage_payload_idle(ledger) -> UsageInfo:
    model = settings.anthropic_model
    budget = settings.token_budget
    empty = _empty_usage_dict(model)
    return UsageInfo(
        turn=empty,
        session=ledger.snapshot().to_dict(model, budget),
        server=server_usage_snapshot(model, budget),
        token_budget=budget,
    )


def _fallback_question(transcript: str) -> str:
    seed = transcript.strip()
    if not seed:
        return "What are you refusing to choose, even now?"
    return f"You said, \"{seed[:120]}\". What truth inside that are you ready to live by today?"


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


async def _finalize_turn(
    state: _SessionState,
    *,
    session_id: str,
    question: str,
    transcript: str,
    result: CouncilTurnResult,
    usage_before,
) -> TurnResponse:
    next_q = result.decision.next_question.strip()
    if not next_q:
        next_q = _fallback_question(transcript)
    chosen = result.decision.chosen_asker

    state.turn += 1
    state.question = next_q

    remaining = state.sm.remaining()
    done = remaining <= 0 or state.turn >= 3

    final_question = None
    reasoning = None
    transcript_path = (
        str(state.sm.last_transcript_path) if state.sm.last_transcript_path else None
    )
    if done:
        final = await state.sm.end_session()
        final_question = final.final_question
        reasoning = final.reasoning

    usage = _usage_payload(state.sm.usage, usage_before)
    log_turn_usage(
        turn=state.turn,
        session=state.sm.usage.snapshot(),
        server=server_usage(),
        budget=settings.token_budget,
    )

    return TurnResponse(
        session_id=session_id,
        turn=state.turn,
        question=question,
        transcript=transcript,
        reflections=result.reflections,
        council_roster=list(state.sm.council_roster),
        conversation=[c.model_dump() for c in result.conversation],
        chosen_asker=chosen,
        chosen_asker_display=DISPLAY_NAMES.get(chosen, chosen),
        next_question=next_q,
        decision_rationale=result.decision.rationale,
        remaining_sec=remaining,
        done=done,
        mock_mode=settings.mock_mode,
        usage=usage,
        final_question=final_question,
        reasoning=reasoning,
        transcript_path=transcript_path,
    )


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/council")
async def council_config() -> dict:
    roster = parse_roster()
    return {
        "roster": roster,
        "members": member_profiles_for_roster(roster),
    }


@app.post("/api/session/start")
async def start_session() -> StartResponse:
    sm = SessionManager()
    sm.start_session()
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = _SessionState(sm=sm, question=INITIAL_QUESTION, turn=0)
    roster = parse_roster()
    return StartResponse(
        session_id=session_id,
        question=INITIAL_QUESTION,
        remaining_sec=sm.remaining(),
        mock_mode=settings.mock_mode,
        usage=_usage_payload_idle(sm.usage),
        council_roster=roster,
        council=member_profiles_for_roster(roster),
        transcript_path=str(sm.last_transcript_path) if sm.last_transcript_path else None,
    )


@app.post("/api/session/{session_id}/answer")
async def answer(session_id: str, req: AnswerRequest) -> TurnResponse:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if state.sm.remaining() <= 0:
        raise HTTPException(status_code=409, detail="Session has ended")

    if state.turn_busy:
        raise HTTPException(status_code=409, detail="Turn already in progress")

    state.turn_busy = True
    bpm_window: list[tuple[float, float]] = []

    q = state.question
    usage_before = state.sm.usage.snapshot()
    try:
        result = await state.sm.run_turn(q, req.transcript, bpm_window)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ModuleNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail="Live AI requires: pip install -r requirements-anthropic.txt "
            "(or set MOCK_MODE=true to test without API calls).",
        ) from exc
    except Exception as exc:
        if exc.__class__.__module__.startswith("anthropic"):
            raise HTTPException(
                status_code=502,
                detail=f"Anthropic API error: {exc}",
            ) from exc
        raise
    finally:
        state.turn_busy = False

    response = await _finalize_turn(
        state,
        session_id=session_id,
        question=q,
        transcript=req.transcript,
        result=result,
        usage_before=usage_before,
    )
    if response.done:
        _SESSIONS.pop(session_id, None)
    return response


@app.post("/api/session/{session_id}/answer/stream")
async def answer_stream(session_id: str, req: AnswerRequest) -> StreamingResponse:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if state.sm.remaining() <= 0:
        raise HTTPException(status_code=409, detail="Session has ended")

    if state.turn_busy:
        raise HTTPException(status_code=409, detail="Turn already in progress")

    state.turn_busy = True
    bpm_window: list[tuple[float, float]] = []
    q = state.question
    usage_before = state.sm.usage.snapshot()

    async def generate():
        try:
            async for event in state.sm.run_turn_events(q, req.transcript, bpm_window):
                if event["type"] == "complete":
                    result = CouncilTurnResult.model_validate(event["result"])
                    response = await _finalize_turn(
                        state,
                        session_id=session_id,
                        question=q,
                        transcript=req.transcript,
                        result=result,
                        usage_before=usage_before,
                    )
                    if response.done:
                        _SESSIONS.pop(session_id, None)
                    yield _sse({"type": "turn_done", **response.model_dump()})
                else:
                    yield _sse(event)
        except RuntimeError as exc:
            yield _sse({"type": "error", "detail": str(exc)})
        except ModuleNotFoundError:
            yield _sse(
                {
                    "type": "error",
                    "detail": "Live AI requires: pip install -r requirements-anthropic.txt "
                    "(or set MOCK_MODE=true to test without API calls).",
                }
            )
        except Exception as exc:
            if exc.__class__.__module__.startswith("anthropic"):
                yield _sse({"type": "error", "detail": f"Anthropic API error: {exc}"})
            else:
                yield _sse({"type": "error", "detail": str(exc)})
        finally:
            state.turn_busy = False

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/usage")
async def usage(session_id: str | None = None) -> dict:
    budget = settings.token_budget
    model = settings.anthropic_model
    payload: dict = {
        "mock_mode": settings.mock_mode,
        "model": model,
        "token_budget": budget,
        "server": server_usage_snapshot(model, budget),
        "billing_note": "Estimated from token counts. Actual balance: console.anthropic.com → Billing.",
    }
    if session_id:
        state = _SESSIONS.get(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Unknown session_id")
        payload["session"] = state.sm.usage.snapshot().to_dict(model, budget)
    return payload


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mock_mode": settings.mock_mode,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8765)
