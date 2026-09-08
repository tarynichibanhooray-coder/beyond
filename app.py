from __future__ import annotations

import json
import secrets
import time
import uuid
from dataclasses import dataclass

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pathlib import Path

from agents.council import DISPLAY_NAMES
from agents.roster import member_profiles_for_roster, parse_roster
from config import settings
from models import CouncilTurnResult
from session import SessionManager
from utils.question_clarity import is_confusion_transcript, rephrase_question
from utils.locale import initial_question, localize_member_profiles, normalize_locale, resolve_locale
from utils.question_limits import limit_question_sentences
from utils.session_export import export_transcript_file
from utils.daily_budget import (
    assert_budget_available,
    daily_usage_snapshot,
    depleted_message,
    record_completed_session,
    set_budget_locale,
)
from utils.usage import log_turn_usage, server_usage, server_usage_snapshot, sync_server_usage_from_daily

ROOT = Path(__file__).resolve().parent

app = FastAPI(title="Before — demo")

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
sync_server_usage_from_daily()


@app.middleware("http")
async def no_cache_live_assets(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


@dataclass
class _SessionState:
    sm: SessionManager
    question: str
    turn: int
    locale: str = "en"
    turn_busy: bool = False


_SESSIONS: dict[str, _SessionState] = {}


class UsageInfo(BaseModel):
    turn: dict
    session: dict
    server: dict
    daily: dict
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
    question_rephrased: bool = False


class AnswerRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)


class ShareResponse(BaseModel):
    share_id: str
    share_url: str


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
        daily=daily_usage_snapshot(budget),
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
        daily=daily_usage_snapshot(budget),
        token_budget=budget,
    )


def _budget_http_error(locale: str) -> HTTPException:
    return HTTPException(status_code=503, detail=depleted_message(locale))


def _fallback_question(transcript: str, locale: str = "en") -> str:
    seed = transcript.strip()
    if normalize_locale(locale) == "es":
        if not seed:
            return "¿Qué te niegas a elegir, incluso ahora?"
        return f'Dijiste: "{seed[:120]}". ¿Qué verdad dentro de eso estás listo para vivir hoy?'
    if not seed:
        return "What are you refusing to choose, even now?"
    return f'You said, "{seed[:120]}". What truth inside that are you ready to live by today?'


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, default=str)}\n\n"


def _validate_transcript_filename(filename: str) -> Path:
    if not filename.endswith(".json") or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid transcript filename")
    path = settings.transcript_dir / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found")
    return path


def _share_index_path() -> Path:
    return settings.transcript_dir / "shares.json"


def _load_share_index() -> dict[str, str]:
    path = _share_index_path()
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(share_id): str(filename)
        for share_id, filename in data.items()
        if isinstance(share_id, str) and isinstance(filename, str)
    }


def _save_share_index(data: dict[str, str]) -> None:
    path = _share_index_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def _share_url(share_id: str) -> str:
    base = str(settings.app_base_url or "").rstrip("/") or "http://localhost:8765"
    return f"{base}/s/{share_id}"


def _ensure_share(filename: str) -> ShareResponse:
    _validate_transcript_filename(filename)
    shares = _load_share_index()
    for share_id, mapped_filename in shares.items():
        if mapped_filename == filename:
            return ShareResponse(share_id=share_id, share_url=_share_url(share_id))

    while True:
        share_id = secrets.token_urlsafe(12)
        if share_id not in shares:
            break
    shares[share_id] = filename
    _save_share_index(shares)
    return ShareResponse(share_id=share_id, share_url=_share_url(share_id))


async def _rephrase_turn_response(
    state: _SessionState,
    *,
    session_id: str,
    original_question: str,
    transcript: str,
    usage_before,
) -> TurnResponse:
    simpler = limit_question_sentences(
        await rephrase_question(original_question, transcript, state.locale)
    )
    state.question = simpler
    state.sm.note_current_question(simpler)
    usage = _usage_payload(state.sm.usage, usage_before)
    model = settings.anthropic_model
    budget = settings.token_budget
    transcript_path = (
        str(state.sm.last_transcript_path) if state.sm.last_transcript_path else None
    )
    return TurnResponse(
        session_id=session_id,
        turn=state.turn,
        question=original_question,
        transcript=transcript,
        reflections={},
        council_roster=list(state.sm.council_roster),
        conversation=[],
        chosen_asker="",
        chosen_asker_display="",
        next_question=simpler,
        decision_rationale="",
        remaining_sec=state.sm.remaining(),
        done=False,
        mock_mode=settings.mock_mode,
        usage=usage,
        transcript_path=transcript_path,
        question_rephrased=True,
    )


async def _finalize_turn(
    state: _SessionState,
    *,
    session_id: str,
    question: str,
    transcript: str,
    result: CouncilTurnResult,
    usage_before,
) -> TurnResponse:
    next_q = limit_question_sentences(result.decision.next_question)
    if not next_q:
        next_q = limit_question_sentences(_fallback_question(transcript, state.locale))
    chosen = result.decision.chosen_asker

    state.turn += 1
    state.question = next_q
    state.sm.note_current_question(next_q)

    remaining = state.sm.remaining()
    done = state.turn >= 3

    final_question = None
    reasoning = None
    transcript_path = (
        str(state.sm.last_transcript_path) if state.sm.last_transcript_path else None
    )
    if done:
        final = await state.sm.end_session(locale=state.locale)
        final_question = limit_question_sentences(final.final_question)
        reasoning = final.reasoning
        record_completed_session(state.sm.usage.snapshot().total_tokens)

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
        decision_rationale="",
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
async def council_config(accept_language: str | None = Header(default=None)) -> dict:
    locale = resolve_locale(accept_language)
    roster = parse_roster()
    return {
        "roster": roster,
        "members": localize_member_profiles(member_profiles_for_roster(roster), locale),
        "locale": locale,
    }


