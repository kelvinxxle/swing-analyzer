"""Shared test helpers for the pose pipeline: synthetic clip generation + fakes.

We deliberately generate tiny synthetic clips at test time rather than committing
binary video fixtures. This keeps the repo lightweight, the tests hermetic (no
network, no large assets), and avoids any third-party footage licensing. Real
swing clips for true landmark-detection assertions arrive with the golden
fixtures in M7.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.pose.schema import LANDMARK_ORDER, Landmark, LandmarkName


def make_synthetic_clip(
    path: Path,
    *,
    frames: int,
    fps: float,
    width: int = 64,
    height: int = 48,
    background: int = 0,
) -> Path:
    """Write a short synthetic MP4 with a moving rectangle and return its path.

    The content is meaningless to pose estimation (no real human) — it exists to
    exercise the decode → sample → structure path deterministically. ``background``
    sets the fill gray level (0–255), useful for brightness-sensitive checks.
    """
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError("Could not open VideoWriter for synthetic clip")
    try:
        for i in range(frames):
            frame = np.full((height, width, 3), background, dtype=np.uint8)
            x = (i * 3) % max(width - 10, 1)
            cv2.rectangle(frame, (x, 10), (x + 8, 30), (255, 255, 255), -1)
            writer.write(frame)
    finally:
        writer.release()
    return path


# Programmatic bad-input clips for the golden harness. Each ``kind`` is engineered
# to trip exactly one M5 rejection rule, so the golden loader can assert a specific
# reason code without committing real footage. ``angle`` / ``framing`` are absent on
# purpose: they need a real human pose (a synthetic clip has none, so it rejects as
# ``no_golfer`` instead) and stay documented skips, covered by the unit checks.
BAD_INPUT_KINDS: tuple[str, ...] = (
    "dark",
    "too_short",
    "low_resolution",
    "no_golfer",
    "unreadable",
)


def build_bad_input_clip(kind: str, directory: Path) -> Path:
    """Generate a degenerate clip that the M5 gate must reject for ``kind``.

    Reuses :func:`make_synthetic_clip` so the golden harness can cover the
    bad-input buckets with zero committed binaries. The dimensions/length mirror
    the synthetic cases already asserted in ``test_analyze.py`` / ``test_validation_*``,
    so the mapped reason code is the same the production gate returns.
    """
    directory = Path(directory)
    if kind == "dark":
        # Black frames → mean luma below MIN_MEAN_LUMA → ``lighting``.
        return make_synthetic_clip(
            directory / "dark.mp4", frames=60, fps=30.0, width=720, height=1280, background=0
        )
    if kind == "too_short":
        # 10 frames @30fps ≈ 0.33s < MIN_DURATION_S → ``too_short``.
        return make_synthetic_clip(
            directory / "too_short.mp4", frames=10, fps=30.0, width=720, height=1280, background=128
        )
    if kind == "low_resolution":
        # Shorter side 48px < MIN_SHORTER_SIDE_PX → ``low_resolution``.
        return make_synthetic_clip(
            directory / "low_res.mp4", frames=60, fps=30.0, width=64, height=48, background=128
        )
    if kind == "no_golfer":
        # Big, bright, long enough to clear the cheap checks, but no human → real
        # MediaPipe finds no pose → ``no_golfer``.
        return make_synthetic_clip(
            directory / "no_golfer.mp4", frames=60, fps=30.0, width=720, height=1280, background=128
        )
    if kind == "unreadable":
        # Claims to be a video but won't decode → ``unreadable``.
        path = directory / "unreadable.mp4"
        path.write_bytes(b"\x00\x01\x02 not really a video")
        return path
    raise ValueError(f"unknown bad-input kind: {kind!r}")


def full_landmark_set(visibility: float = 0.9) -> dict[LandmarkName, Landmark]:
    """A complete, deterministic set of all 33 landmarks for fake estimators."""
    return {
        name: Landmark(x=0.5, y=0.5, z=0.0, visibility=visibility)
        for name in LANDMARK_ORDER
    }


class FakePoseEstimator:
    """A deterministic :class:`PoseEstimator` returning a fixed landmark set.

    Records how many frames it was asked about and whether it was closed, so the
    pipeline's per-frame invocation and resource handling can be asserted.
    """

    def __init__(self, *, detect: bool = True) -> None:
        self._detect = detect
        self.calls = 0
        self.closed = False

    def estimate(self, frame_rgb: np.ndarray) -> dict[LandmarkName, Landmark] | None:
        self.calls += 1
        return full_landmark_set() if self._detect else None

    def close(self) -> None:
        self.closed = True
