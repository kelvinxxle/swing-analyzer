"""Flaw-detection engine (M6).

Rule-based geometric flaw detection over the M4 :class:`~app.pose.schema.PoseSeries`
— no ML, no dataset. Scores a closed catalog of five flaws that are visibly
detectable from the prescribed down-the-line angle, ranks them, and returns the
top 1–3 with a fix tip each (or a valid "no major flaws" result).

This is the engine the ``/analyze`` endpoint runs after the M5 validation gate
passes, reusing the series that gate already extracted.
"""

from __future__ import annotations

from app.detection.catalog import FLAW_CATALOG, FlawCopy, FlawId
from app.detection.engine import UnanalyzableSwingError, detect_flaws

__all__ = [
    "FLAW_CATALOG",
    "FlawCopy",
    "FlawId",
    "UnanalyzableSwingError",
    "detect_flaws",
]
