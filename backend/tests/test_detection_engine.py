"""Flaw-detection engine tests (M6): ranking, the top-3 cap, and the zero path.

These exercise ``detect_flaws`` — the public entry point that replaces the mock —
on synthetic swings: it ranks flaws by score, never returns more than three,
never pads, and reports a valid ``no_major_flaws`` result when nothing clears the
bar.
"""

from __future__ import annotations

import detection_helpers as H
import pytest

from app.analysis import AnalysisStatus, Flaw
from app.detection.catalog import CATALOG_ORDER, FLAW_CATALOG, FlawId
from app.detection.engine import UnanalyzableSwingError, detect_flaws
from app.detection.rules import build_context, score_all
from app.detection.thresholds import MAX_REPORTED_FLAWS, MIN_DETECTED_FRAMES
from app.pose.schema import PoseSeries

_TITLE_TO_ID = {copy.title: copy.id for copy in FLAW_CATALOG}


def _expected_ranking(series: PoseSeries) -> list[FlawId]:
    """The ids the engine *should* return: triggered, by score desc then catalog."""
    context = build_context(series)
    assert context is not None
    triggered = [score for score in score_all(context) if score.triggered]
    triggered.sort(key=lambda s: (-s.score, CATALOG_ORDER[s.id]))
    return [score.id for score in triggered[:MAX_REPORTED_FLAWS]]


def _ids(flaws: list[Flaw]) -> list[FlawId]:
    return [_TITLE_TO_ID[flaw.title] for flaw in flaws]


def test_clean_swing_is_no_major_flaws() -> None:
    # Engine ran fine over an analyzable swing and nothing cleared its bar — a
    # valid zero-result, distinct from "could not analyze" (which raises below).
    status, flaws = detect_flaws(H.make_swing())
    assert status is AnalysisStatus.NO_MAJOR_FLAWS
    assert flaws == []


def test_single_flaw_is_reported() -> None:
    # Per the agreed boundary, one flaw above its bar is reported (not padded,
    # not suppressed). Only zero triggered flaws yields no-major-flaws.
    status, flaws = detect_flaws(H.make_swing({H.HEAD_SWAY}))
    assert status is AnalysisStatus.ANALYZED
    assert len(flaws) == 1
    assert flaws[0].priority == 1
    assert _ids(flaws) == [FlawId.HEAD_SWAY]


def test_flaws_are_ranked_by_score() -> None:
    # Head sway saturates higher than loss of posture, so it must come first.
    series = H.make_swing({H.HEAD_SWAY, H.LOSS_OF_POSTURE})
    status, flaws = detect_flaws(series)

    assert status is AnalysisStatus.ANALYZED
    assert _ids(flaws) == _expected_ranking(series)
    assert _ids(flaws)[0] is FlawId.HEAD_SWAY
    assert [flaw.priority for flaw in flaws] == [1, 2]


def test_caps_at_top_three_and_never_pads() -> None:
    # A swing that trips four rules must surface only the three highest.
    series = H.make_swing(
        {
            H.EARLY_EXTENSION,
            H.LOSS_OF_POSTURE,
            H.HEAD_SWAY,
            H.OVER_THE_TOP,
        }
    )
    context = build_context(series)
    assert context is not None
    triggered = sum(1 for score in score_all(context) if score.triggered)
    assert triggered >= MAX_REPORTED_FLAWS + 1  # more than the cap are present

    status, flaws = detect_flaws(series)
    assert status is AnalysisStatus.ANALYZED
    assert len(flaws) == MAX_REPORTED_FLAWS
    assert [flaw.priority for flaw in flaws] == [1, 2, 3]
    assert _ids(flaws) == _expected_ranking(series)


def test_every_reported_flaw_has_complete_copy() -> None:
    _, flaws = detect_flaws(H.make_swing({H.EARLY_EXTENSION, H.OVER_THE_TOP}))
    assert flaws
    for flaw in flaws:
        assert flaw.category.strip()
        assert flaw.title.strip()
        assert flaw.description.strip()
        assert flaw.fix.strip()


def test_unanalyzable_series_raises_rather_than_reporting_clean() -> None:
    # Too few detected frames to segment a swing → the engine could NOT analyze
    # it. This must surface as a distinct failure, never a falsely-clean
    # no_major_flaws result (the M5 gate only guarantees torso visibility +
    # angle/framing, so an un-analyzable series can still reach the engine).
    with pytest.raises(UnanalyzableSwingError):
        detect_flaws(H.make_swing(n=MIN_DETECTED_FRAMES - 1))
