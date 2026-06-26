"""The flaw-detection engine (M6): score → rank → top-3 → prioritized flaws.

This is the public entry point that replaces the M3 mock in ``/analyze``. It runs
every catalog rule over the (already-extracted) pose series, keeps only flaws that
clear their trigger, ranks them by score, and returns the **top 2–3** as
prioritized :class:`~app.analysis.Flaw` objects — or a valid **"no major flaws"**
result when nothing clears the bar. It never pads the list (PRD detection rule).

**Output suppression (``SUPPRESSED_FLAW_IDS``):** the optional ``SUPPRESSED_FLAW_IDS``
environment variable (read per call) is a comma-separated list of :class:`FlawId`
values to drop from the **output only** — the rules still run, but listed flaws are
filtered out before ranking/top-N selection, so they never consume a top-3 slot.
Unknown/garbage tokens are ignored. Unset or empty means no suppression (zero
behavior change). This is a reversible operational lever, not a detection change.
"""

from __future__ import annotations

import os

from app.analysis import AnalysisStatus, Flaw
from app.detection import thresholds as T
from app.detection.catalog import CATALOG_ORDER, FLAW_COPY_BY_ID, FlawId
from app.detection.rules import FlawScore, build_context, score_all
from app.pose.schema import PoseSeries

_SUPPRESSED_FLAW_IDS_ENV = "SUPPRESSED_FLAW_IDS"


def detect_flaws(series: PoseSeries) -> tuple[AnalysisStatus, list[Flaw]]:
    """Detect the top catalog flaws in one swing's landmark series.

    Returns ``(status, flaws)``:

    * ``ANALYZED`` with 1–3 prioritized flaws when at least one clears its trigger
      (``priority`` 1 = highest score);
    * ``NO_MAJOR_FLAWS`` with an empty list when none clear it — a valid result
      (the list is never padded to hit a number).

    Flaws named in ``SUPPRESSED_FLAW_IDS`` are filtered from the output before
    ranking (the rules still run); see the module docstring.
    """
    context = build_context(series)
    if context is None:
        # Too little usable motion to analyze — treat as no major flaws rather
        # than inventing findings. (The M5 gate has already cleared bad input.)
        return AnalysisStatus.NO_MAJOR_FLAWS, []

    suppressed = _suppressed_flaw_ids()
    triggered = [s for s in score_all(context) if s.triggered and s.id not in suppressed]
    triggered.sort(key=_rank_key)
    top = triggered[: T.MAX_REPORTED_FLAWS]

    if not top:
        return AnalysisStatus.NO_MAJOR_FLAWS, []

    flaws = [_to_flaw(priority, score) for priority, score in enumerate(top, start=1)]
    return AnalysisStatus.ANALYZED, flaws


def _suppressed_flaw_ids() -> frozenset[FlawId]:
    """Parse ``SUPPRESSED_FLAW_IDS`` into a set of valid :class:`FlawId` values.

    Parsed defensively: comma-separated, whitespace-stripped, lowercased; empty
    tokens and any token that is not a valid ``FlawId`` are ignored (never raises).
    Unset/empty yields an empty set, i.e. no suppression.
    """
    raw = os.environ.get(_SUPPRESSED_FLAW_IDS_ENV, "")
    ids: set[FlawId] = set()
    for token in raw.split(","):
        value = token.strip().lower()
        if not value:
            continue
        try:
            ids.add(FlawId(value))
        except ValueError:
            continue
    return frozenset(ids)


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
