from __future__ import annotations

from typing import Any, Literal

Locale = Literal["en", "es"]

SPANISH_DIALOGUE_INSTRUCTION = """
The participant's browser is set to Spanish. Write ALL of your output in Spanish:
- every JSON string value (reflection fields, spoken lines, questions, reasoning)
- natural, literary Spanish—not stiff translation
- keep council member names as proper names (Ibn Arabi, Toni Morrison, Kierkegaard, etc.)
- questions must use plain everyday Spanish anyone can understand on first reading
- no untranslated jargon or specialized foreign terms
""".strip()

REPHRASE_SYSTEM: dict[Locale, str] = {
    "en": (
        "Rephrase the council's question so anyone can understand it. "
        "Use plain everyday English. No jargon, no untranslated foreign terms, "
        "no metaphysical vocabulary. One or two short sentences. Output ONLY the "
        "rephrased question text, no quotes or preamble."
    ),
    "es": (
        "Reformula la pregunta del consejo para que cualquiera pueda entenderla. "
        "Usa un español cotidiano y claro. Sin jerga, sin términos extranjeros sin traducir, "
        "sin vocabulario metafísico. Una o dos frases cortas. Devuelve SOLO el texto "
        "de la pregunta reformulada, sin comillas ni preámbulo."
    ),
}

INITIAL_QUESTIONS: dict[Locale, str] = {
    "en": "What brought you here?",
    "es": "¿Qué te trajo aquí?",
}

COUNCIL_PROFILE_I18N: dict[Locale, dict[str, dict[str, str]]] = {
    "en": {
        "arabi": {
            "role": "The Threshold",
            "bio_role": (
                "Reads what is already opening in this person—not waiting for life to start, "
                "but meeting them in the in-between place where the most real things happen."
            ),
            "bio_pro": (
                "Andalusian mystic philosopher whose work on imagination, the threshold, "
                "and the self as mirror remains among the most rigorous metaphysics "
                "of human experience."
            ),
        },
        "morrison": {
            "role": "The Clearing",
            "bio_role": (
                "Sees through language to what is actually present — the word chosen over another word, "
                "what is named and what is carefully left unnamed. Holds the stories that shaped you, "
                "and what must be named before it can be lived. Practical and undeceived: "
                "neither cosmic nor urgent, but clear."
            ),
            "bio_pro": (
                "American writer and professor whose fiction and criticism insist "
                "that what is unspoken and unwitnessed still shapes the present."
            ),
        },
        "kierkegaard": {
            "role": "The Leap",
            "bio_role": (
                "Names the dread of freedom—the choice you postpone—and presses you "
                "toward a question that demands you decide how to live."
            ),
            "bio_pro": (
                "Danish philosopher and theologian, a founder of existential thought, "
                "who wrote on faith, anxiety, and the leap of choice."
            ),
        },
    },
    "es": {
        "arabi": {
            "role": "El Umbral",
            "bio_role": (
                "Lee lo que ya se abre en esta persona—no esperando a que la vida comience, "
                "sino encontrándola en el lugar intermedio donde ocurren las cosas más reales."
            ),
            "bio_pro": (
                "Filósofo místico andalusí cuya obra sobre la imaginación, el umbral "
                "y el yo como espejo sigue siendo una de las metafísicas más rigurosas "
                "de la experiencia humana."
            ),
        },
        "morrison": {
            "role": "El Claro",
            "bio_role": (
                "Ve a través del lenguaje lo que realmente está presente: la palabra elegida "
                "frente a otra, lo que se nombra y lo que se deja cuidadosamente sin nombrar. "
                "Sostiene las historias que te formaron y lo que debe nombrarse antes de poder vivirse. "
                "Práctica y sin ilusiones: ni cósmica ni urgente, pero clara."
            ),
            "bio_pro": (
                "Escritora y profesora estadounidense cuya ficción y crítica insisten "
                "en que lo no dicho y lo no presenciado sigue moldeando el presente."
            ),
        },
        "kierkegaard": {
            "role": "El Salto",
            "bio_role": (
                "Nombra el pavor de la libertad—la elección que pospones—y te empuja "
                "hacia una pregunta que exige decidir cómo vivir."
            ),
            "bio_pro": (
                "Filósofo y teólogo danés, fundador del pensamiento existencial, "
                "que escribió sobre la fe, la angustia y el salto de la elección."
            ),
        },
    },
}

EXPORT_UI: dict[Locale, dict[str, str]] = {
    "en": {
        "page_title": "Before — session",
        "heading": "In This Time Before",
        "question": "Question",
        "observations": "Observations",
        "conversation": "Conversation",
        "asks_next": "asks next",
        "final_question": "Your final question",
        "footer": "Generated from In This Time Before",
        "council": "Council",
    },
    "es": {
        "page_title": "Before — sesión",
        "heading": "En este tiempo previo",
        "question": "Pregunta",
        "observations": "Observaciones",
        "conversation": "Conversación",
        "asks_next": "pregunta a continuación",
        "final_question": "Tu pregunta final",
        "footer": "Generado desde In This Time Before",
        "council": "Consejo",
    },
}


def resolve_locale(accept_language: str | None) -> Locale:
    if not accept_language:
        return "en"
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if tag.startswith("es"):
            return "es"
        if tag.startswith("en"):
            return "en"
    return "en"


def normalize_locale(locale: str | None) -> Locale:
    return "es" if locale and str(locale).lower().startswith("es") else "en"


def apply_locale_system(system: str | list[dict[str, Any]], locale: str | None) -> str | list[dict[str, Any]]:
    if normalize_locale(locale) != "es":
        return system
    if isinstance(system, str):
        return f"{system.rstrip()}\n\n{SPANISH_DIALOGUE_INSTRUCTION}"
    if isinstance(system, list):
        blocks = [dict(block) for block in system]
        last = blocks[-1]
        last["text"] = f"{last.get('text', '').rstrip()}\n\n{SPANISH_DIALOGUE_INSTRUCTION}"
        blocks[-1] = last
        return blocks
    return system


def initial_question(locale: Locale) -> str:
    return INITIAL_QUESTIONS[locale]


def export_ui(locale: Locale) -> dict[str, str]:
    return EXPORT_UI[locale]


def localize_member_profile(member: dict, locale: Locale) -> dict:
    patch = COUNCIL_PROFILE_I18N[locale].get(member["id"])
    if not patch:
        return member
    return {**member, **patch}


def localize_member_profiles(members: list[dict], locale: Locale) -> list[dict]:
    return [localize_member_profile(m, locale) for m in members]
