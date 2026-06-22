from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from config import settings

CouncilMemberId = Literal["arabi", "blake", "morrison", "kierkegaard"]

ALL_MEMBERS: tuple[CouncilMemberId, ...] = (
    "arabi",
    "blake",
    "morrison",
    "kierkegaard",
)

DEFAULT_ROSTER: tuple[CouncilMemberId, ...] = (
    "arabi",
    "morrison",
    "kierkegaard",
)


@dataclass(frozen=True)
class MemberProfile:
    id: CouncilMemberId
    glyph: str
    name: str
    years: str
    role: str
    bio_role: str
    bio_pro: str
    css_class: str


MEMBER_PROFILES: dict[CouncilMemberId, MemberProfile] = {
    "arabi": MemberProfile(
        id="arabi",
        glyph="◎",
        name="Ibn Arabi",
        years="1165–1240",
        role="The Threshold",
        bio_role=(
            "Reads what is already opening in this person—not waiting for life to start, "
            "but meeting them in the in-between place where the most real things happen."
        ),
        bio_pro=(
            "Andalusian mystic philosopher whose work on imagination, the threshold, "
            "and the self as mirror remains among the most rigorous metaphysics "
            "of human experience."
        ),
        css_class="arabi",
    ),
    "blake": MemberProfile(
        id="blake",
        glyph="Λ",
        name="William Blake",
        years="1757–1827",
        role="The Visionary",
        bio_role=(
            "Sees what you are imagining—and what you refuse to imagine. "
            "Reads symbol, fire, and the sacred breaking through language."
        ),
        bio_pro=(
            "Visionary poet–artist who wrote and illustrated his own books, "
            "challenging reason, empire, and conventional religion."
        ),
        css_class="blake",
    ),
    "morrison": MemberProfile(
        id="morrison",
        glyph="Ψ",
        name="Toni Morrison",
        years="1931–2019",
        role="The Clearing",
        bio_role=(
            "Sees through language to what is actually present — the word chosen over another word, "
            "what is named and what is carefully left unnamed. Holds the stories that shaped you, "
            "and what must be named before it can be lived. Practical and undeceived: "
            "neither cosmic nor urgent, but clear."
        ),
        bio_pro=(
            "American writer and professor whose fiction and criticism insist "
            "that what is unspoken and unwitnessed still shapes the present."
        ),
        css_class="morrison",
    ),
    "kierkegaard": MemberProfile(
        id="kierkegaard",
        glyph="Δ",
        name="Søren Kierkegaard",
        years="1813–1855",
        role="The Leap",
        bio_role=(
            "Names the dread of freedom—the choice you postpone—and presses you "
            "toward a question that demands you decide how to live."
        ),
        bio_pro=(
            "Danish philosopher and theologian, a founder of existential thought, "
            "who wrote on faith, anxiety, and the leap of choice."
        ),
        css_class="kierkegaard",
    ),
}


def parse_roster(raw: str | None = None) -> list[CouncilMemberId]:
    text = (raw if raw is not None else settings.council_roster).strip()
    if not text:
        return list(DEFAULT_ROSTER)
    ids: list[CouncilMemberId] = []
    for part in text.split(","):
        member_id = part.strip().lower()
        if member_id not in MEMBER_PROFILES:
            raise ValueError(f"Unknown council member: {member_id!r}")
        if member_id not in ids:
            ids.append(member_id)  # type: ignore[arg-type]
    if len(ids) != 3:
        raise ValueError("Council roster must contain exactly 3 members")
    return ids


def display_name(member_id: CouncilMemberId) -> str:
    return MEMBER_PROFILES[member_id].name


def display_label(member_id: CouncilMemberId) -> str:
    profile = MEMBER_PROFILES[member_id]
    return f"{profile.glyph} {profile.name}"


def member_profiles_for_roster(roster: list[CouncilMemberId] | None = None) -> list[dict]:
    roster = roster or parse_roster()
    return [
        {
            "id": profile.id,
            "glyph": profile.glyph,
            "name": profile.name,
            "years": profile.years,
            "role": profile.role,
            "bio_role": profile.bio_role,
            "bio_pro": profile.bio_pro,
            "css_class": profile.css_class,
        }
        for member_id in roster
        if (profile := MEMBER_PROFILES[member_id])
    ]
