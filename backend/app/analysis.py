"""Mock swing-analysis logic for the M3 walking skeleton.

No real computer vision yet (that lands in M4–M6). `/analyze` returns hardcoded
results for three demoable cases — a happy path with 2–3 flaws, a valid
"no major flaws detected" result, and a rejected bad-input result with a reason.

The case is chosen deterministically: an explicit ``scenario`` wins, otherwise it
is inferred from the uploaded filename so all three paths are demoable on the
deployed URLs just by naming the file.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Scenario(str, Enum):
    """Which mock result to return."""

    FLAWS = "flaws"
    CLEAN = "clean"
    REJECTED = "rejected"


class AnalysisStatus(str, Enum):
    """Top-level outcome of an analysis, mapped to a frontend screen."""

    ANALYZED = "analyzed"
    NO_MAJOR_FLAWS = "no_major_flaws"
    REJECTED = "rejected"


class Flaw(BaseModel):
    """A single detected swing flaw with its prioritized fix tip (text only)."""

    priority: int = Field(ge=1)
    category: str
    title: str
    description: str
    fix: str


class RejectionDetail(BaseModel):
    """One specific reason a video was rejected. ``code`` maps to a frontend icon."""

    code: Literal["angle", "lighting", "no_golfer"]
    label: str
    title: str


class RejectionReason(BaseModel):
    """The rejection payload shown on the error screen."""

    headline: str
    summary: str
    details: list[RejectionDetail]


class AnalyzeResponse(BaseModel):
    """The `/analyze` contract: ``{ status, flaws[], reason? }``."""

    status: AnalysisStatus
    flaws: list[Flaw]
    reason: RejectionReason | None = None


# --- Mock catalog -----------------------------------------------------------

_MOCK_FLAWS: list[Flaw] = [
    Flaw(
        priority=1,
        category="Posture Loss",
        title="Early Extension",
        description=(
            "Your hips move closer to the ball during the downswing, forcing you to "
            "stand up and lose your posture, which leads to inconsistent contact and "
            "loss of power."
        ),
        fix=(
            "Keep your glutes against an imaginary wall during the downswing. Feel your "
            "left hip push back and clear, rather than thrusting forward toward the ball."
        ),
    ),
    Flaw(
        priority=2,
        category="Path",
        title="Over the Top",
        description=(
            "Your downswing starts with the upper body and shoulders spinning out, "
            "causing the club path to travel outside-in relative to the target line, "
            "resulting in pulls or weak slices."
        ),
        fix=(
            "Initiate the downswing from the ground up. Allow your arms to 'drop' into "
            "the slot naturally before your shoulders begin to aggressively rotate "
            "toward the target."
        ),
    ),
]

_MOCK_REJECTION = RejectionReason(
    headline="Invalid Video Input Detected",
    summary=(
        "The video provided does not meet the guidelines required for auto-detection. "
        "Our system cannot accurately diagnose your swing."
    ),
    details=[
        RejectionDetail(code="angle", label="Reason 01", title="Angle too wide"),
        RejectionDetail(code="lighting", label="Reason 02", title="Low lighting"),
        RejectionDetail(code="no_golfer", label="Reason 03", title="No golfer detected"),
    ],
)

# Filename keywords → scenario, for demoable inference when no explicit scenario.
_REJECT_HINTS = ("reject", "bad", "dark", "wrong", "angle", "blurry")
_CLEAN_HINTS = ("clean", "good", "perfect", "pro", "ideal")


def select_scenario(filename: str | None, scenario: Scenario | None) -> Scenario:
    """Pick the mock scenario: explicit override wins, else infer from the filename."""
    if scenario is not None:
        return scenario

    name = (filename or "").lower()
    if any(hint in name for hint in _REJECT_HINTS):
        return Scenario.REJECTED
    if any(hint in name for hint in _CLEAN_HINTS):
        return Scenario.CLEAN
    return Scenario.FLAWS


def build_response(scenario: Scenario) -> AnalyzeResponse:
    """Return the mock `/analyze` response for a chosen scenario."""
    if scenario is Scenario.REJECTED:
        return AnalyzeResponse(
            status=AnalysisStatus.REJECTED,
            flaws=[],
            reason=_MOCK_REJECTION.model_copy(deep=True),
        )
    if scenario is Scenario.CLEAN:
        return AnalyzeResponse(status=AnalysisStatus.NO_MAJOR_FLAWS, flaws=[])
    return AnalyzeResponse(
        status=AnalysisStatus.ANALYZED,
        flaws=[flaw.model_copy(deep=True) for flaw in _MOCK_FLAWS],
    )
