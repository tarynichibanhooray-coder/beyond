"""Anthropic prompt caching — shared static prefix for all council calls."""

from __future__ import annotations

from agents.roster import CouncilMemberId, parse_roster
from prompt_training.core import (
    ARABI_HUNGER,
    BLAKE_HUNGER,
    COUNCIL_FRAME,
    KIERKEGAARD_HUNGER,
    MORRISON_HUNGER,
)

HUNGER_BY_MEMBER: dict[CouncilMemberId, str] = {
    "arabi": ARABI_HUNGER,
    "blake": BLAKE_HUNGER,
    "morrison": MORRISON_HUNGER,
    "kierkegaard": KIERKEGAARD_HUNGER,
}


def cached_system_base(roster: list[CouncilMemberId] | None = None) -> str:
    roster = roster or parse_roster()
    hungers = "\n".join(HUNGER_BY_MEMBER[member_id] for member_id in roster)
    return f"{COUNCIL_FRAME}\n{hungers}"


# Default roster prefix (used when build_system() called without explicit roster).
CACHED_SYSTEM_BASE = cached_system_base()


def build_system(suffix: str, roster: list[CouncilMemberId] | None = None) -> list[dict]:
    """System blocks: cached static prefix + uncached call-specific tail."""
    base = cached_system_base(roster) if roster else CACHED_SYSTEM_BASE
    return [
        {
            "type": "text",
            "text": base,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": suffix.strip(),
        },
    ]