@app.post("/api/session/start")
async def start_session(accept_language: str | None = Header(default=None)) -> StartResponse:
    locale = resolve_locale(accept_language)
    set_budget_locale(locale)
    try:
        assert_budget_available(locale)
    except RuntimeError as exc:
        raise _budget_http_error(locale) from exc
    question = initial_question(locale)
    sm = SessionManager()
    sm.start_session(initial_question=question)
    session_id = uuid.uuid4().hex
    _SESSIONS[session_id] = _SessionState(sm=sm, question=question, turn=0, locale=locale)
    roster = parse_roster()
    return StartResponse(
        session_id=session_id,
        question=question,
        remaining_sec=sm.remaining(),
        mock_mode=settings.mock_mode,
        usage=_usage_payload_idle(sm.usage),
        council_roster=roster,
        council=localize_member_profiles(member_profiles_for_roster(roster), locale),
        transcript_path=str(sm.last_transcript_path) if sm.last_transcript_path else None,
    )


@app.post("/api/session/{session_id}/checkpoint")
async def checkpoint(session_id: str) -> dict:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")
    state.sm.note_current_question(state.question)
    return {
        "transcript_path": str(state.sm.last_transcript_path)
        if state.sm.last_transcript_path
        else None,
    }


@app.post("/api/session/{session_id}/answer")
async def answer(session_id: str, req: AnswerRequest) -> TurnResponse:
    state = _SESSIONS.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Unknown session_id")

    if state.turn_busy:
        raise HTTPException(status_code=409, detail="Turn already in progress")

    state.sm.note_current_question(state.question)
    state.turn_busy = True
    set_budget_locale(state.locale)
    try:
        assert_budget_available(state.locale)
    except RuntimeError as exc:
        state.turn_busy = False
        raise _budget_http_error(state.locale) from exc
    bpm_window: list[tuple[float, float]] = []

    q = state.question
    usage_before = state.sm.usage.snapshot()
    try:
        if is_confusion_transcript(req.transcript):
            return await _rephrase_turn_response(
                state,
                session_id=session_id,
                original_question=q,
                transcript=req.transcript,
                usage_before=usage_before,
            )
        result = await state.sm.run_turn(q, req.transcript, bpm_window, locale=state.locale)
    except RuntimeError as exc:
        if depleted_message("en") in str(exc) or depleted_message("es") in str(exc):
            raise _budget_http_error(state.locale) from exc
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

    if state.turn_busy:
        raise HTTPException(status_code=409, detail="Turn already in progress")

    state.sm.note_current_question(state.question)
    state.turn_busy = True
    set_budget_locale(state.locale)
    try:
        assert_budget_available(state.locale)
    except RuntimeError as exc:
        state.turn_busy = False
        raise _budget_http_error(state.locale) from exc
    bpm_window: list[tuple[float, float]] = []
    q = state.question
    usage_before = state.sm.usage.snapshot()

    async def generate():
        try:
            if is_confusion_transcript(req.transcript):
                response = await _rephrase_turn_response(
                    state,
                    session_id=session_id,
                    original_question=q,
                    transcript=req.transcript,
                    usage_before=usage_before,
                )
                yield _sse({"type": "turn_done", **response.model_dump()})
                return
            async for event in state.sm.run_turn_events(q, req.transcript, bpm_window, locale=state.locale):
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
            if depleted_message("en") in str(exc) or depleted_message("es") in str(exc):
                yield _sse({"type": "error", "detail": depleted_message(state.locale)})
            else:
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
        "daily": daily_usage_snapshot(budget),
        "server": server_usage_snapshot(model, budget),
        "billing_note": "Estimated from token counts. Actual balance: console.anthropic.com → Billing.",
    }
    if session_id:
        state = _SESSIONS.get(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Unknown session_id")
        payload["session"] = state.sm.usage.snapshot().to_dict(model, budget)
    return payload


@app.get("/api/transcript/{filename}/export")
async def export_transcript(
    filename: str,
    accept_language: str | None = Header(default=None),
) -> Response:
    path = _validate_transcript_filename(filename)
    locale = resolve_locale(accept_language)
    html_out, html_name = export_transcript_file(path, locale=locale)
    return Response(
        content=html_out,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{html_name}"'},
    )


@app.post("/api/transcript/{filename}/share")
async def share_transcript(filename: str) -> ShareResponse:
    return _ensure_share(filename)


@app.get("/s/{share_id}")
async def shared_transcript(
    share_id: str,
    accept_language: str | None = Header(default=None),
) -> Response:
    shares = _load_share_index()
    filename = shares.get(share_id)
    if not filename:
        raise HTTPException(status_code=404, detail="Share not found")
    path = _validate_transcript_filename(filename)
    locale = resolve_locale(accept_language)
    html_out, _html_name = export_transcript_file(path, locale=locale)
    return Response(content=html_out, media_type="text/html; charset=utf-8")


@app.get("/api/health")
async def health() -> dict[str, str | bool]:
    settings.transcript_dir.mkdir(parents=True, exist_ok=True)
    return {
        "status": "ok",
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mock_mode": settings.mock_mode,
        "transcript_dir": str(settings.transcript_dir),
        "transcript_dir_exists": settings.transcript_dir.is_dir(),
    }


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(app, host="0.0.0.0", port=port)
