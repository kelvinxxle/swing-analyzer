"""The individual validation checks (M5).

Two groups, deliberately ordered cheap → expensive:

* **Cheap pre-checks** run on the decoded video before the pose pass: is it
  decodable, big enough, long enough, bright enough. They consume a lightweight
  :class:`VideoProbe` (a few sampled frames + metadata) so they stay pure and
  unit-testable without a real clip.
* **Pose checks** consume the M4 :class:`~app.pose.schema.PoseSeries`: is there a
  golfer, is it the prescribed down-the-line angle, is the swing fully in frame.

Every check returns a :class:`RejectionCode` (the first thing wrong) or ``None``.
No check best-effort analyzes — a failure is a hard reject per the PRD.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy.typing as npt

from app.pose.schema import LandmarkName, PoseSeries
from app.validation import thresholds as T
from app.validation.result import RejectionCode

# Core torso landmarks: the most reliable signal that a framed golfer is present.
_CORE_LANDMARKS = (
    LandmarkName.LEFT_SHOULDER,
    LandmarkName.RIGHT_SHOULDER,
    LandmarkName.LEFT_HIP,
    LandmarkName.RIGHT_HIP,
)

# Extremities that must stay in frame for the whole swing (head, hands, feet).
_FRAMING_LANDMARKS = (
    LandmarkName.NOSE,
    LandmarkName.LEFT_WRIST,
    LandmarkName.RIGHT_WRIST,
    LandmarkName.LEFT_ANKLE,
    LandmarkName.RIGHT_ANKLE,
    LandmarkName.LEFT_FOOT_INDEX,
    LandmarkName.RIGHT_FOOT_INDEX,
)


@dataclass(frozen=True)
class VideoProbe:
    """Cheap, decode-only summary of a video for the pre-checks.

    ``readable`` is ``False`` when OpenCV cannot open the file or decode a frame.
    Dimensions / duration are ``0`` when the container omits that metadata; the
    checks treat unknown values as "can't tell" and do not reject on them, to
    avoid false rejections of otherwise-valid clips.
    """

    readable: bool
    width: int
    height: int
    duration_s: float
    mean_luma: float


def probe_video(path: str | Path) -> VideoProbe:
    """Open ``path`` and read just enough to run the cheap pre-checks."""
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return VideoProbe(False, 0, 0, 0.0, 0.0)

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        ok, first = capture.read()
        if not ok or first is None:
            return VideoProbe(False, 0, 0, 0.0, 0.0)

        duration_s = (frame_count / fps) if fps > 0 and frame_count > 0 else 0.0
        mean_luma = _sample_mean_luma(capture, first, frame_count)
        return VideoProbe(True, max(width, 0), max(height, 0), duration_s, mean_luma)
    finally:
        capture.release()


def _sample_mean_luma(
    capture: cv2.VideoCapture, first_bgr: npt.NDArray[Any], frame_count: int
) -> float:
    """Mean grayscale luma (0–255) over a few evenly-spaced frames.

    Seeks to spread the samples across the clip; falls back to whatever decoded
    frames are reachable. The already-decoded first frame is always included so
    a single-frame or unseekable clip still yields a brightness estimate.
    """
    lumas = [float(cv2.cvtColor(first_bgr, cv2.COLOR_BGR2GRAY).mean())]

    if frame_count > 1:
        n = min(T.BRIGHTNESS_SAMPLE_FRAMES, frame_count)
        positions = [round(i * (frame_count - 1) / max(n - 1, 1)) for i in range(1, n)]
        for pos in positions:
            capture.set(cv2.CAP_PROP_POS_FRAMES, float(pos))
            ok, frame = capture.read()
            if ok and frame is not None:
                lumas.append(float(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).mean()))

    return sum(lumas) / len(lumas)


def check_cheap(probe: VideoProbe) -> RejectionCode | None:
    """Run the cheap pre-checks in order; return the first failure or ``None``."""
    if not probe.readable:
        return RejectionCode.UNREADABLE

    shorter_side = min(probe.width, probe.height)
    if shorter_side > 0 and shorter_side < T.MIN_SHORTER_SIDE_PX:
        return RejectionCode.LOW_RESOLUTION

    if probe.duration_s > 0.0 and probe.duration_s < T.MIN_DURATION_S:
        return RejectionCode.TOO_SHORT

    if probe.mean_luma < T.MIN_MEAN_LUMA:
        return RejectionCode.LIGHTING

    return None


def check_pose(series: PoseSeries) -> RejectionCode | None:
    """Run the pose-based checks in order; return the first failure or ``None``."""
    no_golfer = _check_no_golfer(series)
    if no_golfer is not None:
        return no_golfer
    # The engine needs a minimum number of detected frames to segment the swing.
    # Reject a too-sparse capture here (as too_short) so the user gets a clear
    # 200/rejected rather than a downstream 500 from the engine. Mirrors the
    # engine's MIN_DETECTED_FRAMES floor (aliased in thresholds).
    if len(series.detected_frames) < T.MIN_ANALYZABLE_DETECTED_FRAMES:
        return RejectionCode.TOO_SHORT
    # Angle / framing are only meaningful once a golfer is reliably present.
    if _check_angle(series) is not None:
        return RejectionCode.ANGLE
    if _check_framing(series) is not None:
        return RejectionCode.FRAMING
    return None


def _check_no_golfer(series: PoseSeries) -> RejectionCode | None:
    detected = series.detected_frames
    if series.sampled_count == 0:
        return RejectionCode.NO_GOLFER

    if len(detected) / series.sampled_count < T.MIN_DETECTED_FRAME_RATIO:
        return RejectionCode.NO_GOLFER

    visibilities = [
        landmarks[name].visibility
        for frame in detected
        if (landmarks := frame.landmarks) is not None
        for name in _CORE_LANDMARKS
    ]
    if visibilities and sum(visibilities) / len(visibilities) < T.MIN_MEAN_VISIBILITY:
        return RejectionCode.NO_GOLFER

    return None


def _check_angle(series: PoseSeries) -> RejectionCode | None:
    spans = [
        abs(
            landmarks[LandmarkName.LEFT_SHOULDER].x
            - landmarks[LandmarkName.RIGHT_SHOULDER].x
        )
        for frame in series.detected_frames
        if (landmarks := frame.landmarks) is not None
    ]
    if spans and sum(spans) / len(spans) > T.MAX_SHOULDER_SPAN_X:
        return RejectionCode.ANGLE
    return None


def _check_framing(series: PoseSeries) -> RejectionCode | None:
    detected = series.detected_frames
    if not detected:
        return None

    low, high = -T.OUT_OF_FRAME_TOL, 1.0 + T.OUT_OF_FRAME_TOL
    out_of_frame = 0
    for frame in detected:
        landmarks = frame.landmarks
        if landmarks is None:
            continue
        if any(
            not (low <= landmarks[name].x <= high and low <= landmarks[name].y <= high)
            for name in _FRAMING_LANDMARKS
        ):
            out_of_frame += 1

    if out_of_frame / len(detected) > T.MAX_OUT_OF_FRAME_RATIO:
        return RejectionCode.FRAMING
    return None
