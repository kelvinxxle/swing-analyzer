"""Structured result of the input-validation gate (M5).

The gate decides **pass or reject** — it never best-effort analyzes. A rejection
carries a single, specific :class:`~app.analysis.RejectionReason` that maps onto
the existing Error screen. M6 calls the gate before running real flaw detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.analysis import RejectionReason


class RejectionCode(str, Enum):
    """The closed set of bad-input reasons. ``value`` is the wire ``code`` that
    the frontend resolves to an icon (kept in lockstep with ``ReasonCode`` and
    ``REASON_ICONS`` in ``frontend/src/lib/analysis.ts``)."""

    UNREADABLE = "unreadable"
    LOW_RESOLUTION = "low_resolution"
    TOO_SHORT = "too_short"
    LIGHTING = "lighting"
    NO_GOLFER = "no_golfer"
    ANGLE = "angle"
    FRAMING = "framing"


@dataclass(frozen=True)
class ValidationResult:
    """Outcome of the validation gate.

    ``rejection`` is ``None`` when the video passed every check; otherwise it is
    the specific reason to surface on the Error screen.
    """

    rejection: RejectionReason | None = None

    @property
    def passed(self) -> bool:
        """True when the video met every guideline and analysis may proceed."""
        return self.rejection is None
