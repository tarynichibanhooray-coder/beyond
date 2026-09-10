import importlib

import pytest
from fastapi.testclient import TestClient


def test_settings_default_to_mock_mode():
    import config

    importlib.reload(config)
    assert config.settings.mock_mode is True


def test_get_anthropic_client_returns_none_in_mock_mode():
    import agents._client as client_mod
    import config

    config.settings.mock_mode = True
    assert client_mod.get_anthropic_client() is None


@pytest.mark.asyncio
async def test_session_turn_uses_mock_council():
    from session import SessionManager

    sm = SessionManager()
    sm.start_session()
    result = await sm.run_turn(
        "What brought you here?",
        "I came because I needed quiet.",
        [(0.0, 72.0), (0.5, 73.0)],
    )

    assert result.decision.next_question
    assert result.decision.chosen_asker in {"arabi", "blake", "morrison", "kierkegaard"}
    assert len(result.conversation) == 3


def test_spanish_session_dialogue_in_mock_mode():
    import app as app_mod

    client = TestClient(app_mod.app)
    start = client.post("/api/session/start", headers={"Accept-Language": "es-ES"})
    assert start.status_code == 200
    data = start.json()
    assert data["question"] == "¿Qué te trajo aquí?"

    session_id = data["session_id"]
    turn = client.post(
        f"/api/session/{session_id}/answer",
        json={"transcript": "Vine porque necesitaba silencio."},
        headers={"Accept-Language": "es-ES"},
    )
    assert turn.status_code == 200
    body = turn.json()
    assert body["next_question"]
    assert any(ch in body["next_question"] for ch in "¿áéíóú")
    assert body["conversation"]
    assert any(ch in body["conversation"][0]["text"] for ch in "áéíóú")


def test_api_session_flow_without_live_ai():
    import app as app_mod

    client = TestClient(app_mod.app)
    start = client.post("/api/session/start")
    assert start.status_code == 200
    session_id = start.json()["session_id"]

    turn = client.post(
        f"/api/session/{session_id}/answer",
        json={"transcript": "I am testing without spending API credits."},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["turn"] == 1
    assert data["next_question"]
    assert data["chosen_asker"] in {"arabi", "blake", "morrison", "kierkegaard"}
    assert "reflections" in data
    assert "arabi" in data["reflections"]


def test_clamp_observation_caps_sentences_and_words():
    from utils.observation_limits import clamp_observation, clamp_reflection_display

    long = (
        "They keep saying they are tired of waiting and then they explain the whole hallway "
        "again and again until the original fatigue is gone — and something larger is moving "
        "through them in the in-between where searching is not failure at all."
    )
    clipped = clamp_observation(long)
    assert clipped.count(".") + clipped.count("!") + clipped.count("?") <= 2
    assert len(clipped.split()) <= 40

    dumped = clamp_reflection_display(
        "arabi",
        {"disclosure_read": long, "color_intensity": 64},
    )
    assert dumped["disclosure_read"] == clipped
    assert dumped["color_intensity"] == 64


def test_kierkegaard_reflect_coerces_mis_keyed_json():
    from agents._client import parse_json_response
    from models import KierkegaardReflection

    raw = '{"tajalli_read": "The dread they will not name.", "mirror_clarity": 71}'
    result = parse_json_response(raw, KierkegaardReflection)
    assert result.dread_read == "The dread they will not name."
    assert result.color_intensity == 71
    assert result.avoided_choice
    assert result.leap_pressure

    raw_str_int = '{"tajalli_read": "Opening toward life.", "mirror_clarity": "63"}'
    result2 = parse_json_response(raw_str_int, KierkegaardReflection)
    assert result2.color_intensity == 63


def test_parse_json_response_extracts_prose_wrapped_object():
    from agents._client import parse_json_response
    from models import CouncilDecision

    raw = """I would choose Kierkegaard here.

    {
      "chosen_asker": "kierkegaard",
      "next_question": "What would you begin if you trusted one longing enough to let it lead?"
    }
    """

    result = parse_json_response(raw, CouncilDecision)

    assert result.chosen_asker == "kierkegaard"
    assert result.next_question.startswith("What would you begin")


def test_create_json_message_prefills_and_continues_on_max_tokens():
    from types import SimpleNamespace

    from agents._client import create_json_message

    calls = []

    class FakeMessages:
        def create(self, **kwargs):
            calls.append(kwargs)
            if len(calls) == 1:
                return SimpleNamespace(
                    stop_reason="max_tokens",
                    content=[SimpleNamespace(text='"chosen_asker": "arabi", ')],
                    usage=SimpleNamespace(
                        input_tokens=1,
                        output_tokens=1,
                        cache_creation_input_tokens=0,
                        cache_read_input_tokens=0,
                    ),
                )
            return SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(text='"next_question": "What now?"}')],
                usage=SimpleNamespace(
                    input_tokens=1,
                    output_tokens=1,
                    cache_creation_input_tokens=0,
                    cache_read_input_tokens=0,
                ),
            )

    client = SimpleNamespace(messages=FakeMessages())
    raw = create_json_message(
        client,
        label="council.decide",
        model="claude-test",
        max_tokens=540,
        messages=[{"role": "user", "content": "{}"}],
    )

    assert raw == '{"chosen_asker": "arabi", "next_question": "What now?"}'
    assert calls[0]["messages"][-1] == {"role": "assistant", "content": "{"}
    assert calls[1]["messages"][-1]["content"].startswith("{")


