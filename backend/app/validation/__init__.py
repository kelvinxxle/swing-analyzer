"""Input-validation gate (M5).

Rejects videos that don't meet the capture guidelines with a single specific
reason (never best-effort analyzes a bad video, per the PRD). Built on the M4
pose pipeline; reused by M6 as the gate before real flaw detection.
"""

from __future__ import annotations

from app.validation.checks import VideoProbe, check_cheap, check_pose, probe_video
from app.validation.reasons import build_rejection
from app.validation.result import RejectionCode, ValidationResult
from app.validation.service import validate_video

__all__ = [
    "RejectionCode",
    "ValidationResult",
    "VideoProbe",
    "build_rejection",
    "check_cheap",
    "check_pose",
    "probe_video",
    "validate_video",
]
