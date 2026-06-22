from typing import Literal

from pydantic import BaseModel, Field

AskerName = Literal["arabi", "blake", "morrison", "kierkegaard"]


class ArabiOutput(BaseModel):
    disclosure_read: str
    barzakh_note: str
    mirror_read: str
    color_intensity: int = Field(ge=0, le=100)


class LambdaOutput(BaseModel):
    vision_read: str
    symbols: list[str]
    blocked_imagination: str
    color_intensity: int = Field(ge=0, le=100)


class PsiOutput(BaseModel):
    witness_read: str
    carried_story: str
    color_intensity: int = Field(ge=0, le=100)


class KierkegaardReflection(BaseModel):
    dread_read: str
    avoided_choice: str
    leap_pressure: str
    color_intensity: int = Field(ge=0, le=100)


class ConversationLine(BaseModel):
    speaker: AskerName
    text: str


class CouncilDecision(BaseModel):
    chosen_asker: AskerName
    next_question: str
    rationale: str = ""


class CouncilTurnResult(BaseModel):
    reflections: dict[str, dict]
    conversation: list[ConversationLine]
    decision: CouncilDecision


class DeltaFinal(BaseModel):
    final_question: str
    reasoning: str


class TurnContext(BaseModel):
    question: str
    transcript: str
    locale: str = "en"
    bpm_window: list[tuple[float, float]] = Field(
        default_factory=list,
        description="(timestamp_offset_sec, bpm) samples for this turn",
    )
