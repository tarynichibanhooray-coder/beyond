from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from agents.roster import MEMBER_PROFILES, display_label, display_name, member_profiles_for_roster

ROOT = Path(__file__).resolve().parent.parent
EXPORT_CSS_PATH = ROOT / "static" / "export.css"

REFLECTION_FIELD: dict[str, str] = {
    "arabi": "disclosure_read",
    "blake": "vision_read",
    "morrison": "witness_read",
    "kierkegaard": "dread_read",
}


_EMDASH_GLUE = re.compile(r"(\S)\s*—\s*(\S)")


def space_em_dashes(text: str | None) -> str:
    if not text:
        return text or ""
    while True:
        updated = _EMDASH_GLUE.sub(r"\1 — \2", text)
        if updated == text:
            return updated
        text = updated


_ROMAN_TURNS = ("", "I", "II", "III")


def _turn_heading(turn_index: int) -> str:
    if 1 <= turn_index <= 3:
        return _ROMAN_TURNS[turn_index]
    return str(turn_index)


def _esc(text: str | None) -> str:
    return html.escape(space_em_dashes(text), quote=True)


def _parse_history(history: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str | None, str | None]:
    turns: list[dict[str, Any]] = []
    final_question: str | None = None
    final_reasoning: str | None = None
    for item in history:
        if "question" in item and "transcript" in item:
            turns.append(item)
            continue
        final = item.get("final_question")
        if isinstance(final, dict):
            final_question = final.get("final_question") or None
            final_reasoning = final.get("reasoning") or None
    return turns, final_question, final_reasoning


def most_recent_question(history: list[dict[str, Any]]) -> str | None:
    for item in history:
        session = item.get("session")
        if isinstance(session, dict):
            q = session.get("current_question") or session.get("initial_question")
            if q:
                return str(q)
    turns, _, _ = _parse_history(history)
    if turns:
        last = turns[-1]
        return str(last.get("next_question") or last.get("question") or "") or None
    return None


def _slug_from_question(text: str, *, max_words: int = 5, max_len: int = 48) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if not words:
        return ""
    slug = "-".join(words[:max_words])
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug


def export_filename_from_history(
    history: list[dict[str, Any]],
    *,
    fallback_stem: str | None = None,
) -> str:
    recent = most_recent_question(history)
    if recent:
        slug = _slug_from_question(recent)
        if slug:
            return f"{slug}.html"
    if fallback_stem:
        return f"{fallback_stem}.html"
    return "in-this-time-before-session.html"


def _session_label_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    match = re.search(r"session-(\d{8})-(\d{6})", filename)
    if not match:
        return None
    date_part, time_part = match.groups()
    return f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]} · {time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"


def _render_turn(turn: dict[str, Any], turn_index: int, members: list[dict[str, Any]]) -> str:
    roster = turn.get("council_roster") or [m["id"] for m in members]
    member_map = {m["id"]: m for m in members}
    reflections = turn.get("reflections") or {}

    thought_cards: list[str] = []
    for member_id in roster:
        profile = member_map.get(member_id, {"id": member_id, "name": member_id, "css_class": member_id})
        css_class = profile.get("css_class") or member_id
        field = REFLECTION_FIELD.get(member_id, "")
        reflection = reflections.get(member_id) or {}
        text = reflection.get(field, "") if field else ""
        thought_cards.append(
            f'<div class="thought {_esc(css_class)}">'
            f"<strong>{_esc(profile.get('name', member_id))}</strong>"
            f"<p>{_esc(text)}</p></div>"
        )

    conversation_lines: list[str] = []
    for entry in turn.get("conversation") or []:
        speaker = entry.get("speaker") or ""
        label = display_label(speaker) if speaker in MEMBER_PROFILES else speaker
        conversation_lines.append(
            f'<div class="conv-line line-{_esc(speaker)}">'
            f"<strong>{_esc(label)}</strong> {_esc(entry.get('text', ''))}</div>"
        )

    chosen = turn.get("chosen_asker") or ""
    chosen_name = display_name(chosen) if chosen in MEMBER_PROFILES else (chosen or "Council")

    return (
        f'<div class="turn">'
        f"<h2>{_turn_heading(turn_index)}</h2>"
        f'<article class="feed-question">'
        f"<h3>Question</h3>"
        f'<p class="qtext">{_esc(turn.get("question", ""))}</p></article>'
        f'<p class="feed-answer">{_esc(turn.get("transcript", ""))}</p>'
        f'<article class="private-thoughts">'
        f"<h3>Observations</h3>"
        f'<div class="thought-grid">{"".join(thought_cards)}</div></article>'
        f'<article class="conversation">'
        f"<h3>Conversation</h3>"
        f'<div class="conv-lines">{"".join(conversation_lines)}</div></article>'
        f'<article class="forged">'
        f"<h3>{_esc(chosen_name)} asks next</h3>"
        f'<p class="q-next">{_esc(turn.get("next_question", ""))}</p></article>'
        f"</div>"
    )


def build_session_export_html(
    history: list[dict[str, Any]],
    *,
    members: list[dict[str, Any]] | None = None,
    session_label: str | None = None,
    final_question: str | None = None,
    final_reasoning: str | None = None,
) -> str:
    turns, parsed_final_q, parsed_final_r = _parse_history(history)
    if not members and turns:
        roster = turns[0].get("council_roster") or []
        members = member_profiles_for_roster(roster)  # type: ignore[arg-type]
    members = members or member_profiles_for_roster()

    final_q = final_question if final_question is not None else parsed_final_q
    final_r = final_reasoning if final_reasoning is not None else parsed_final_r

    roster_html = "".join(
        f'<article class="council-member {_esc(m["css_class"])}">'
        f'<h3>{_esc(m["glyph"])} {_esc(m["name"])} '
        f'<span class="role">{_esc(m["role"])}</span></h3>'
        f'<p class="bio-role">{_esc(m.get("bio_role", ""))}</p>'
        f'<p class="bio-pro">{_esc(m.get("bio_pro", ""))}</p>'
        f'<p class="years">{_esc(m.get("years", ""))}</p>'
        f"</article>"
        for m in members
    )

    turns_html = "".join(_render_turn(turn, idx, members) for idx, turn in enumerate(turns, start=1))

    final_html = ""
    if final_q:
        final_html = (
            '<section class="final">'
            "<h2>Your final question</h2>"
            f'<p class="final-q">{_esc(final_q)}</p>'
            "</section>"
        )

    meta_line = f'<p class="session-meta">{_esc(session_label)}</p>' if session_label else ""

    css = EXPORT_CSS_PATH.read_text(encoding="utf-8")

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        "  <title>Before — session</title>\n"
        f"  <style>\n{css}\n  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <main class="wrap">\n'
        '    <header class="head-title">\n'
        "      <h1>In This Time Before</h1>\n"
        f"      {meta_line}\n"
        "    </header>\n"
        f'    <section class="council-roster">{roster_html}</section>\n'
        f'    <section class="log">{turns_html}</section>\n'
        f"    {final_html}\n"
        '    <footer class="export-footer">Generated from In This Time Before</footer>\n'
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def export_transcript_file(path: Path, *, session_label: str | None = None) -> tuple[str, str]:
    history = json.loads(path.read_text(encoding="utf-8"))
    label = session_label or _session_label_from_filename(path.name)
    html_out = build_session_export_html(history, session_label=label)
    filename = export_filename_from_history(history, fallback_stem=path.stem)
    return html_out, filename
