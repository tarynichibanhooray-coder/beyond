from __future__ import annotations

import json
import re
from typing import TypeVar

from pydantic import BaseModel

from config import settings

TModel = TypeVar("TModel", bound=BaseModel)


def get_anthropic_client():
    if settings.mock_mode or not settings.anthropic_api_key:
        return None
    from anthropic import Anthropic

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
    return model.model_validate(data)
