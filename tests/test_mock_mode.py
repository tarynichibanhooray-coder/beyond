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


def test_confusion_transcript_detection():
    from utils.question_clarity import is_confusion_transcript

    assert is_confusion_transcript("I don't understand the question")
    assert is_confusion_transcript("What do you mean?")
    assert is_confusion_transcript("huh")
    assert not is_confusion_transcript("I came because I needed quiet.")


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
