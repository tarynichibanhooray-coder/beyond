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
        or "Something in them is opening toward a life they have not yet claimed.",
        "avoided_choice": _first_str(
            data,
            "avoided_choice",
            "avoided_leap",
            "choice_avoided",
            "blocked_imagination",
            "carried_story",
        )
        or "They hesitate before a good they already recognize.",
        "leap_pressure": _first_str(
            data,
            "leap_pressure",
            "leap_read",
            "leap",
            "mirror_read",
            "barzakh_note",
            "blocked_imagination",
        )
        or "Becoming themselves is nearer than they think—and worth trusting.",
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
        or "Something is disclosing itself through their words.",
        "barzakh_note": _first_str(
            data, "barzakh_note", "threshold_note", "leap_pressure"
        )
        or "They stand in a threshold not yet crossed.",
        "mirror_read": _first_str(
            data, "mirror_read", "mirror_clarity", "carried_story", "avoided_choice"
        )
        or "Something larger than biography moves through this moment.",
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
        or "They are asking to be seen without naming what they need seen.",
        "carried_story": _first_str(
            data,
            "carried_story",
            "barzakh_note",
            "avoided_choice",
            "blocked_imagination",
        )
        or "Older voices may still be measuring whether they are allowed to be lost.",
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
        symbols = ["closed door", "dim lamp"]

    return {
        "vision_read": _first_str(
            data,
            "vision_read",
            "disclosure_read",
            "witness_read",
            "dread_read",
        )
        or "A vision strains beneath their words.",
        "symbols": symbols,
        "blocked_imagination": _first_str(
            data,
            "blocked_imagination",
            "avoided_choice",
            "carried_story",
            "barzakh_note",
        )
        or "They have learned to distrust their own seeing.",
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


def coerce_reflect_payload(model: type, data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    coercer = REFLECT_COERCERS.get(model)
    if coercer is None:
        return data
    return coercer(data)
