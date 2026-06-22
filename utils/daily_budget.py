"""Persisted daily token budget (UTC calendar day)."""

from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import settings
from utils.locale import normalize_locale

_LOCK = threading.Lock()
_BUDGET_LOCALE: ContextVar[str] = ContextVar("daily_budget_locale", default="en")

DEPLETED_EN = "The tokens are depleted. Please return tomorrow."
DEPLETED_ES = "Los tokens se han agotado. Vuelve mañana."


def depleted_message(locale: str | None = "en") -> str:
    return DEPLETED_ES if normalize_locale(locale) == "es" else DEPLETED_EN


def usage_file_path() -> Path:
    return settings.transcript_dir / "daily_token_usage.json"


def today_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def message_total_tokens(message: Any) -> int:
    usage = getattr(message, "usage", None)
    if usage is None:
        return 0
    return (
        int(usage.input_tokens or 0)
        + int(usage.output_tokens or 0)
        + int(getattr(usage, "cache_creation_input_tokens", 0) or 0)
        + int(getattr(usage, "cache_read_input_tokens", 0) or 0)
    )


def _load_raw() -> dict[str, Any]:
    path = usage_file_path()
    if not path.is_file():
        return {"date": today_key(), "tokens_used": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"date": today_key(), "tokens_used": 0}
    if data.get("date") != today_key():
        return {"date": today_key(), "tokens_used": 0}
    return {
        "date": today_key(),
        "tokens_used": max(0, int(data.get("tokens_used") or 0)),
    }


def _save_raw(data: dict[str, Any]) -> None:
    path = usage_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def tokens_used_today() -> int:
    with _LOCK:
        return int(_load_raw()["tokens_used"])


def record_message_tokens(message: Any) -> int:
    added = message_total_tokens(message)
    if added <= 0:
        return 0
    with _LOCK:
        data = _load_raw()
        data["tokens_used"] = int(data["tokens_used"]) + added
        _save_raw(data)
    return added


def is_depleted(budget: int | None = None) -> bool:
    cap = settings.token_budget if budget is None else budget
    if cap <= 0 or settings.mock_mode:
        return False
    return tokens_used_today() >= cap


def remaining_tokens(budget: int | None = None) -> int | None:
    cap = settings.token_budget if budget is None else budget
    if cap <= 0:
        return None
    return max(0, cap - tokens_used_today())


def daily_usage_snapshot(budget: int | None = None) -> dict[str, Any]:
    cap = settings.token_budget if budget is None else budget
    used = tokens_used_today()
    rem = remaining_tokens(cap)
    return {
        "date": today_key(),
        "used_tokens": used,
        "remaining_tokens": rem,
        "token_budget": cap,
        "depleted": is_depleted(cap),
    }


def set_budget_locale(locale: str | None) -> None:
    _BUDGET_LOCALE.set(normalize_locale(locale))


def assert_budget_available(locale: str | None = None, budget: int | None = None) -> None:
    loc = normalize_locale(locale) if locale else _BUDGET_LOCALE.get()
    if is_depleted(budget):
        raise RuntimeError(depleted_message(loc))