def test_parse_council_decision_falls_back_when_model_returns_prose():
    from agents.council import parse_council_decision
    from models import CouncilDecision

    fallback = CouncilDecision(
        chosen_asker="morrison",
        next_question="What story are you still telling as if it were finished?",
    )
    raw = (
        "I'll work through this privately before deciding what to ask. "
        "**Private Council Reflections:** **Arabi:** They said no."
    )

    result = parse_council_decision(raw, ["arabi", "morrison", "kierkegaard"], fallback)

    assert result.chosen_asker == "morrison"
    assert result.next_question == fallback.next_question


def test_parse_speak_line_accepts_plain_text():
    from agents._speak import parse_speak_line

    raw = "I hear the purpose already moving through what you said."

    assert parse_speak_line(raw) == raw


def test_confusion_transcript_detection():
    from utils.question_clarity import is_confusion_transcript

    assert is_confusion_transcript("I don't understand the question")
    assert is_confusion_transcript("What do you mean?")
    assert is_confusion_transcript("huh")
    assert is_confusion_transcript("no entiendo la pregunta")
    assert is_confusion_transcript("¿qué quieres decir?")


def test_confusion_rephrase_skips_council_turn():
    import app as app_mod

    client = TestClient(app_mod.app)
    start = client.post("/api/session/start")
    assert start.status_code == 200
    session_id = start.json()["session_id"]
    original_question = start.json()["question"]

    turn = client.post(
        f"/api/session/{session_id}/answer",
        json={"transcript": "I don't understand what you're asking."},
    )
    assert turn.status_code == 200
    data = turn.json()
    assert data["question_rephrased"] is True
    assert data["turn"] == 0
    assert data["next_question"]
    assert data["next_question"] != original_question or "simply" in data["next_question"].lower()
    assert data["reflections"] == {}
    assert data["conversation"] == []
    assert data["chosen_asker"] == ""


def test_export_filename_uses_most_recent_question():
    from utils.session_export import export_filename_from_history

    history = [
        {
            "session": {
                "initial_question": "What brought you here?",
                "current_question": "What truth are you already living toward?",
            }
        },
        {
            "question": "What brought you here?",
            "transcript": "I came for quiet.",
            "next_question": "What truth are you already living toward?",
        },
        {
            "final_question": {
                "final_question": "In the time that remains before, what will you choose to be?",
                "reasoning": "A door left open.",
            }
        },
    ]
    assert export_filename_from_history(history) == "what-truth-are-you-already.html"


@pytest.mark.asyncio
async def test_sse_keepalive_fills_silent_gaps():
    import asyncio

    import app as app_mod

    async def slow_source():
        yield 'data: {"type": "phase"}\n\n'
        await asyncio.sleep(0.5)
        yield 'data: {"type": "speak"}\n\n'

    original = app_mod.SSE_HEARTBEAT_SECONDS
    app_mod.SSE_HEARTBEAT_SECONDS = 0.1
    try:
        chunks = [chunk async for chunk in app_mod._sse_keepalive(slow_source())]
    finally:
        app_mod.SSE_HEARTBEAT_SECONDS = original

    assert [c for c in chunks if c.startswith("data:")] == [
        'data: {"type": "phase"}\n\n',
        'data: {"type": "speak"}\n\n',
    ]
    assert sum(1 for c in chunks if c.startswith(": keepalive")) >= 2


@pytest.mark.asyncio
async def test_sse_keepalive_propagates_source_errors():
    import app as app_mod

    async def boom():
        yield 'data: {"type": "phase"}\n\n'
        raise RuntimeError("agent exploded")

    with pytest.raises(RuntimeError, match="agent exploded"):
        async for _ in app_mod._sse_keepalive(boom()):
            pass


def test_index_and_code_assets_are_not_cached():
    import app as app_mod

    client = TestClient(app_mod.app)
    no_store = "no-store, max-age=0, must-revalidate"

    assert client.get("/").headers["cache-control"] == no_store
    assert client.get("/static/style.css").headers["cache-control"] == no_store
    assert client.get("/static/i18n.js").headers["cache-control"] == no_store
    # Images stay cacheable so every page load does not refetch them.
    assert "no-store" not in client.get("/static/og-in-this-time-before.png").headers.get(
        "cache-control", ""
    )


def test_answer_allowed_after_timer_expires():
    import time

    import app as app_mod

    client = TestClient(app_mod.app)
    start = client.post("/api/session/start").json()
    session_id = start["session_id"]
    state = app_mod._SESSIONS[session_id]
    state.sm._start_monotonic = time.monotonic() - state.sm.timer_seconds - 1

    turn = client.post(
        f"/api/session/{session_id}/answer",
        json={"transcript": "One last thought before time runs out."},
    )
    assert turn.status_code == 200
    assert turn.json()["turn"] == 1
    assert turn.json()["done"] is False
    assert turn.json()["next_question"]
