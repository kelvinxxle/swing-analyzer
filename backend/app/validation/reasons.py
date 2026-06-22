"""Maps a :class:`RejectionCode` to the Error-screen payload (M5).

Single source of truth for rejection copy. Each bad-input case produces one
specific, named reason; the headline/summary stay the calm, generic frame from
``docs/design/screens/04-error-rejection.png`` while the per-reason title is
direct and points at the fix.
"""

from __future__ import annotations

from app.analysis import RejectionDetail, RejectionReason
from app.validation.result import RejectionCode

_HEADLINE = "Invalid Video Input Detected"

_SUMMARY = (
    "The video provided does not meet the guidelines required for auto-detection. "
    "Our system cannot accurately diagnose your swing."
)

# Direct, expert, encouraging titles — one per code, matching the Error screen.
_TITLES: dict[RejectionCode, str] = {
    RejectionCode.UNREADABLE: "Unreadable video",
    RejectionCode.LOW_RESOLUTION: "Resolution too low",
    RejectionCode.TOO_SHORT: "Clip too short",
    RejectionCode.LIGHTING: "Low lighting",
    RejectionCode.NO_GOLFER: "No golfer detected",
    RejectionCode.ANGLE: "Angle too wide",
    RejectionCode.FRAMING: "Swing out of frame",
}


def build_rejection(code: RejectionCode) -> RejectionReason:
    """Build the single-reason rejection payload for ``code``."""
    return RejectionReason(
        headline=_HEADLINE,
        summary=_SUMMARY,
        details=[
            RejectionDetail(code=code.value, label="Reason 01", title=_TITLES[code]),
        ],
    )
