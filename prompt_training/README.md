# Prompt Training — Council AI Instructions

This directory holds **all prompt-training documents** that govern how the council
listen, speak, and forge questions.

Edit these files to change council behavior. Agent code in `agents/` imports from here.

## Active roster

Default council (3 at a time): **Ibn Arabi, Toni Morrison, Søren Kierkegaard**.

Set `COUNCIL_ROSTER` in `.env` to rotate members, e.g. `blake,morrison,kierkegaard`.
Available ids: `arabi`, `blake` (backup), `morrison`, `kierkegaard`.

## Files

| File | Purpose |
|------|---------|
| `core.py` | Installation premise, philosophically therapeutic core, per-member hungers, tensions |
| `prompts.py` | Per-agent reflect, speak, decide, and final-question system prompts |
| `system_blocks.py` | Cached prefix builder (roster-aware) |

## Turn flow (per participant response)

1. **Private reflection** — each roster member thinks alone (parallel).
2. **One spoken turn each** — sequential. They may **disagree**; see `COUNCIL_TENSIONS` in `core.py`.
3. **Formulate question** — the council chooses who asks next and forges the question.

## Core intent

Questions to the participant should be **philosophically therapeutic** at their core:
helping the person process their place in this moment in history and find purpose
and meaning—not clinical therapy, not interview, not comfort for its own sake.
