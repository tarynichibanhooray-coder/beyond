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
    if not settings.mock_mode and settings.token_budget > 0:
        from utils.daily_budget import record_message_tokens

        record_message_tokens(msg)
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


def extract_json_block(text: str) -> str:
    text = text.strip()
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        return m.group(1).strip()
    return text


def parse_json_response(text: str, model: type[TModel]) -> TModel:
    raw = extract_json_block(text)
    data = json.loads(raw)
    data = coerce_reflect_payload(model, data)
    try:
        return model.model_validate(data)
    except ValidationError:
        if isinstance(data, dict):
            data = coerce_reflect_payload(model, data)
            return model.model_validate(data)
        raise
