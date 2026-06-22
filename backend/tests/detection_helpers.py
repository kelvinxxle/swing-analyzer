"""Synthetic ``PoseSeries`` builders for flaw-detection tests (M6).

Real labeled swing clips arrive with the golden fixtures in **M7**; until then the
rules are exercised against **constructed** landmark series. We model a simple,
deterministic down-the-line swing as joint *center* trajectories (hips, shoulders,
nose, knees, ankles, hands) over a phase timeline (address → top → impact), then
expand each center into a left/right landmark pair.

A ``make_swing()`` with no flaws is a clean baseline that should score below every
trigger. Each named flaw applies an **isolated** perturbation that exaggerates
exactly that flaw's geometric signal, leaving the others at their clean values —
so a per-rule test can assert "high on its own fixture, low on clean".

Coordinates follow MediaPipe: normalized ``[0, 1]``, ``y`` grows downward. The
default skeleton is bent toward the ball on the ``+x`` side (so ``ball_dir`` is
``+1``); a forward spine tilt of ~29° and clearly flexed knees give the posture
and knee rules room to move.

Joint *centers* are authored in a ``[0, 1]`` **reference square** and then mapped
to whatever ``width`` × ``height`` the series declares, such that the *physical*
(pixel-space) geometry the engine reconstructs is identical regardless of aspect
ratio. So ``make_swing(..., width=720, height=1280)`` (portrait) and
``width=1280, height=720`` (landscape) encode the **same** swing — which is what
the aspect-ratio parity test relies on. The default is a square frame, so the
authored centers are used verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.pose.schema import LANDMARK_ORDER, Landmark, LandmarkName, PoseFrame, PoseSeries

# Side of the reference square the joint centers are authored in. Centers map to a
# real frame as ``norm = center * REFERENCE_DIM / dimension`` per axis, so the
# engine's ``norm * dimension`` recovers ``center * REFERENCE_DIM`` on both axes —
# the same physical geometry for any width/height.
_REFERENCE_DIM = 1000

# Phase timeline (fractions of the clip): settle at address, hands highest at the
# top, hands back down at impact. The rest is follow-through.
_T_ADDRESS_END = 0.15
_T_TOP = 0.45
_T_IMPACT = 0.78

# Hand-height keyframes (mid-wrist y): high backswing dips y, returns near address.
_HAND_HEIGHT = ((0.0, 0.62), (_T_TOP, 0.25), (_T_IMPACT, 0.60), (1.0, 0.40))
# A swing whose finish is HIGHER than the backswing top (hands above the top at the
# end) — used to prove top-of-backswing detection ignores the follow-through.
_HAND_HEIGHT_HIGH_FINISH = ((0.0, 0.62), (_T_TOP, 0.25), (_T_IMPACT, 0.60), (1.0, 0.12))

# Left/right separation in x for each pair — small, as expected down-the-line.
_DX = {
    "shoulder": 0.04,
    "hip": 0.04,
    "knee": 0.04,
    "ankle": 0.04,
    "wrist": 0.02,
}

CLEAN = "clean"
EARLY_EXTENSION = "early_extension"
LOSS_OF_POSTURE = "loss_of_posture"
HEAD_SWAY = "head_sway"
LOSS_OF_KNEE_FLEX = "loss_of_knee_flex"
OVER_THE_TOP = "over_the_top"


@dataclass(frozen=True)
class Centers:
    """The joint-center positions for one frame (pre left/right expansion)."""

    hip_x: float = 0.50
    hip_y: float = 0.60
    sho_x: float = 0.60
    sho_y: float = 0.42
    nose_x: float = 0.58
    nose_y: float = 0.30
    knee_x: float = 0.56
    knee_y: float = 0.75
    ankle_x: float = 0.50
    ankle_y: float = 0.90
    wrist_x: float = 0.58
    wrist_y: float = 0.62


def make_swing(
    flaws: frozenset[str] | set[str] = frozenset(),
    *,
    n: int = 30,
    fps: float = 30.0,
    width: int = _REFERENCE_DIM,
    height: int = _REFERENCE_DIM,
    high_finish: bool = False,
) -> PoseSeries:
    """Build a synthetic down-the-line swing, optionally exhibiting ``flaws``.

    ``width`` / ``height`` set the frame's pixel dimensions; the same swing is
    encoded so that the engine reconstructs identical physical geometry at any
    aspect ratio (the default is square). ``high_finish`` raises the follow-through
    above the backswing top, to exercise top-of-backswing detection.
    """
    keyframes = _HAND_HEIGHT_HIGH_FINISH if high_finish else _HAND_HEIGHT
    frames = [_build_frame(i, n, fps, flaws, width, height, keyframes) for i in range(n)]
    return PoseSeries(
        fps=fps,
        sampled_fps=fps,
        frame_count=n,
        sampled_count=n,
        width=width,
        height=height,
        duration_s=n / fps,
        frames=frames,
    )


def _build_frame(
    i: int,
    n: int,
    fps: float,
    flaws: frozenset[str] | set[str],
    width: int,
    height: int,
    keyframes: tuple[tuple[float, float], ...],
) -> PoseFrame:
    t = i / (n - 1) if n > 1 else 0.0
    centers = _apply_flaws(Centers(wrist_y=_piecewise(t, keyframes)), t, flaws)
    return PoseFrame(
        index=i,
        source_frame_index=i,
        timestamp_s=i / fps,
        detected=True,
        landmarks=_expand(centers, width, height),
    )


def _apply_flaws(c: Centers, t: float, flaws: frozenset[str] | set[str]) -> Centers:
    """Perturb the joint centers for whichever flaws are active at phase ``t``.

    Each perturbation is isolated to the landmarks its rule reads, and ramps in
    over the downswing so address stays the clean baseline.
    """
    d = _downswing_progress(t)

    if EARLY_EXTENSION in flaws:
        # Pelvis (and the upper body / knees riding with it) drives toward the ball
        # while the feet stay planted — trunk angle and knee angle are preserved,
        # so only the hip→ankle offset grows.
        shift = 0.12 * d
        c = replace(c, hip_x=c.hip_x + shift, sho_x=c.sho_x + shift, knee_x=c.knee_x + shift)

    if LOSS_OF_POSTURE in flaws:
        # Chest rises and the spine straightens toward vertical; hands ride up with
        # the shoulders so the hand→shoulder plane offset is unchanged.
        rise = 0.10 * d
        c = replace(c, sho_x=c.sho_x - rise, wrist_x=c.wrist_x - rise)

    if HEAD_SWAY in flaws:
        c = replace(c, nose_x=c.nose_x + 0.12 * d)

    if LOSS_OF_KNEE_FLEX in flaws:
        # Knees straighten toward the hip/ankle line (angle approaches 180°).
        c = replace(c, knee_x=c.knee_x - 0.06 * d)

    if OVER_THE_TOP in flaws and _is_early_downswing(t):
        # Hands jut out toward the ball just after the top, then recover.
        c = replace(c, wrist_x=c.wrist_x + 0.14)

    return c


def _expand(c: Centers, width: int, height: int) -> dict[LandmarkName, Landmark]:
    """Expand joint centers into a full 33-landmark dict (left/right pairs).

    Each center, authored in the reference square, is mapped to normalized frame
    coordinates per axis (``center * REFERENCE_DIM / dimension``) so the engine
    recovers the same physical geometry at any aspect ratio.
    """
    sx = _REFERENCE_DIM / width
    sy = _REFERENCE_DIM / height

    def lm(x: float, y: float) -> Landmark:
        return Landmark(x=x * sx, y=y * sy, z=0.0, visibility=0.95)

    landmarks = {name: lm(0.5, 0.5) for name in LANDMARK_ORDER}
    landmarks[LandmarkName.NOSE] = lm(c.nose_x, c.nose_y)
    pairs: tuple[tuple[LandmarkName, LandmarkName, float, float, str], ...] = (
        (LandmarkName.LEFT_SHOULDER, LandmarkName.RIGHT_SHOULDER, c.sho_x, c.sho_y, "shoulder"),
        (LandmarkName.LEFT_HIP, LandmarkName.RIGHT_HIP, c.hip_x, c.hip_y, "hip"),
        (LandmarkName.LEFT_KNEE, LandmarkName.RIGHT_KNEE, c.knee_x, c.knee_y, "knee"),
        (LandmarkName.LEFT_ANKLE, LandmarkName.RIGHT_ANKLE, c.ankle_x, c.ankle_y, "ankle"),
        (LandmarkName.LEFT_WRIST, LandmarkName.RIGHT_WRIST, c.wrist_x, c.wrist_y, "wrist"),
    )
    for left, right, x, y, kind in pairs:
        dx = _DX[kind]
        landmarks[left] = lm(x - dx, y)
        landmarks[right] = lm(x + dx, y)
    return landmarks


def _downswing_progress(t: float) -> float:
    """0 up to the top, ramping linearly to 1 at impact, then held at 1."""
    if t <= _T_TOP:
        return 0.0
    if t >= _T_IMPACT:
        return 1.0
    return (t - _T_TOP) / (_T_IMPACT - _T_TOP)


def _is_early_downswing(t: float) -> bool:
    window_end = _T_TOP + 0.4 * (_T_IMPACT - _T_TOP)
    return _T_TOP < t <= window_end


def _piecewise(t: float, keys: tuple[tuple[float, float], ...]) -> float:
    """Linear interpolation of ``(t, value)`` keyframes, clamped at the ends."""
    if t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:], strict=False):
        if t0 <= t <= t1:
            span = t1 - t0
            frac = (t - t0) / span if span else 0.0
            return v0 + (v1 - v0) * frac
    return keys[-1][1]
