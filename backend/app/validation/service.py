"""The validation gate: orchestrates the cheap → pose checks for one video (M5).

``validate_video`` is the single entry point the ``/analyze`` endpoint calls
before analysis, and the gate M6 will reuse before real flaw detection. It runs
the cheap pre-checks first and only pays for the (expensive) pose pass when they
pass — then returns the extracted :class:`PoseSeries` so the caller can reuse it
for detection without decoding the video twice.
"""

from __future__ import annotations

from pathlib import Path

from app.pose import PoseEstimator, PoseSeries, VideoDecodeError, extract_pose_series
from app.validation.checks import check_cheap, check_pose, probe_video
from app.validation.reasons import build_rejection
from app.validation.result import RejectionCode, ValidationResult


def validate_video(
    video_path: str | Path,
    estimator: PoseEstimator | None = None,
) -> tuple[ValidationResult, PoseSeries | None]:
    """Validate one swing video against the input guidelines.

    Args:
        video_path: Path to the (ephemeral) saved upload.
        estimator: Optional pose backend, forwarded to the pose pipeline. Tests
            inject a fake; production uses the default MediaPipe backend.

    Returns:
        ``(result, series)``. ``result.passed`` is ``True`` only when every check
        passed. ``series`` is the extracted pose series when the pose pass ran
        (so M6 can reuse it), or ``None`` when a cheap check rejected first or the
        video could not be decoded.
    """
    cheap = check_cheap(probe_video(video_path))
    if cheap is not None:
        return _reject(cheap), None

    try:
        series = extract_pose_series(video_path, estimator=estimator)
    except VideoDecodeError:
        # The cheap probe decoded a frame, but the full pass found the stream
        # unusable — still a bad, unanalyzable input.
        return _reject(RejectionCode.UNREADABLE), None

    pose = check_pose(series)
    if pose is not None:
        return _reject(pose), series

    return ValidationResult(), series


def _reject(code: RejectionCode) -> ValidationResult:
    return ValidationResult(rejection=build_rejection(code))
