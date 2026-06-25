"""The flaw-detection engine (M6): score → rank → top-3 → prioritized flaws.

This is the public entry point that replaces the M3 mock in ``/analyze``. It runs
every catalog rule over the (already-extracted) pose series, keeps only flaws that
clear their trigger, ranks them by score, and returns the **top 1–3** as
prioritized :class:`~app.analysis.Flaw` objects — or a valid **"no major flaws"**
result when the engine ran but nothing cleared the bar. It never pads the list
(PRD detection rule).

A swing the engine **could not analyze at all** (it can't be segmented, or the
required landmarks are missing / too low-visibility) is a different outcome: it
raises :class:`UnanalyzableSwingError` so the caller can fail loud rather than
mislabel an un-analyzed swing as clean.
"""

from __future__ import annotations

from app.analysis import AnalysisStatus, Flaw
from app.detection import thresholds as T
from app.detection.catalog import CATALOG_ORDER, FLAW_COPY_BY_ID
from app.detection.rules import FlawScore, build_context, score_all
from app.pose.schema import PoseSeries


class UnanalyzableSwingError(RuntimeError):
    """The engine could not analyze the swing at all.

    Raised when :func:`~app.detection.rules.build_context` cannot assemble a
    context — e.g. the swing can't be segmented into phases, or the landmarks the
    rules need are missing / below the visibility floor. This is **not** the same
    as "the engine ran and found nothing" (a valid ``NO_MAJOR_FLAWS`` result): an
    un-analyzed swing must never be reported as clean. ``detect_flaws`` and any
    internal caller therefore still see the raised exception. The ``/analyze``
    boundary, however, maps it to a graceful **200 rejected** response with reason
    ``framing`` — the same actionable "reframe the shot" outcome as the M5 gate's
    unreadable-wrists path — rather than a 500, because this is a common, user-
    correctable real-world capture (only a passing-gate-but-``None``-series internal
    fault remains a 500). The M5 gate only guarantees core torso visibility +
    angle/framing, so a torso-visible clip with unreadable wrists or too few usable
    frames can pass validation and still land here.
    """


def detect_flaws(series: PoseSeries) -> tuple[AnalysisStatus, list[Flaw]]:
    """Detect the top catalog flaws in one swing's landmark series.

    Returns ``(status, flaws)``:

    * ``ANALYZED`` with 1–3 prioritized flaws when at least one clears its trigger
      (``priority`` 1 = highest score);
    * ``NO_MAJOR_FLAWS`` with an empty list when the engine ran but none cleared it
      — a valid result (the list is never padded to hit a number).

    Raises :class:`UnanalyzableSwingError` when the swing cannot be analyzed at all
    (it can't be segmented or required landmarks are missing/low-visibility), so
    the caller can fail loud instead of mislabeling it as a clean swing.
    """
    context = build_context(series)
    if context is None:
        # The swing couldn't be analyzed (un-segmentable, or required landmarks
        # missing/low-visibility). Surface this as a distinct failure rather than
        # inventing findings OR falsely reporting a clean swing — the M5 gate only
        # guarantees core torso visibility + angle/framing, so an un-analyzable
        # series can still reach here.
        raise UnanalyzableSwingError(
            "The swing could not be analyzed: it can't be segmented or required "
            "landmarks are missing or too low-visibility."
        )

    triggered = [score for score in score_all(context) if score.triggered]
    triggered.sort(key=_rank_key)
    top = triggered[: T.MAX_REPORTED_FLAWS]

    if not top:
        return AnalysisStatus.NO_MAJOR_FLAWS, []

    flaws = [_to_flaw(priority, score) for priority, score in enumerate(top, start=1)]
    return AnalysisStatus.ANALYZED, flaws


def _rank_key(score: FlawScore) -> tuple[float, int]:
    """Rank by score descending, breaking ties by catalog precedence."""
    return (-score.score, CATALOG_ORDER[score.id])


def _to_flaw(priority: int, score: FlawScore) -> Flaw:
    copy = FLAW_COPY_BY_ID[score.id]
    return Flaw(
        priority=priority,
        category=copy.category,
        title=copy.title,
        description=copy.description,
        fix=copy.fix,
    )
