import json
from types import SimpleNamespace

import pytest

from utils import daily_budget as db


@pytest.fixture
def usage_file(tmp_path, monkeypatch):
    path = tmp_path / "daily_token_usage.json"
    monkeypatch.setattr(db, "usage_file_path", lambda: path)
    return path


def test_tokens_reset_on_new_utc_day(usage_file, monkeypatch):
    monkeypatch.setattr(db, "today_key", lambda: "2026-06-21")
    usage_file.write_text(json.dumps({"date": "2026-06-21", "tokens_used": 1000}), encoding="utf-8")
    monkeypatch.setattr(db, "today_key", lambda: "2026-06-22")
    assert db.tokens_used_today() == 0


def test_record_message_tokens_persists(usage_file):
    msg = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            cache_creation_input_tokens=0,
            cache_read_input_tokens=0,
        )
    )
    db.record_message_tokens(msg)
    db.record_message_tokens(msg)
    assert db.tokens_used_today() == 240


def test_depleted_when_at_budget(usage_file, monkeypatch):
    monkeypatch.setattr("config.settings.token_budget", 600_000)
    monkeypatch.setattr("config.settings.mock_mode", False)
    usage_file.write_text(
        json.dumps({"date": db.today_key(), "tokens_used": 600_000}),
        encoding="utf-8",
    )
    assert db.is_depleted() is True
    assert db.remaining_tokens() == 0


def test_mock_mode_skips_depleted_check(usage_file, monkeypatch):
    monkeypatch.setattr("config.settings.token_budget", 600_000)
    monkeypatch.setattr("config.settings.mock_mode", True)
    usage_file.write_text(
        json.dumps({"date": db.today_key(), "tokens_used": 900_000}),
        encoding="utf-8",
    )
    assert db.is_depleted() is False


def test_api_blocks_start_when_depleted(usage_file, monkeypatch):
    import app as app_mod
    from fastapi.testclient import TestClient

    monkeypatch.setattr("config.settings.token_budget", 100)
    monkeypatch.setattr("config.settings.mock_mode", False)
    usage_file.write_text(
        json.dumps({"date": db.today_key(), "tokens_used": 100}),
        encoding="utf-8",
    )
    client = TestClient(app_mod.app)
    res = client.post("/api/session/start", headers={"Accept-Language": "en"})
    assert res.status_code == 503
    assert "depleted" in res.json()["detail"].lower()
