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
