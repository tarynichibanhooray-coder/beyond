from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from agents._reflect_coerce import coerce_reflect_payload
from config import settings

TModel = TypeVar("TModel", bound=BaseModel)


def create_message(client, *, label: str, **kwargs):
    system = kwargs.get("system")
    if isinstance(system, list) and not settings.prompt_cache:
        kwargs = {
            **kwargs,
            "system": "\n\n".join(block["text"] for block in system),
        }
    if not settings.mock_mode and settings.token_budget > 0:
        from utils.daily_budget import assert_budget_available

        assert_budget_available()
    msg = client.messages.create(**kwargs)
    from utils.usage import record_message_usage

    record_message_usage(msg, label)
    from utils.usage import log_api_usage

    log_api_usage(msg, label, budget=settings.token_budget)
    return msg


def get_anthropic_client():
    if settings.mock_mode or not settings.anthropic_api_key.strip():
        return None
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise RuntimeError(
            "Live AI requires: pip install -r requirements-anthropic.txt "
            "(or set MOCK_MODE=true to test without API calls)."
        ) from exc

    return Anthropic(api_key=settings.anthropic_api_key)


def _first_json_object(text: str) -> str | None:
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escape = False
        for idx in range(start, len(text)):
            ch = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : idx + 1].strip()
        start = text.find("{", start + 1)
    return None


def extract_json_block(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    return _first_json_object(text) or text


def parse_json_response(text: str, model: type[TModel]) -> TModel:
    raw = extract_json_block(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        snippet = raw[:160].replace("\n", " ").strip() or "<empty>"
        raise ValueError(f"Model returned invalid JSON for {model.__name__}: {snippet}") from exc
    data = coerce_reflect_payload(model, data)
    try:
        return model.model_validate(data)
    except ValidationError:
        if isinstance(data, dict):
            data = coerce_reflect_payload(model, data)
            return model.model_validate(data)
        raise
