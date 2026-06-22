"""Pose estimation backends.

The pipeline depends only on the :class:`PoseEstimator` protocol, never on
MediaPipe directly. This keeps the heavy, loosely-typed CV dependency at the
edge of the system: downstream code (M5/M6) consumes the typed
:mod:`app.pose.schema` series, and tests can inject a lightweight fake estimator
instead of running real inference.

The production backend, :class:`MediaPipePoseEstimator`, wraps MediaPipe's legacy
``solutions.pose`` API. That API bundles its model weights inside the pip wheel,
so it runs fully offline (important for hermetic CI). MediaPipe is imported
lazily so merely importing this module — or the FastAPI app — stays cheap.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import numpy as np

from app.pose.schema import LANDMARK_ORDER, Landmark, LandmarkName

if TYPE_CHECKING:
    import numpy.typing as npt

    # An RGB frame as a (H, W, 3) array. Kept loose because OpenCV's decode/
    # color-convert return types are only weakly typed.
    FrameRGB = npt.NDArray[Any]
else:
    FrameRGB = np.ndarray


class PoseEstimator(Protocol):
    """Estimates body landmarks for a single RGB frame.

    Implementations may be stateful (e.g. tracking across frames), so a series
    should be processed in order and :meth:`close` called when done.
    """

    def estimate(self, frame_rgb: FrameRGB) -> dict[LandmarkName, Landmark] | None:
        """Return named landmarks for the frame, or ``None`` if no pose is found."""
        ...

    def close(self) -> None:
        """Release any underlying resources."""
        ...


class MediaPipePoseEstimator:
    """:class:`PoseEstimator` backed by MediaPipe ``solutions.pose``.

    Stateful: with ``static_image_mode=False`` MediaPipe tracks the subject
    across frames, which suits a continuous swing clip. Construct one estimator
    per video and :meth:`close` it afterwards (or use it as a context manager).
    """

    def __init__(
        self,
        *,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        # Imported lazily so importing this module (and the app) does not pull in
        # MediaPipe's heavy native stack until pose estimation is actually used.
        import mediapipe as mp

        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=model_complexity,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def estimate(self, frame_rgb: FrameRGB) -> dict[LandmarkName, Landmark] | None:
        result = self._pose.process(frame_rgb)
        raw = getattr(result, "pose_landmarks", None)
        if raw is None:
            return None
        return {
            LANDMARK_ORDER[i]: Landmark(
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=_clamp_unit(lm.visibility),
            )
            for i, lm in enumerate(raw.landmark)
        }

    def close(self) -> None:
        self._pose.close()

    def __enter__(self) -> MediaPipePoseEstimator:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _clamp_unit(value: float) -> float:
    """Clamp a confidence to ``[0.0, 1.0]`` (MediaPipe can emit tiny overshoots)."""
    return max(0.0, min(1.0, float(value)))
