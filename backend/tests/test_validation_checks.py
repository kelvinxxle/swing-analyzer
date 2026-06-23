"""Unit tests for the individual validation checks (M5).

Cheap checks are exercised through a constructed :class:`VideoProbe`; pose checks
through a constructed :class:`PoseSeries` — no real clip needed, so each reason is
asserted in isolation, pass and fail.
"""

from __future__ import annotations

from pose_helpers import full_landmark_set

from app.pose.schema import Landmark, LandmarkName, PoseFrame, PoseSeries
from app.validation import thresholds as T
from app.validation.checks import VideoProbe, check_cheap, check_pose
from app.validation.result import RejectionCode

# --- Cheap checks -----------------------------------------------------------


def _probe(
    *,
    readable: bool = True,
    width: int = 1080,
    height: int = 1920,
    duration_s: float = 3.0,
    mean_luma: float = 128.0,
) -> VideoProbe:
    return VideoProbe(readable, width, height, duration_s, mean_luma)


def test_cheap_passes_a_good_probe() -> None:
    assert check_cheap(_probe()) is None


def test_cheap_rejects_unreadable() -> None:
    assert check_cheap(_probe(readable=False)) is RejectionCode.UNREADABLE


def test_cheap_rejects_low_resolution() -> None:
    probe = _probe(width=320, height=240)
    assert check_cheap(probe) is RejectionCode.LOW_RESOLUTION


def test_cheap_rejects_too_short() -> None:
    assert check_cheap(_probe(duration_s=0.4)) is RejectionCode.TOO_SHORT


def test_cheap_rejects_low_lighting() -> None:
    assert check_cheap(_probe(mean_luma=10.0)) is RejectionCode.LIGHTING


def test_cheap_ignores_unknown_dimensions_and_duration() -> None:
    # Missing metadata (zeros) must not cause a false rejection.
    assert check_cheap(_probe(width=0, height=0, duration_s=0.0)) is None


def test_cheap_order_resolution_before_lighting() -> None:
    # A clip that is both tiny and dark reports the resolution reason first.
    probe = _probe(width=320, height=240, mean_luma=1.0)
    assert check_cheap(probe) is RejectionCode.LOW_RESOLUTION


# --- Pose checks ------------------------------------------------------------


def _frame(index: int, landmarks: dict[LandmarkName, Landmark] | None) -> PoseFrame:
    return PoseFrame(
        index=index,
        source_frame_index=index,
        timestamp_s=index / 30.0,
        detected=landmarks is not None,
        landmarks=landmarks,
    )


def _series(frames: list[PoseFrame]) -> PoseSeries:
    return PoseSeries(
        fps=30.0,
        sampled_fps=30.0,
        frame_count=len(frames),
        sampled_count=len(frames),
        width=1080,
        height=1920,
        duration_s=len(frames) / 30.0,
        frames=frames,
    )


def _down_the_line_landmarks() -> dict[LandmarkName, Landmark]:
    """A centered golfer with shoulders nearly in line with the camera."""
    landmarks = full_landmark_set(visibility=0.9)
    landmarks[LandmarkName.LEFT_SHOULDER] = Landmark(x=0.50, y=0.4, z=0.0, visibility=0.9)
    landmarks[LandmarkName.RIGHT_SHOULDER] = Landmark(x=0.55, y=0.4, z=0.0, visibility=0.9)
    return landmarks


def test_pose_passes_a_good_down_the_line_series() -> None:
    frames = [_frame(i, _down_the_line_landmarks()) for i in range(10)]
    assert check_pose(_series(frames)) is None


def test_pose_rejects_no_golfer_when_few_frames_detected() -> None:
    frames = [_frame(0, _down_the_line_landmarks())] + [
        _frame(i, None) for i in range(1, 10)
    ]
    assert check_pose(_series(frames)) is RejectionCode.NO_GOLFER


def test_pose_rejects_no_golfer_when_visibility_is_low() -> None:
    faint = full_landmark_set(visibility=0.1)
    frames = [_frame(i, faint) for i in range(10)]
    assert check_pose(_series(frames)) is RejectionCode.NO_GOLFER


def test_pose_rejects_wide_angle() -> None:
    landmarks = full_landmark_set(visibility=0.9)
    landmarks[LandmarkName.LEFT_SHOULDER] = Landmark(x=0.2, y=0.4, z=0.0, visibility=0.9)
    landmarks[LandmarkName.RIGHT_SHOULDER] = Landmark(x=0.8, y=0.4, z=0.0, visibility=0.9)
    frames = [_frame(i, landmarks) for i in range(10)]
    assert check_pose(_series(frames)) is RejectionCode.ANGLE


def test_pose_rejects_out_of_frame() -> None:
    out = _down_the_line_landmarks()
    out[LandmarkName.NOSE] = Landmark(x=0.5, y=1.5, z=0.0, visibility=0.9)
    # Over half the frames clip the golfer → framing reject.
    frames = [_frame(i, out if i % 2 == 0 else _down_the_line_landmarks()) for i in range(10)]
    assert check_pose(_series(frames)) is RejectionCode.FRAMING


def test_pose_no_golfer_takes_priority_over_angle() -> None:
    # Even with a wide angle, an absent golfer is reported first.
    wide = full_landmark_set(visibility=0.9)
    wide[LandmarkName.LEFT_SHOULDER] = Landmark(x=0.1, y=0.4, z=0.0, visibility=0.9)
    wide[LandmarkName.RIGHT_SHOULDER] = Landmark(x=0.9, y=0.4, z=0.0, visibility=0.9)
    frames = [_frame(0, wide)] + [_frame(i, None) for i in range(1, 10)]
    assert check_pose(_series(frames)) is RejectionCode.NO_GOLFER


def test_pose_rejects_too_few_analyzable_frames() -> None:
    # A golfer is clearly present (all frames detected) but there are fewer than
    # the engine's frame floor, so the swing can't be segmented. The gate rejects
    # it as too_short here rather than letting the engine 500 downstream.
    n = T.MIN_ANALYZABLE_DETECTED_FRAMES - 1
    frames = [_frame(i, _down_the_line_landmarks()) for i in range(n)]
    assert check_pose(_series(frames)) is RejectionCode.TOO_SHORT


def test_thresholds_are_sane() -> None:
    assert 0.0 < T.MIN_DETECTED_FRAME_RATIO <= 1.0
    assert 0.0 < T.MAX_OUT_OF_FRAME_RATIO <= 1.0
    assert T.MIN_SHORTER_SIDE_PX > 0
