"""The `/analyze` response contract + the demo-only canned screens.

Real flaw detection lives in ``app.detection`` (M6) and is what a normal upload
runs. What remains here is the **contract** (``Flaw`` / ``AnalyzeResponse`` /
``AnalysisStatus`` — the shape the frontend renders) and the deliberate
**demo levers**: ``build_response`` returns hardcoded screens for the explicit
``scenario`` form field (``flaws`` / ``clean`` / ``rejected``) so all three result
states stay demoable on the deployed URLs without a real swing video. The levers
are never consulted for a real upload — that path always runs validation then the
real engine.
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
    """One specific reason a video was rejected. ``code`` maps to a frontend icon.

    The code set is kept in lockstep with the frontend ``ReasonCode`` union and
    ``REASON_ICONS`` registry (``frontend/src/lib/analysis.ts``) and the
    ``RejectionCode`` enum (``app.validation.result``); the frontend parser fails
    closed on any code outside this set.
    """

    code: Literal[
        "angle",
        "lighting",
        "no_golfer",
        "unreadable",
        "low_resolution",
        "too_short",
        "framing",
    ]
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


# --- Demo-lever canned screens ----------------------------------------------
# These back the explicit ``scenario`` form field only (never a real upload),
# so the analyzed / no-major-flaws / rejected screens stay demoable on the live
# URLs. A normal upload runs the real M6 engine (``app.detection``) instead.

_DEMO_FLAWS: list[Flaw] = [
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

_DEMO_REJECTION = RejectionReason(
    headline="Invalid Video Input Detected",
    summary=(
        "The video provided does not meet the guidelines required for auto-detection. "
        "Our system cannot accurately diagnose your swing."
    ),
    # Single specific reason, consistent with the real M5 gate (first-failure-wins,
    # one "Reason 01" detail). This is the deliberate dev lever used to demo the
    # rejection screen; genuine rejections come from the validation gate.
    details=[
        RejectionDetail(code="angle", label="Reason 01", title="Angle too wide"),
    ],
)


def build_response(scenario: Scenario) -> AnalyzeResponse:
    """Return the canned demo `/analyze` response for an explicit ``scenario``.

    Used only for the ``scenario`` form-field dev lever, so each result screen is
    demoable on the deployed URLs. Real uploads never reach this — they run the
    M5 gate and then the real M6 engine.
    """
    if scenario is Scenario.REJECTED:
        return AnalyzeResponse(
            status=AnalysisStatus.REJECTED,
            flaws=[],
            reason=_DEMO_REJECTION.model_copy(deep=True),
        )
    if scenario is Scenario.CLEAN:
        return AnalyzeResponse(status=AnalysisStatus.NO_MAJOR_FLAWS, flaws=[])
    return AnalyzeResponse(
        status=AnalysisStatus.ANALYZED,
        flaws=[flaw.model_copy(deep=True) for flaw in _DEMO_FLAWS],
    )
