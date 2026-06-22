"""End-to-end pose-extraction pipeline: video file → :class:`PoseSeries`.

Decodes the video with OpenCV, samples frames per :mod:`app.pose.sampling`, runs
a :class:`PoseEstimator` on each sampled frame, and normalizes the result into
the typed :class:`PoseSeries` contract consumed by M5/M6.

Memory is bounded: frames are read and processed one at a time (the pipeline
never holds the whole decoded video in memory), and the sampling budget caps how
many frames are processed per clip.

This module is **internal** to the backend — M4 does not wire it into the
``/analyze`` endpoint, which keeps returning mock results until M6.
"""

from __future__ import annotations

from pathlib import Path

import cv2

from app.pose.config import DEFAULT_SAMPLING, SamplingConfig
from app.pose.estimator import MediaPipePoseEstimator, PoseEstimator
from app.pose.sampling import compute_stride, effective_fps
from app.pose.schema import PoseFrame, PoseSeries


class VideoDecodeError(RuntimeError):
    """Raised when OpenCV cannot open or read the supplied video file."""


def extract_pose_series(
    video_path: str | Path,
    config: SamplingConfig = DEFAULT_SAMPLING,
    estimator: PoseEstimator | None = None,
) -> PoseSeries:
    """Extract a per-frame landmark series from a swing video.

    Args:
        video_path: Path to the (already-saved, ephemeral) video file.
        config: Frame-sampling configuration.
        estimator: Pose backend to use. Defaults to a fresh
            :class:`MediaPipePoseEstimator`; inject a fake for tests. An
            estimator created here is closed before returning; an injected one is
            left open for the caller to manage.

    Returns:
        The normalized :class:`PoseSeries`.

    Raises:
        VideoDecodeError: If the file cannot be opened or has no readable frames.
    """
    path = Path(video_path)
    capture = cv2.VideoCapture(str(path))
    owns_estimator = estimator is None
    pose = estimator if estimator is not None else MediaPipePoseEstimator()
    try:
        if not capture.isOpened():
            raise VideoDecodeError(f"Could not open video: {path}")

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))

        if fps <= 0:
            # Some containers omit FPS metadata; fall back to a sane default so
            # sampling/timestamps stay well-defined rather than dividing by zero.
            fps = config.target_fps

        stride = compute_stride(fps, max(frame_count, 0), config)
        frames = _decode_and_estimate(capture, fps, stride, pose, config.max_frames)

        # Frame count / dimensions may be missing in metadata; recover from what
        # we actually decoded so the series is internally consistent.
        if frame_count <= 0:
            frame_count = frames[-1].source_frame_index + 1 if frames else 0
        if width <= 0 or height <= 0:
            width = width if width > 0 else 1
            height = height if height > 0 else 1

        if frame_count > 0 and not frames:
            raise VideoDecodeError(f"No readable frames in video: {path}")

        return PoseSeries(
            fps=fps,
            sampled_fps=effective_fps(fps, stride),
            frame_count=frame_count,
            sampled_count=len(frames),
            width=width,
            height=height,
            duration_s=(frame_count / fps) if fps > 0 else 0.0,
            frames=frames,
        )
    finally:
        capture.release()
        if owns_estimator:
            pose.close()


def _decode_and_estimate(
    capture: cv2.VideoCapture,
    fps: float,
    stride: int,
    estimator: PoseEstimator,
    max_frames: int,
) -> list[PoseFrame]:
    """Walk the video, estimating pose on every ``stride``-th frame.

    ``max_frames`` is a hard backstop: decoding stops once that many frames have
    been sampled. The stride is normally widened upstream so the cap is rarely
    hit, but when frame-count metadata is missing (``CAP_PROP_FRAME_COUNT`` == 0)
    that widening can't happen — this loop-level cap preserves the bounded-latency
    guarantee regardless.
    """
    frames: list[PoseFrame] = []
    source_index = 0
    sampled_index = 0
    while sampled_index < max_frames:
        grabbed = capture.grab()
        if not grabbed:
            break
        if source_index % stride == 0:
            ok, frame_bgr = capture.retrieve()
            if not ok:
                break
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            landmarks = estimator.estimate(frame_rgb)
            frames.append(
                PoseFrame(
                    index=sampled_index,
                    source_frame_index=source_index,
                    timestamp_s=source_index / fps,
                    detected=landmarks is not None,
                    landmarks=landmarks,
                )
            )
            sampled_index += 1
        source_index += 1
    return frames
