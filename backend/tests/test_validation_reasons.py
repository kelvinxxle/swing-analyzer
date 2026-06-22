"""Tests for the rejection-reason catalog (M5).

Guards the frontend/backend lockstep: every :class:`RejectionCode` resolves to a
single, well-formed reason whose ``code`` is in the closed set the frontend
parser accepts.
"""

from __future__ import annotations

import pytest

from app.validation.reasons import build_rejection
from app.validation.result import RejectionCode

# Mirrors the frontend `REASON_CODES` array in `frontend/src/lib/analysis.ts`.
_FRONTEND_CODES = {
    "angle",
    "lighting",
    "no_golfer",
    "unreadable",
    "low_resolution",
    "too_short",
    "framing",
}


@pytest.mark.parametrize("code", list(RejectionCode))
def test_build_rejection_is_well_formed(code: RejectionCode) -> None:
    reason = build_rejection(code)

    assert reason.headline.strip()
    assert reason.summary.strip()
    assert len(reason.details) == 1

    detail = reason.details[0]
    assert detail.code == code.value
    assert detail.label == "Reason 01"
    assert detail.title.strip()


def test_codes_are_in_lockstep_with_the_frontend() -> None:
    assert {code.value for code in RejectionCode} == _FRONTEND_CODES
