"""Map mis-keyed model JSON (from shared council cache bleed) to expected schemas."""

from __future__ import annotations

from typing import Any

from models import ArabiOutput, KierkegaardReflection, LambdaOutput, PsiOutput


def _first_str(data: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _first_int(data: dict[str, Any], *keys: str, default: int = 50) -> int:
    for key in keys:
        value = data.get(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            return max(0, min(100, int(value)))
        if isinstance(value, str) and value.strip().isdigit():
            return max(0, min(100, int(value.strip())))
    return default


def coerce_kierkegaard_reflect(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "dread_read": _first_str(
            data,
            "dread_read",
            "tajalli_read",
            "disclosure_read",
            "witness_read",
            "vision_read",
            "dread",
        )
        or "There is real feeling in what they said, even where the words ran out.",
        "avoided_choice": _first_str(
            data,
            "avoided_choice",
            "avoided_leap",
            "choice_avoided",
            "blocked_imagination",
            "carried_story",
        )
        or "Nothing here reads as a refusal, only an answer still finding its shape.",
        "leap_pressure": _first_str(
            data,
            "leap_pressure",
            "leap_read",
            "leap",
            "mirror_read",
            "barzakh_note",
            "blocked_imagination",
        )
        or "Whatever they choose next is theirs to choose.",
        "color_intensity": _first_int(
            data, "color_intensity", "mirror_clarity", "intensity"
        ),
    }


def coerce_arabi_reflect(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "disclosure_read": _first_str(
            data,
            "disclosure_read",
            "tajalli_read",
            "witness_read",
            "vision_read",
            "dread_read",
        )
        or "Their words are still worth sitting with, even without a clean read.",
        "barzakh_note": _first_str(
            data, "barzakh_note", "threshold_note", "leap_pressure"
        )
        or "They are exactly where they are, and that is enough to begin from.",
        "mirror_read": _first_str(
            data, "mirror_read", "mirror_clarity", "carried_story", "avoided_choice"
        )
        or "This moment belongs only to them.",
        "color_intensity": _first_int(
            data, "color_intensity", "mirror_clarity", "intensity"
        ),
    }


def coerce_psi_reflect(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "witness_read": _first_str(
            data,
            "witness_read",
            "disclosure_read",
            "tajalli_read",
            "dread_read",
            "vision_read",
        )
        or "Their words deserve to be taken exactly as given.",
        "carried_story": _first_str(
            data,
            "carried_story",
            "barzakh_note",
            "avoided_choice",
            "blocked_imagination",
        )
        or "What they carry is theirs to name, not ours to guess.",
        "color_intensity": _first_int(
            data, "color_intensity", "mirror_clarity", "intensity"
        ),
    }


def coerce_lambda_reflect(data: dict[str, Any]) -> dict[str, Any]:
    symbols = data.get("symbols")
    if not isinstance(symbols, list):
        symbols = []
    symbols = [str(s).strip() for s in symbols if str(s).strip()][:3]
    if not symbols:
        symbols = ["unlit window", "quiet flame"]

    return {
        "vision_read": _first_str(
            data,
            "vision_read",
            "disclosure_read",
            "witness_read",
            "dread_read",
        )
        or "There is an image in their words worth staying with, even unclear.",
        "symbols": symbols,
        "blocked_imagination": _first_str(
            data,
            "blocked_imagination",
            "avoided_choice",
            "carried_story",
            "barzakh_note",
        )
        or "Nothing here suggests they've stopped seeing — only that the words are still catching up.",
        "color_intensity": _first_int(
            data, "color_intensity", "mirror_clarity", "intensity"
        ),
    }


REFLECT_COERCERS = {
    KierkegaardReflection: coerce_kierkegaard_reflect,
    ArabiOutput: coerce_arabi_reflect,
    PsiOutput: coerce_psi_reflect,
    LambdaOutput: coerce_lambda_reflect,
}

REFLECT_COERCERS_BY_NAME = {
    "KierkegaardReflection": coerce_kierkegaard_reflect,
    "ArabiOutput": coerce_arabi_reflect,
    "PsiOutput": coerce_psi_reflect,
    "LambdaOutput": coerce_lambda_reflect,
}


def _coercer_for_model(model: type) -> Any | None:
    return REFLECT_COERCERS.get(model) or REFLECT_COERCERS_BY_NAME.get(getattr(model, "__name__", ""))


def coerce_reflect_payload(model: type, data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    coercer = _coercer_for_model(model)
    if coercer is None:
        return data
    return coercer(data)
