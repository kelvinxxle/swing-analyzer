"""Coarse swing-phase segmentation for flaw detection (M6).

The rules measure change *between phases* (address → top → impact), so the engine
first locates those landmarks in the (detected-frame) series. With no club or ball
to key off, phases are derived from the **hands' height**:

* **address** — a short window of settled frames at the start, the baseline every
  rule compares against;
* **top of backswing** — the **first** hand-height peak (highest hands = minimum
  wrist ``y``) after address; the search locks the peak once the hands descend
  back toward address height, so a high follow-through / finish can't be mistaken
  for the top;
* **impact** — the post-top frame whose hands come **closest** to the address
  height on the way down (the nearest return to baseline, not merely the first).

This is deliberately a heuristic. It is robust enough for the synthetic fixtures
and a first pass on real clips, and is explicitly a candidate for hardening in
**M7** against golden footage. Rules degrade gracefully when the windows are thin.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.detection import thresholds as T
from app.detection.geometry import pair_midpoint
from app.pose.schema import LandmarkName, PoseFrame


@dataclass(frozen=True)
class SwingPhases:
    """Frame positions of the key swing events, indexing the **detected** list.

    All indices refer to positions within ``series.detected_frames`` (not the
    full sampled series), so callers iterate that same ordered list.
    """

    address_start: int
    address_end: int  # exclusive — the address baseline is [start, end)
    top: int
    impact: int


def _mean_wrist_y(frame: PoseFrame) -> float | None:
    """Height (``y``) of the hands' midpoint, or ``None`` if not visible."""
    hands = pair_midpoint(
        frame, LandmarkName.LEFT_WRIST, LandmarkName.RIGHT_WRIST, T.MIN_LANDMARK_VISIBILITY
    )
    return hands[1] if hands is not None else None


def detect_phases(detected: list[PoseFrame]) -> SwingPhases | None:
    """Locate address / top / impact in a list of detected frames.

    Returns ``None`` when the series is too short to segment a swing.
    """
    n = len(detected)
    if n < T.MIN_DETECTED_FRAMES:
        return None

    address_end = min(max(1, round(n * T.ADDRESS_FRACTION)), n)
    wrist_ys = [_mean_wrist_y(frame) for frame in detected]

    address_baseline = _mean(wrist_ys[:address_end])
    if address_baseline is None:
        # Hands unreadable at address: fall back to the first usable height.
        address_baseline = _first(wrist_ys)
    if address_baseline is None:
        return None

    # Top of backswing = the FIRST hand-height peak after address. Locking the
    # first peak (rather than the global minimum) stops a high follow-through /
    # finish from masquerading as the top and dragging impact to the end.
    top = _first_peak_after(wrist_ys, start=address_end, baseline=address_baseline)
    if top is None:
        top = max(address_end, n // 2)

    # Impact = the post-top frame whose hands come closest to address height.
    impact = _return_to_baseline(wrist_ys, after=top, baseline=address_baseline)

    return SwingPhases(address_start=0, address_end=address_end, top=top, impact=impact)


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def _first(values: list[float | None]) -> float | None:
    for v in values:
        if v is not None:
            return v
    return None


def _first_peak_after(
    values: list[float | None], start: int, baseline: float
) -> int | None:
    """Index of the **first** hand-height peak (minimum ``y``) at or after ``start``.

    Tracks the running highest point (smallest ``y``); once the hands descend back
    a meaningful fraction (``TOP_PEAK_DROP_FRACTION``) of the way from that peak
    toward the ``baseline`` address height, the peak is locked in as the top. This
    keeps a later, higher follow-through / finish from being selected as the top of
    the backswing. Skips ``None`` (unreadable) frames.
    """
    best_idx: int | None = None
    best_val = float("inf")
    for i in range(start, len(values)):
        v = values[i]
        if v is None:
            continue
        if v < best_val:
            best_val = v
            best_idx = i
        elif best_idx is not None and baseline > best_val:
            drop = (v - best_val) / (baseline - best_val)
            if drop >= T.TOP_PEAK_DROP_FRACTION:
                break
    return best_idx


def _return_to_baseline(values: list[float | None], after: int, baseline: float) -> int:
    """Post-``after`` frame whose value is **closest** to ``baseline``.

    Models the hands coming back nearest to address height at impact (the nearest
    return to baseline overall, not merely the first crossing). Falls back to the
    last frame when nothing after the top is usable.
    """
    best_idx = len(values) - 1
    best_gap = float("inf")
    for i in range(after + 1, len(values)):
        v = values[i]
        if v is None:
            continue
        gap = abs(v - baseline)
        if gap < best_gap:
            best_gap = gap
            best_idx = i
    return max(best_idx, min(after + 1, len(values) - 1))
